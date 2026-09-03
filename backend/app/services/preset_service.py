"""Preset service managing demo video metadata, caching, and raw video streaming."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Iterator, Optional
import uuid

import httpx
from fastapi import HTTPException

from backend.app.config import settings
from backend.app.schemas.preset import PresetItem, PresetListResponse

REFERENCE_VIDEO_URL = (
    "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4"
)
PRESET_FILENAME = "behind_the_scenes_pixel.mp4"
DEFAULT_DURATION = 322.87
DEFAULT_SIZE_BYTES = 39519854
DEFAULT_SIZE_MB = 37.69

DEFAULT_PRESETS = [
    PresetItem(
        id="pixel-bts-5m",
        title="Google Pixel Production (5-Min Video)",
        subtitle="Behind the scenes long-form video demonstrating agentic scaling",
        size_mb=37.69,
        mime_type="video/mp4",
        duration_seconds=322.87,
        video_url="/api/preset/video?preset_id=pixel-bts-5m",
        source_url="https://storage.googleapis.com/cloud-samples-data/generative-ai/video/behind_the_scenes_pixel.mp4",
        filename="behind_the_scenes_pixel.mp4",
        default_prompt="Describe the different cameras, equipment, and filming setups used throughout this shoot, and what the director explains about filming on Pixel.",
    ),
    PresetItem(
        id="sustainability-4m",
        title="Google Sustainability (4-Min Keynote)",
        subtitle="Clean energy & data center sustainability presentation",
        size_mb=33.81,
        mime_type="video/mp4",
        duration_seconds=238.03,
        video_url="/api/preset/video?preset_id=sustainability-4m",
        source_url="https://storage.googleapis.com/cloud-samples-data/generative-ai/video/google_sustainability.mp4",
        filename="google_sustainability.mp4",
        default_prompt="What specific clean energy targets and data center sustainability goals are presented in this video?",
    ),
    PresetItem(
        id="sports-10m",
        title="La Liga Football Match (10-Min Video)",
        subtitle="10-minute sports broadcast demonstrating long-form frame retrieval",
        size_mb=27.26,
        mime_type="video/mp4",
        duration_seconds=600.0,
        video_url="/api/preset/video?preset_id=sports-10m",
        source_url="https://storage.googleapis.com/cloud-samples-data/generative-ai/video/sports_match_10m.mp4",
        filename="sports_match_10m.mp4",
        default_prompt="What match is this video showing, which teams are playing, and at what timestamps are goals or major shots attempted?",
    ),
    PresetItem(
        id="blog-demo-58s",
        title="DeepMind Needle Demo (58s Clip)",
        subtitle="Gemini 3.7 Flash Needle-in-a-Haystack benchmark demo",
        size_mb=25.90,
        mime_type="video/mp4",
        duration_seconds=58.67,
        video_url="/api/preset/video?preset_id=blog-demo-58s",
        source_url=REFERENCE_VIDEO_URL,
        filename="KW_SxS-needle_Blog_V1.mp4",
        default_prompt="In the OS terminal demo, what is the utility being used to display the locomotive?",
    ),
]


class PresetService:
    """Service handling preset video retrieval, disk caching, and byte reading."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        presets: Optional[list[PresetItem]] = None,
    ):
        self.cache_dir: Path = cache_dir or settings.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.presets: list[PresetItem] = (
            list(presets) if presets is not None else list(DEFAULT_PRESETS)
        )
        self._presets_by_id: dict[str, PresetItem] = {p.id: p for p in self.presets}
        self._lock: Optional[asyncio.Lock] = None
        self._bytes_cache: dict[str, bytes] = {}

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy-initialize asyncio.Lock on the active running loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def list_presets(self) -> list[PresetItem]:
        """Return all available demo presets."""
        return list(self.presets)

    def get_preset_by_id(self, preset_id: str) -> Optional[PresetItem]:
        """Get preset metadata by preset ID."""
        return self._presets_by_id.get(preset_id)

    def get_primary_preset(self) -> PresetItem:
        """Return primary demo preset."""
        return self.presets[0]

    def get_preset_list_response(self) -> PresetListResponse:
        """Construct full preset response with legacy/flat compatibility fields."""
        primary = self.get_primary_preset()
        return PresetListResponse(
            presets=self.presets,
            id=primary.id,
            title=primary.title,
            filename=primary.filename or PRESET_FILENAME,
            duration_seconds=primary.duration_seconds,
            size_bytes=int(primary.size_mb * 1024 * 1024),
            size_formatted=f"{primary.size_mb:.2f} MB • {primary.mime_type}",
            mime_type=primary.mime_type,
            media_url=primary.video_url,
            source_url=primary.source_url,
            default_prompt=primary.default_prompt,
            status="ready",
        )

    def get_cached_video_path(self, preset_id: Optional[str] = None) -> Path:
        """Get local cached file path for a preset video."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if preset_id:
            preset = self.get_preset_by_id(preset_id)
            if preset and preset.filename:
                return self.cache_dir / preset.filename
            if preset_id == "pixel-bts-5m":
                return self.cache_dir / "behind_the_scenes_pixel.mp4"
            if preset_id == "sustainability-4m":
                return self.cache_dir / "google_sustainability.mp4"
            if preset_id == "blog-demo-58s":
                return self.cache_dir / "KW_SxS-needle_Blog_V1.mp4"
        primary = self.get_primary_preset()
        filename = primary.filename if primary and primary.filename else PRESET_FILENAME
        return self.cache_dir / filename

    async def ensure_video_cached(self, preset_id: Optional[str] = None) -> Path:
        """Ensure the reference video is downloaded to local cache with atomic locking."""
        effective_id = preset_id or self.get_primary_preset().id
        preset = self.get_preset_by_id(effective_id) or self.get_primary_preset()
        video_path = self.get_cached_video_path(effective_id)
        if video_path.is_file() and video_path.stat().st_size > 0:
            return video_path

        source_url = preset.source_url or REFERENCE_VIDEO_URL

        async with self.lock:
            # Double-check inside lock
            if video_path.is_file() and video_path.stat().st_size > 0:
                return video_path

            temp_path = video_path.with_name(
                f"{video_path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
            )
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    async with client.stream("GET", source_url) as response:
                        if response.status_code != 200:
                            raise HTTPException(
                                status_code=502,
                                detail=f"Failed to fetch reference video from upstream: {response.status_code}",
                            )
                        with open(temp_path, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                                f.write(chunk)

                temp_path.replace(video_path)
            finally:
                if temp_path.is_file():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass

        return video_path

    async def get_cached_video_bytes(self, preset_id: Optional[str] = None) -> bytes:
        """Return cached video bytes for inline payload construction."""
        cache_key = preset_id or self.get_primary_preset().id
        if cache_key in self._bytes_cache:
            return self._bytes_cache[cache_key]

        video_path = await self.ensure_video_cached(preset_id)
        data = video_path.read_bytes()
        self._bytes_cache[cache_key] = data
        return data

    async def ensure_url_cached(self, url: str, filename: Optional[str] = None) -> Path:
        """Download and cache an arbitrary HTTP/HTTPS video URL."""
        if not filename:
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
            filename = f"custom_video_{url_hash}.mp4"

        target_path = self.cache_dir / filename
        if target_path.is_file() and target_path.stat().st_size > 0:
            return target_path

        async with self.lock:
            if target_path.is_file() and target_path.stat().st_size > 0:
                return target_path

            temp_path = target_path.with_name(
                f"{target_path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
            )
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    async with client.stream("GET", url) as response:
                        if response.status_code != 200:
                            raise HTTPException(
                                status_code=400,
                                detail={
                                    "error": "video_download_failed",
                                    "message": f"Failed to download video from URL: HTTP {response.status_code}",
                                },
                            )
                        with open(temp_path, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                                f.write(chunk)
                temp_path.replace(target_path)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "invalid_video_url",
                        "message": f"Could not retrieve video from URL '{url}': {exc}",
                    },
                ) from exc
            finally:
                if temp_path.is_file():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass

        return target_path

    def stream_video_slice(
        self, file_path: Path, start: int, length: int, chunk_size: int = 256 * 1024
    ) -> Iterator[bytes]:
        """Yield file slices chunk-by-chunk for HTTP StreamingResponse."""
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                bytes_to_read = min(remaining, chunk_size)
                chunk = f.read(bytes_to_read)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk


# Singleton instance
preset_service = PresetService()


def get_preset_service() -> PresetService:
    """FastAPI dependency provider returning PresetService singleton."""
    return preset_service


# Module-level convenience functions matching legacy interface
ensure_video_cached = preset_service.ensure_video_cached
get_cached_video_path = preset_service.get_cached_video_path
PRESETS = preset_service.presets
