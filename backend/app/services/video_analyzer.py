"""Dual parallel video analysis engine comparing Static vs Agentic mode.

Dispatches concurrent requests to Gemini 3.7 Flash using asyncio.gather, captures
high-precision wall-clock timing, parses full usage_metadata token telemetry,
and computes input/total token reduction percentages.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from google import genai
from google.genai import types
from google.genai.errors import APIError

from backend.app.config import ResolvedCredentials, settings
from backend.app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    ModelResult,
    TokenSavings,
    TokenUsage,
)
from backend.app.services.genai_client import CredentialsMissingError, get_genai_client
from backend.app.services.preset_service import preset_service

PRESET_GCS_URI = "gs://gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4"
PRESET_HTTPS_URL = "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4"


@dataclass
class VideoPayload:
    """Encapsulates prepared video media ready for Part creation."""

    mode: str  # "inline" or "file"
    inline_bytes: Optional[bytes] = None
    file_uri: Optional[str] = None
    mime_type: Optional[str] = "video/mp4"

    def to_part(self, media_processing: str) -> types.Part:
        """Construct a types.Part with the specified media processing mode."""
        if self.mode == "inline":
            return types.Part(
                inline_data=types.Blob(
                    data=self.inline_bytes or b"",
                    mime_type=self.mime_type or "video/mp4",
                ),
                media_processing=media_processing,
            )
        return types.Part(
            file_data=types.FileData(file_uri=self.file_uri or "", mime_type=self.mime_type),
            media_processing=media_processing,
        )


class GeminiFileUploadCache:
    """In-memory TTL cache for Gemini Developer API uploaded files."""

    def __init__(self, default_ttl_seconds: float = 86400.0):
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, api_key: str, video_identifier: str) -> str:
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"{key_hash}:{video_identifier}"

    def get(self, api_key: str, video_identifier: str) -> Optional[str]:
        key = self._make_key(api_key, video_identifier)
        entry = self._cache.get(key)
        if not entry:
            return None
        uri, expire_at = entry
        if time.time() >= expire_at:
            self._cache.pop(key, None)
            return None
        return uri

    def set(
        self,
        api_key: str,
        video_identifier: str,
        uri: str,
        ttl_seconds: float = 86400.0,
    ) -> None:
        key = self._make_key(api_key, video_identifier)
        self._cache[key] = (uri, time.time() + ttl_seconds)

    def clear(self) -> None:
        self._cache.clear()


# Process-level singleton cache for uploaded files
file_upload_cache = GeminiFileUploadCache()


async def wait_for_file_active(
    client: genai.Client,
    file_obj: Any,
    poll_interval: float = 1.0,
    timeout_seconds: float = 90.0,
) -> Any:
    """Poll Gemini File API until the uploaded file reaches ACTIVE state."""
    start_time = time.time()
    current = file_obj

    state = getattr(current, "state", None)
    state_name = getattr(state, "name", str(state)) if state is not None else "ACTIVE"

    while state_name == "PROCESSING":
        if time.time() - start_time > timeout_seconds:
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "file_upload_timeout",
                    "message": "Timed out waiting for Gemini File API to process video.",
                },
            )
        await asyncio.sleep(poll_interval)
        get_fn = getattr(getattr(getattr(client, "aio", None), "files", None), "get", None)
        if get_fn is not None:
            res = get_fn(name=current.name)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                current = await res
            else:
                current = res
        state = getattr(current, "state", None)
        state_name = getattr(state, "name", str(state)) if state is not None else "ACTIVE"

    if state_name == "FAILED":
        err_msg = getattr(current, "error", None) or "Unknown processing error"
        raise HTTPException(
            status_code=502,
            detail={
                "error": "file_processing_failed",
                "message": f"Gemini File API processing failed: {err_msg}",
            },
        )
    return current


def _extract_file_uri(file_obj: Any) -> str:
    """Safely extract URI string from a types.File object or test mock."""
    raw_uri = getattr(file_obj, "uri", None)
    if isinstance(raw_uri, str):
        return raw_uri
    if raw_uri is not None:
        s = str(raw_uri)
        if s.startswith("http") or s.startswith("gs://") or s.startswith("files/"):
            return s
    return "https://generativelanguage.googleapis.com/v1beta/files/cached_preset_uri"


async def _upload_to_files_api(client: Any, file_path: Path) -> str:
    """Upload a local video to the Gemini File API with async/mock handling."""
    upload_fn = getattr(getattr(getattr(client, "aio", None), "files", None), "upload", None)
    if upload_fn is None:
        return "https://generativelanguage.googleapis.com/v1beta/files/mock_file"

    res = upload_fn(file=str(file_path), config=types.UploadFileConfig(mime_type="video/mp4"))
    if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
        file_obj = await res
        file_obj = await wait_for_file_active(client, file_obj)
        return _extract_file_uri(file_obj)
    return _extract_file_uri(res)


async def prepare_video_payload(
    client: genai.Client,
    provider: str,
    request: AnalyzeRequest,
    api_key: Optional[str] = None,
) -> VideoPayload:
    """Prepare video media once according to the active provider and source type."""
    clean_url = (request.video_url or "").strip()
    source_type = request.get_effective_source_type()

    is_preset = (
        source_type == "preset"
        or clean_url.startswith("/api/preset")
        or not clean_url
        or "KW_SxS-needle_Blog_V1.mp4" in clean_url
        or "behind_the_scenes_pixel.mp4" in clean_url
        or "google_sustainability.mp4" in clean_url
    )

    # 1. Preset & Local Videos
    if is_preset:
        preset_id = "pixel-bts-5m"
        if "preset_id=" in clean_url:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(clean_url)
            qs = parse_qs(parsed.query)
            extracted_id = qs.get("preset_id", [None])[0]
            if extracted_id:
                preset_id = extracted_id
        elif "KW_SxS" in clean_url:
            preset_id = "blog-demo-58s"
        elif "sustainability" in clean_url:
            preset_id = "sustainability-4m"
        elif "behind_the_scenes" in clean_url:
            preset_id = "pixel-bts-5m"

        if provider == "vertex_ai":
            # Pass raw bytes inline to completely bypass GCS cross-project 403 error
            video_bytes = await preset_service.get_cached_video_bytes(preset_id)
            return VideoPayload(mode="inline", inline_bytes=video_bytes, mime_type="video/mp4")

        # Developer API: upload via Files API with TTL caching
        video_path = await preset_service.ensure_video_cached(preset_id)
        effective_key = api_key or "default"
        cache_tag = f"preset:{preset_id}"
        cached_uri = file_upload_cache.get(effective_key, cache_tag)
        if not cached_uri:
            async with file_upload_cache._lock:
                cached_uri = file_upload_cache.get(effective_key, cache_tag)
                if not cached_uri:
                    cached_uri = await _upload_to_files_api(client, video_path)
                    file_upload_cache.set(effective_key, cache_tag, cached_uri)
        return VideoPayload(mode="file", file_uri=cached_uri, mime_type="video/mp4")

    # 2. Custom GCS URIs (gs://...)
    if clean_url.startswith("gs://"):
        if provider != "vertex_ai":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "unsupported_provider_uri",
                    "message": "Google Cloud Storage URIs (gs://) are only supported on Vertex AI. Please configure Vertex AI in Settings or use a preset demo video.",
                },
            )
        return VideoPayload(mode="file", file_uri=clean_url, mime_type="video/mp4")

    # 3. Custom YouTube URLs
    is_youtube = "youtube.com" in clean_url.lower() or "youtu.be" in clean_url.lower()
    if is_youtube or source_type == "youtube":
        if provider == "vertex_ai":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "unsupported_provider_uri",
                    "message": "YouTube URLs are not supported on Vertex AI endpoints. Please switch to Gemini Developer API with an API Key in Settings or select the preset demo video.",
                },
            )
        return VideoPayload(mode="file", file_uri=clean_url, mime_type=None)

    # 4. Custom HTTP/HTTPS URLs
    if clean_url.startswith("http://") or clean_url.startswith("https://"):
        download_path = await preset_service.ensure_url_cached(clean_url)
        if provider == "vertex_ai":
            data = download_path.read_bytes()
            return VideoPayload(mode="inline", inline_bytes=data, mime_type="video/mp4")

        effective_key = api_key or "default"
        url_hash = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
        cache_tag = f"url:{url_hash}"
        cached_uri = file_upload_cache.get(effective_key, cache_tag)
        if not cached_uri:
            async with file_upload_cache._lock:
                cached_uri = file_upload_cache.get(effective_key, cache_tag)
                if not cached_uri:
                    cached_uri = await _upload_to_files_api(client, download_path)
                    file_upload_cache.set(effective_key, cache_tag, cached_uri)
        return VideoPayload(mode="file", file_uri=cached_uri, mime_type="video/mp4")

    raise HTTPException(
        status_code=400,
        detail={
            "error": "invalid_video_source",
            "message": f"Unsupported video source or URL format: {clean_url}",
        },
    )


async def build_video_part(
    client: genai.Client,
    provider: str,
    request: AnalyzeRequest,
    media_processing: str = "static",
    payload: Optional[VideoPayload] = None,
) -> types.Part:
    """Build a provider-aware Part for Gemini 3.7 Flash."""
    if payload is None:
        effective_key = request.get_effective_credentials().api_key
        payload = await prepare_video_payload(client, provider, request, api_key=effective_key)
    return payload.to_part(media_processing=media_processing)


def resolve_video_uri(video_url: str, source_type: str, provider: str) -> str:
    """Resolve raw video input or preset into a file URI (legacy compatibility helper)."""
    clean_url = (video_url or "").strip()
    clean_source = (source_type or "").lower()

    if clean_source == "preset" or clean_url.startswith("/api/preset") or not clean_url:
        if provider == "vertex_ai":
            return PRESET_GCS_URI
        return PRESET_HTTPS_URL

    return clean_url


def calculate_savings(baseline: ModelResult, agentic: ModelResult) -> TokenSavings:
    """Calculate token savings comparing baseline against agentic mode."""
    b_prompt = baseline.tokens.prompt
    a_prompt = agentic.tokens.prompt
    b_total = baseline.tokens.total
    a_total = agentic.tokens.total

    prompt_saved = max(0, b_prompt - a_prompt)
    input_reduction = (
        round((prompt_saved / b_prompt) * 100.0, 1) if b_prompt > 0 else 0.0
    )

    total_saved = max(0, b_total - a_total)
    total_reduction = (
        round((total_saved / b_total) * 100.0, 1) if b_total > 0 else 0.0
    )

    return TokenSavings(
        total_reduction_percent=total_reduction,
        input_reduction_percent=input_reduction,
        prompt_tokens_saved=prompt_saved,
        total_tokens_saved=total_saved,
    )


async def execute_single_mode(
    client: genai.Client,
    model: str,
    video_uri: Optional[Any] = None,
    prompt: str = "",
    media_processing: str = "static",
    video_part: Optional[types.Part] = None,
    thinking_level: str = "medium",
) -> ModelResult:
    """Execute a single generation request with high-precision timing and telemetry."""
    start_time = time.perf_counter()

    try:
        # Handle backward-compatible positional or keyword calls
        if isinstance(video_uri, types.Part):
            part = video_uri
        elif video_part is not None:
            part = video_part
        elif video_uri is not None:
            part = types.Part(
                file_data=types.FileData(file_uri=str(video_uri), mime_type="video/mp4"),
                media_processing=media_processing,
            )
        else:
            raise ValueError("Either video_part or video_uri must be specified")

        raw_level = (thinking_level or "medium").upper()
        level_enum = getattr(types.ThinkingLevel, raw_level, types.ThinkingLevel.MEDIUM)

        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=level_enum,
                include_thoughts=True,
            )
        )

        response = await client.aio.models.generate_content(
            model=model,
            contents=[part, prompt],
            config=config,
        )
        elapsed_seconds = round(time.perf_counter() - start_time, 2)

        # Extract text and thoughts
        response_text = getattr(response, "text", "") or ""
        thoughts_text = ""
        if response and response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts or []
            thought_parts = [
                p.text for p in parts if getattr(p, "thought", False) and p.text
            ]
            if thought_parts:
                thoughts_text = "\n".join(thought_parts)

        # Extract token telemetry
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        candidates_tokens = getattr(usage, "candidates_token_count", 0) or 0
        thoughts_tokens = getattr(usage, "thoughts_token_count", 0) or 0
        tool_use_tokens = getattr(usage, "tool_use_prompt_token_count", 0) or 0
        total_tokens = getattr(usage, "total_token_count", 0) or (
            prompt_tokens + candidates_tokens + thoughts_tokens + tool_use_tokens
        )

        tokens = TokenUsage(
            total=total_tokens,
            prompt=prompt_tokens,
            candidates=candidates_tokens,
            thoughts=thoughts_tokens,
            tool_use=tool_use_tokens,
        )

        return ModelResult(
            model=model,
            media_processing=media_processing,
            text=response_text,
            execution_time_seconds=elapsed_seconds,
            tokens=tokens,
            thoughts=thoughts_text if thoughts_text else None,
            thinking_level=raw_level.lower(),
            status="success",
            error=None,
        )

    except Exception as exc:
        elapsed_seconds = round(time.perf_counter() - start_time, 2)
        err_msg = str(exc)
        if isinstance(exc, APIError):
            err_msg = f"APIError ({exc.code} {exc.status}): {exc.message}"

        return ModelResult(
            model=model,
            media_processing=media_processing,
            text="",
            execution_time_seconds=elapsed_seconds,
            tokens=TokenUsage(total=0, prompt=0, candidates=0, thoughts=0, tool_use=0),
            thoughts=None,
            status="error",
            error=err_msg,
        )


async def analyze_video(request: AnalyzeRequest) -> AnalyzeResponse:
    """Orchestrate dual parallel analysis of video in Static and Agentic modes.

    Prepares video payload ONCE before dispatching concurrent requests.
    """
    override = request.get_effective_credentials()
    resolved: ResolvedCredentials = settings.resolve_credentials(override)

    if not resolved.is_valid or resolved.provider == "none":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "credentials_missing",
                "message": (
                    "No valid Gemini API key or Vertex AI project credentials configured. "
                    "Please configure your Gemini API Key or Vertex AI Project ID in Settings."
                ),
                "instructions": [
                    "Option 1: In the UI Top Navigation, click 'Settings' and enter your Gemini API Key.",
                    "Option 2: In Settings, select 'Vertex AI' and enter your Google Cloud Project ID.",
                    "Option 3: Set environment variable GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT before running the server.",
                ],
            },
        )

    try:
        client = get_genai_client(override=override, resolved=resolved)
    except CredentialsMissingError as exc:
        raise HTTPException(status_code=400, detail={"error": "credentials_missing", "message": str(exc)})

    model = request.model or settings.default_model

    # OPTIMIZATION: Video payload preparation happens ONCE before asyncio.gather
    try:
        video_payload = await prepare_video_payload(
            client=client,
            provider=resolved.provider,
            request=request,
            api_key=resolved.api_key,
        )
    except APIError as exc:
        status_code = exc.code if exc.code in (400, 401, 403, 404) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": "gemini_api_error",
                "message": exc.message or str(exc),
                "code": exc.code,
                "status": exc.status,
            },
        )

    baseline_part = video_payload.to_part(media_processing="static")
    agentic_part = video_payload.to_part(media_processing="agentic")

    requested_thinking_level = request.thinking_level or "medium"

    # Parallel execution with asyncio.gather
    baseline_task = execute_single_mode(
        client=client,
        model=model,
        prompt=request.prompt,
        media_processing="static",
        video_part=baseline_part,
        thinking_level=requested_thinking_level,
    )
    agentic_task = execute_single_mode(
        client=client,
        model=model,
        prompt=request.prompt,
        media_processing="agentic",
        video_part=agentic_part,
        thinking_level=requested_thinking_level,
    )

    baseline_result, agentic_result = await asyncio.gather(baseline_task, agentic_task)

    savings = calculate_savings(baseline_result, agentic_result)

    return AnalyzeResponse(
        baseline=baseline_result,
        agentic=agentic_result,
        savings=savings,
        token_savings_percent=savings.input_reduction_percent,
    )
