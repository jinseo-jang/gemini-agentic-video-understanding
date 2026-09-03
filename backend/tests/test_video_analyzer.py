"""Unit tests for video analyzer engine, token calculations, and parallel execution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.schemas.analyze import (
    AnalyzeRequest,
    CredentialsOverride,
    ModelResult,
    TokenUsage,
)
from backend.app.services.video_analyzer import (
    analyze_video,
    build_video_part,
    calculate_savings,
    execute_single_mode,
    file_upload_cache,
    prepare_video_payload,
    resolve_video_uri,
)


def test_calculate_savings_standard():
    """Verify input and total token reduction calculations."""
    baseline = ModelResult(
        media_processing="static",
        text="Baseline answer",
        execution_time_seconds=20.0,
        tokens=TokenUsage(total=100000, prompt=95000, candidates=100, thoughts=0),
    )
    agentic = ModelResult(
        media_processing="agentic",
        text="Agentic answer",
        execution_time_seconds=25.0,
        tokens=TokenUsage(total=30000, prompt=3800, candidates=200, thoughts=26000),
    )

    savings = calculate_savings(baseline, agentic)

    # Input token savings: (95000 - 3800) / 95000 * 100 = 96.0%
    assert savings.input_reduction_percent == 96.0
    assert savings.prompt_tokens_saved == 91200
    # Total token savings: (100000 - 30000) / 100000 * 100 = 70.0%
    assert savings.total_reduction_percent == 70.0
    assert savings.total_tokens_saved == 70000


def test_calculate_savings_zero_tokens_edge_case():
    """Verify no division by zero when token counts are zero."""
    baseline = ModelResult(
        media_processing="static",
        tokens=TokenUsage(total=0, prompt=0, candidates=0, thoughts=0),
    )
    agentic = ModelResult(
        media_processing="agentic",
        tokens=TokenUsage(total=0, prompt=0, candidates=0, thoughts=0),
    )

    savings = calculate_savings(baseline, agentic)
    assert savings.input_reduction_percent == 0.0
    assert savings.total_reduction_percent == 0.0
    assert savings.prompt_tokens_saved == 0


def test_resolve_video_uri_preset():
    """Verify preset video resolves to GCS for Vertex AI and HTTPS for API Key."""
    uri_vertex = resolve_video_uri("/api/preset/video", "preset", "vertex_ai")
    assert uri_vertex.startswith("gs://")

    uri_apikey = resolve_video_uri("/api/preset/video", "preset", "gemini_api_key")
    assert uri_apikey.startswith("https://")


def test_resolve_video_uri_youtube_and_direct():
    """Verify YouTube URLs and direct GCS/HTTPS URIs are preserved."""
    yt = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert resolve_video_uri(yt, "youtube", "vertex_ai") == yt

    gcs = "gs://custom-bucket/test.mp4"
    assert resolve_video_uri(gcs, "url", "vertex_ai") == gcs


@pytest.mark.asyncio
async def test_execute_single_mode_success(dummy_agentic_response):
    """Verify execute_single_mode returns populated ModelResult and timing."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=dummy_agentic_response)

    result = await execute_single_mode(
        client=mock_client,
        model="gemini-3.7-flash",
        video_uri="gs://test-bucket/video.mp4",
        prompt="Describe the scene",
        media_processing="agentic",
    )

    assert result.status == "success"
    assert result.media_processing == "agentic"
    assert "Partner X" in result.text
    assert result.tokens.prompt == 4800
    assert result.tokens.thoughts == 85000
    assert result.tokens.tool_use == 7000
    assert result.tokens.total == 96950
    assert result.thoughts is not None
    assert "Analyzing video frames" in result.thoughts


@pytest.mark.asyncio
async def test_execute_single_mode_error_resilience():
    """Verify execute_single_mode handles API errors gracefully."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Quota exceeded 429")
    )

    result = await execute_single_mode(
        client=mock_client,
        model="gemini-3.7-flash",
        video_uri="gs://test-bucket/video.mp4",
        prompt="Describe the scene",
        media_processing="static",
    )

    assert result.status == "error"
    assert "Quota exceeded 429" in result.error
    assert result.tokens.total == 0


@pytest.mark.asyncio
async def test_analyze_video_orchestration(dummy_static_response, dummy_agentic_response):
    """Verify analyze_video orchestrates dual execution and computes savings."""
    mock_client = MagicMock()

    async def side_effect(model, contents, config):
        # Examine part media_processing
        part = contents[0]
        proc = str(getattr(part, "media_processing", "")).upper()
        if "STATIC" in proc:
            return dummy_static_response
        return dummy_agentic_response

    mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)

    with patch("backend.app.services.video_analyzer.get_genai_client", return_value=mock_client):
        request = AnalyzeRequest(
            video_url="/api/preset/video",
            video_source_type="preset",
            prompt="What is the logo?",
            api_key="test_dummy_key",
        )

        response = await analyze_video(request)

        assert response.baseline.media_processing == "static"
        assert response.baseline.tokens.prompt == 120000

        assert response.agentic.media_processing == "agentic"
        assert response.agentic.tokens.prompt == 4800

        assert response.savings.input_reduction_percent == 96.0
        assert response.savings.prompt_tokens_saved == 115200


@pytest.mark.asyncio
async def test_analyze_video_missing_credentials():
    """Verify analyze_video raises HTTP 400 when credentials are missing."""
    with patch("backend.app.services.video_analyzer.settings.resolve_credentials") as mock_resolve:
        from backend.app.config import ResolvedCredentials

        mock_resolve.return_value = ResolvedCredentials(provider="none", is_valid=False)

        request = AnalyzeRequest(
            video_url="/api/preset/video",
            prompt="What is the logo?",
        )

        with pytest.raises(HTTPException) as exc_info:
            await analyze_video(request)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "credentials_missing"


@pytest.mark.asyncio
async def test_analyze_video_partial_error(dummy_static_response):
    """Verify that if one mode encounters an error, the overall response still returns both results."""
    mock_client = MagicMock()

    async def side_effect(model, contents, config):
        part = contents[0]
        proc = str(getattr(part, "media_processing", "")).upper()
        if "STATIC" in proc:
            return dummy_static_response
        raise RuntimeError("Agentic mode timed out")

    mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)

    with patch("backend.app.services.video_analyzer.get_genai_client", return_value=mock_client):
        request = AnalyzeRequest(
            video_url="/api/preset/video",
            prompt="Find key points",
            api_key="valid_key",
        )

        response = await analyze_video(request)

        assert response.baseline.status == "success"
        assert response.baseline.tokens.prompt == 120000

        assert response.agentic.status == "error"
        assert "Agentic mode timed out" in response.agentic.error
        assert response.agentic.tokens.total == 0


def test_analyze_request_credential_helpers():
    """Verify get_effective_credentials and get_effective_source_type behaviors."""
    req1 = AnalyzeRequest(
        video_url="https://youtube.com/watch?v=123",
        video_source="youtube",
        prompt="Test",
        api_key="top_key",
    )
    creds1 = req1.get_effective_credentials()
    assert creds1.api_key == "top_key"
    assert req1.get_effective_source_type() == "youtube"

    req2 = AnalyzeRequest(
        video_url="/api/preset/video",
        prompt="Test",
        credentials=CredentialsOverride(api_key="nested_key", project="nested_project"),
    )
    creds2 = req2.get_effective_credentials()
    assert creds2.api_key == "nested_key"
    assert creds2.project == "nested_project"
    assert req2.get_effective_source_type() == "preset"


@pytest.mark.asyncio
async def test_build_video_part_preset_vertex_ai_inline():
    """Verify build_video_part with Vertex AI provider returns inline_data Blob (bypassing GCS 403)."""
    mock_client = MagicMock()
    request = AnalyzeRequest(
        video_url="/api/preset/video",
        video_source_type="preset",
        prompt="Test prompt",
    )

    with patch("backend.app.services.video_analyzer.preset_service.get_cached_video_bytes", new=AsyncMock(return_value=b"PRESET_RAW_BYTES")):
        part = await build_video_part(
            client=mock_client,
            provider="vertex_ai",
            request=request,
            media_processing="agentic",
        )

    assert part.inline_data is not None
    assert part.inline_data.data == b"PRESET_RAW_BYTES"
    assert part.inline_data.mime_type == "video/mp4"
    assert part.file_data is None
    proc = str(part.media_processing).upper()
    assert "AGENTIC" in proc


@pytest.mark.asyncio
async def test_build_video_part_preset_developer_api_file_upload(tmp_path):
    """Verify build_video_part with Gemini Developer API provider uploads via Files API and caches."""
    file_upload_cache.clear()

    mock_client = MagicMock()
    mock_file = MagicMock()
    mock_file.uri = "https://generativelanguage.googleapis.com/v1beta/files/test_file_id"
    mock_file.state = MagicMock(name="ACTIVE")
    mock_file.state.name = "ACTIVE"

    mock_client.aio.files.upload = AsyncMock(return_value=mock_file)
    mock_client.aio.files.get = AsyncMock(return_value=mock_file)

    request = AnalyzeRequest(
        video_url="/api/preset/video",
        video_source_type="preset",
        prompt="Test prompt",
        api_key="test_api_key_123",
    )

    fake_video = tmp_path / "test.mp4"
    fake_video.write_bytes(b"DATA")

    with patch("backend.app.services.video_analyzer.preset_service.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
        part1 = await build_video_part(
            client=mock_client,
            provider="gemini_api_key",
            request=request,
            media_processing="static",
        )
        assert part1.file_data is not None
        assert part1.file_data.file_uri == "https://generativelanguage.googleapis.com/v1beta/files/test_file_id"
        assert mock_client.aio.files.upload.await_count == 1

        # Second call should use cache and NOT invoke upload again
        part2 = await build_video_part(
            client=mock_client,
            provider="gemini_api_key",
            request=request,
            media_processing="agentic",
        )
        assert part2.file_data is not None
        assert part2.file_data.file_uri == "https://generativelanguage.googleapis.com/v1beta/files/test_file_id"
        assert mock_client.aio.files.upload.await_count == 1


@pytest.mark.asyncio
async def test_build_video_part_gcs_vertex_ai_supported():
    """Verify custom GCS URI is supported on Vertex AI."""
    mock_client = MagicMock()
    request = AnalyzeRequest(
        video_url="gs://my-customer-bucket/video.mp4",
        video_source_type="url",
        prompt="Test GCS",
    )

    part = await build_video_part(
        client=mock_client,
        provider="vertex_ai",
        request=request,
        media_processing="static",
    )
    assert part.file_data is not None
    assert part.file_data.file_uri == "gs://my-customer-bucket/video.mp4"


@pytest.mark.asyncio
async def test_build_video_part_gcs_developer_api_raises_400():
    """Verify custom GCS URI is rejected on Developer API with HTTP 400."""
    mock_client = MagicMock()
    request = AnalyzeRequest(
        video_url="gs://my-customer-bucket/video.mp4",
        video_source_type="url",
        prompt="Test GCS",
    )

    with pytest.raises(HTTPException) as exc_info:
        await build_video_part(
            client=mock_client,
            provider="gemini_api_key",
            request=request,
            media_processing="static",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "unsupported_provider_uri"


@pytest.mark.asyncio
async def test_build_video_part_youtube_vertex_ai_supported():
    """Verify YouTube URL on Vertex AI is passed as file_data with mime_type='video/mp4'."""
    mock_client = MagicMock()
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    request = AnalyzeRequest(
        video_url=yt_url,
        video_source_type="youtube",
        prompt="Test YouTube",
    )

    part = await build_video_part(
        client=mock_client,
        provider="vertex_ai",
        request=request,
        media_processing="agentic",
    )
    assert part.file_data is not None
    assert part.file_data.file_uri == yt_url
    assert "AGENTIC" in str(part.media_processing).upper()


@pytest.mark.asyncio
async def test_build_video_part_youtube_developer_api_supported():
    """Verify YouTube URL on Developer API is passed as file_data."""
    mock_client = MagicMock()
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    request = AnalyzeRequest(
        video_url=yt_url,
        video_source_type="youtube",
        prompt="Test YouTube",
        api_key="valid_dev_key",
    )

    part = await build_video_part(
        client=mock_client,
        provider="gemini_api_key",
        request=request,
        media_processing="static",
    )
    assert part.file_data is not None
    assert part.file_data.file_uri == yt_url
    assert part.file_data.mime_type == "video/mp4"


