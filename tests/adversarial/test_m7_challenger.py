"""Milestone M7 Empirical Challenger Test Suite.

Adversarially tests:
1. GCS URI on Gemini Developer API (must return 400).
2. YouTube URL on Vertex AI (must return 400).
3. Non-existent preset ID (must return 404 or raise clean error).
4. Malformed and boundary Range headers on video streaming (416 vs 206).
5. High-concurrency downloads, byte caching, double-checked locking, and live streaming.
6. Multi-provider video payload construction integrity and TTL cache behavior.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.genai import types

from backend.app.config import CredentialsOverride
from backend.app.main import app
from backend.app.schemas.analyze import AnalyzeRequest
from backend.app.schemas.preset import PresetItem
from backend.app.services.preset_service import (
    PRESET_FILENAME,
    PresetService,
    get_preset_service,
    preset_service,
)
from backend.app.services.video_analyzer import (
    GeminiFileUploadCache,
    VideoPayload,
    build_video_part,
    file_upload_cache,
    prepare_video_payload,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ============================================================================
# 1. GCS URI on Gemini Developer API
# ============================================================================


class TestGCSDeveloperApiEdgeCases:
    """Validate GCS URIs behavior on Gemini Developer API."""

    @pytest.mark.asyncio
    async def test_gcs_uri_with_explicit_source_type_raises_400(self):
        """When video_source_type='url' or 'gcs', GCS URI on Dev API returns 400."""
        req = AnalyzeRequest(
            video_url="gs://test-bucket/my-video.mp4",
            video_source_type="url",
            prompt="Describe this video.",
            credentials=CredentialsOverride(api_key="fake-dev-api-key"),
        )
        mock_client = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await prepare_video_payload(
                mock_client,
                provider="gemini_api_key",
                request=req,
                api_key="fake-dev-api-key",
            )
        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        msg = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        assert "Google Cloud Storage URIs (gs://) are only supported on Vertex AI" in msg

    @pytest.mark.asyncio
    async def test_BUG_gcs_uri_without_source_type_silently_falls_back_to_preset(self):
        """EMPIRICAL BUG REPRODUCTION:
        When video_source_type is omitted, AnalyzeRequest defaults to 'preset'.
        prepare_video_payload checks `is_preset` before checking `clean_url.startswith('gs://')`.
        Result: GCS URI is completely ignored and preset video payload is returned instead of HTTP 400!
        """
        req = AnalyzeRequest(
            video_url="gs://test-bucket/my-video.mp4",
            prompt="Describe this video.",
            credentials=CredentialsOverride(api_key="fake-dev-api-key"),
        )
        mock_client = MagicMock()

        # This should raise HTTPException(400), but instead it falls back to preset video upload
        with patch("backend.app.services.video_analyzer._upload_to_files_api", new=AsyncMock(return_value="https://files/preset_uri")):
            payload = await prepare_video_payload(
                mock_client,
                provider="gemini_api_key",
                request=req,
                api_key="fake-dev-api-key",
            )
            # Demonstrates the bug: payload mode is 'file' for the PRESET video, not 400
            assert payload.mode == "file"
            assert payload.file_uri == "https://files/preset_uri"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "gcs_url",
        [
            "gs://my-bucket/deeply/nested/video_001.mp4",
            "gs://bucket-without-path",
            "gs://another-bucket/sub/folder/file.mov",
        ],
    )
    async def test_gcs_uri_variations_raise_400_on_developer_api(self, gcs_url: str):
        """Various GCS URI shapes with source_type='url' must all trigger 400 on Developer API."""
        req = AnalyzeRequest(
            video_url=gcs_url,
            video_source_type="url",
            prompt="Analyze this clip.",
            credentials=CredentialsOverride(api_key="fake-key"),
        )
        mock_client = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await prepare_video_payload(
                mock_client,
                provider="gemini_api_key",
                request=req,
                api_key="fake-key",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_gcs_uri_supported_on_vertex_ai(self):
        """GCS URI on Vertex AI must succeed and construct FileData part."""
        req = AnalyzeRequest(
            video_url="gs://valid-bucket/video.mp4",
            video_source_type="url",
            prompt="Analyze.",
            credentials=CredentialsOverride(project="my-project", location="global"),
        )
        mock_client = MagicMock()

        payload = await prepare_video_payload(
            mock_client,
            provider="vertex_ai",
            request=req,
        )
        assert payload.mode == "file"
        assert payload.file_uri == "gs://valid-bucket/video.mp4"
        assert payload.mime_type == "video/mp4"

        part = payload.to_part("static")
        assert part.file_data is not None
        assert part.file_data.file_uri == "gs://valid-bucket/video.mp4"

    def test_post_analyze_with_gcs_and_dev_api_via_testclient(self, client: TestClient):
        """Integration test: POST /api/analyze with GCS and explicit video_source_type returns 400."""
        payload = {
            "video_url": "gs://test-bucket/video.mp4",
            "video_source_type": "url",
            "prompt": "Summarize.",
            "api_key": "dummy-dev-api-key",
        }
        resp = client.post("/api/analyze", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        error_msg = data.get("detail", {}).get("message", "")
        assert "Google Cloud Storage URIs (gs://) are only supported on Vertex AI" in error_msg


# ============================================================================
# 2. YouTube URL on Vertex AI
# ============================================================================


class TestYouTubeVertexAiEdgeCases:
    """Validate YouTube URLs behavior on Vertex AI endpoints."""

    @pytest.mark.asyncio
    async def test_youtube_url_with_explicit_source_type_raises_400(self):
        """When video_source_type='youtube', YouTube URL on Vertex AI returns 400."""
        req = AnalyzeRequest(
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            video_source_type="youtube",
            prompt="Describe.",
            credentials=CredentialsOverride(project="test-proj", location="global"),
        )
        mock_client = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await prepare_video_payload(
                mock_client,
                provider="vertex_ai",
                request=req,
            )
        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        msg = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        assert "YouTube URLs are not supported on Vertex AI endpoints" in msg

    @pytest.mark.asyncio
    async def test_BUG_youtube_url_without_source_type_silently_falls_back_to_preset(self):
        """EMPIRICAL BUG REPRODUCTION:
        When video_source_type is omitted, AnalyzeRequest defaults to 'preset'.
        prepare_video_payload checks `is_preset` before checking `is_youtube`.
        Result: YouTube URL is completely ignored and preset video payload is returned instead of HTTP 400!
        """
        req = AnalyzeRequest(
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            prompt="Describe.",
            credentials=CredentialsOverride(project="test-proj", location="global"),
        )
        mock_client = MagicMock()

        with patch("backend.app.services.video_analyzer.preset_service.get_cached_video_bytes", new=AsyncMock(return_value=b"PRESET_BYTES")):
            payload = await prepare_video_payload(
                mock_client,
                provider="vertex_ai",
                request=req,
            )
            # Demonstrates the bug: payload mode is 'inline' for the PRESET video, not 400
            assert payload.mode == "inline"
            assert payload.inline_bytes == b"PRESET_BYTES"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "youtube_url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc123def45",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
        ],
    )
    async def test_youtube_url_variations_raise_400_on_vertex_ai(self, youtube_url: str):
        """All variations of YouTube URLs with source_type='youtube' raise 400 on Vertex AI."""
        req = AnalyzeRequest(
            video_url=youtube_url,
            video_source_type="youtube",
            prompt="Describe.",
            credentials=CredentialsOverride(project="test-proj", location="global"),
        )
        mock_client = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await prepare_video_payload(
                mock_client,
                provider="vertex_ai",
                request=req,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_youtube_supported_on_developer_api(self):
        """YouTube URL on Developer API succeeds and builds FileData part."""
        yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        req = AnalyzeRequest(
            video_url=yt_url,
            video_source_type="youtube",
            prompt="Describe.",
            credentials=CredentialsOverride(api_key="valid-key"),
        )
        mock_client = MagicMock()

        payload = await prepare_video_payload(
            mock_client,
            provider="gemini_api_key",
            request=req,
            api_key="valid-key",
        )
        assert payload.mode == "file"
        assert payload.file_uri == yt_url
        assert payload.mime_type is None

        part = payload.to_part("agentic")
        assert part.file_data is not None
        assert part.file_data.file_uri == yt_url

    def test_post_analyze_with_youtube_and_vertex_ai_via_testclient(self, client: TestClient):
        """Integration test: POST /api/analyze with YouTube URL and vertex credentials returns 400."""
        payload = {
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_source_type": "youtube",
            "prompt": "Summarize.",
            "vertex_project": "my-vertex-project",
            "vertex_location": "global",
        }
        resp = client.post("/api/analyze", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        error_msg = data.get("detail", {}).get("message", "")
        assert "YouTube URLs are not supported on Vertex AI endpoints" in error_msg


# ============================================================================
# 3. Non-existent Preset ID and Catalog Integrity
# ============================================================================


class TestPresetCatalogAndNonExistentPreset:
    """Test preset service retrieval, missing IDs, and 404 handling."""

    def test_get_preset_by_id_returns_none_for_missing_ids(self):
        """PresetService.get_preset_by_id must cleanly return None for unknown IDs."""
        service = PresetService()
        assert service.get_preset_by_id("non-existent-preset-999") is None
        assert service.get_preset_by_id("") is None
        assert service.get_preset_by_id("../../etc/passwd") is None
        assert service.get_preset_by_id("null") is None
        assert service.get_preset_by_id("undefined") is None

    def test_get_preset_by_id_returns_expected_presets(self):
        """PresetService returns expected standard presets."""
        service = PresetService()
        p1 = service.get_preset_by_id("io-2026-ucp")
        assert p1 is not None
        assert p1.id == "io-2026-ucp"

        p2 = service.get_preset_by_id("antigravity-locomotive")
        assert p2 is not None
        assert p2.id == "antigravity-locomotive"

    def test_non_existent_preset_endpoints_return_404(self, client: TestClient):
        """All non-existent preset endpoints return clean 404s."""
        endpoints = [
            "/api/preset/non-existent-id",
            "/api/presets/non-existent-id",
            "/api/presets/video/non-existent-id",
            "/api/preset/video/non-existent-id",
            "/api/presets/video/io-2026-ucp",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 404, f"Expected 404 for {ep}, got {resp.status_code}"

    def test_valid_preset_metadata_endpoint(self, client: TestClient):
        """GET /api/preset returns status 200 with presets list."""
        resp = client.get("/api/preset")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) >= 2
        preset_ids = [p["id"] for p in data["presets"]]
        assert "io-2026-ucp" in preset_ids
        assert "antigravity-locomotive" in preset_ids


# ============================================================================
# 4. Malformed and Boundary Range Headers (416 vs 206 vs 200)
# ============================================================================


class TestRangeHeadersEdgeCases:
    """Exhaustive boundary testing of HTTP Range header handling."""

    def test_full_content_without_range_header(self, client: TestClient, tmp_path: Path):
        fake_video = tmp_path / PRESET_FILENAME
        fake_video.write_bytes(b"ABCDEFGHIJ" * 10)  # 100 bytes

        with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
            resp = client.get("/api/preset/video")
            assert resp.status_code == 200
            assert resp.headers["Content-Length"] == "100"
            assert resp.headers["Content-Type"] == "video/mp4"
            assert len(resp.content) == 100

    def test_valid_exact_single_byte_range(self, client: TestClient, tmp_path: Path):
        fake_video = tmp_path / PRESET_FILENAME
        fake_video.write_bytes(b"0123456789")  # 10 bytes: indices 0..9

        with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
            # Byte 0
            resp = client.get("/api/preset/video", headers={"Range": "bytes=0-0"})
            assert resp.status_code == 206
            assert resp.headers["Content-Range"] == "bytes 0-0/10"
            assert resp.headers["Content-Length"] == "1"
            assert resp.content == b"0"

            # Last byte (index 9)
            resp = client.get("/api/preset/video", headers={"Range": "bytes=9-9"})
            assert resp.status_code == 206
            assert resp.headers["Content-Range"] == "bytes 9-9/10"
            assert resp.headers["Content-Length"] == "1"
            assert resp.content == b"9"

    def test_valid_open_ended_range(self, client: TestClient, tmp_path: Path):
        fake_video = tmp_path / PRESET_FILENAME
        fake_video.write_bytes(b"0123456789")  # 10 bytes

        with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
            # From 5 to end
            resp = client.get("/api/preset/video", headers={"Range": "bytes=5-"})
            assert resp.status_code == 206
            assert resp.headers["Content-Range"] == "bytes 5-9/10"
            assert resp.headers["Content-Length"] == "5"
            assert resp.content == b"56789"

            # From 0 to end
            resp2 = client.get("/api/preset/video", headers={"Range": "bytes=0-"})
            assert resp2.status_code == 206
            assert resp2.headers["Content-Range"] == "bytes 0-9/10"
            assert resp2.content == b"0123456789"

    def test_valid_suffix_range(self, client: TestClient, tmp_path: Path):
        fake_video = tmp_path / PRESET_FILENAME
        fake_video.write_bytes(b"0123456789")  # 10 bytes

        with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
            # Last 3 bytes
            resp = client.get("/api/preset/video", headers={"Range": "bytes=-3"})
            assert resp.status_code == 206
            assert resp.headers["Content-Range"] == "bytes 7-9/10"
            assert resp.content == b"789"

            # Suffix larger than file size -> clamps to whole file
            resp2 = client.get("/api/preset/video", headers={"Range": "bytes=-50"})
            assert resp2.status_code == 206
            assert resp2.headers["Content-Range"] == "bytes 0-9/10"
            assert resp2.content == b"0123456789"

    @pytest.mark.parametrize(
        "invalid_range",
        [
            "bytes=10-5",           # start > end
            "bytes=100-200",        # start >= file_size (file_size = 10)
            "bytes=10-10",          # start == file_size (boundary overflow)
            "bytes=0-10",           # end == file_size (boundary overflow, valid is 0-9)
            "bytes=999999999-",     # start >> file_size
            "words=0-5",            # invalid unit
            "characters=0-5",       # invalid unit
            "bytes=abc-def",        # non-numeric
            "bytes=1.5-4.5",        # floating point
            "bytes=10--5",          # negative end
        ],
    )
    def test_invalid_range_headers_return_416(self, client: TestClient, tmp_path: Path, invalid_range: str):
        fake_video = tmp_path / PRESET_FILENAME
        fake_video.write_bytes(b"0123456789")  # 10 bytes

        with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
            resp = client.get("/api/preset/video", headers={"Range": invalid_range})
            assert resp.status_code == 416, f"Expected 416 for '{invalid_range}', got {resp.status_code}"
            if resp.status_code == 416:
                content_range = resp.headers.get("Content-Range", "")
                assert "bytes */10" in content_range or "detail" in resp.json()

    def test_degenerate_range_header_tolerance(self, client: TestClient, tmp_path: Path):
        """Test how router handles degenerate/permissive ranges like 'bytes=', 'bytes=-', 'bytes=--5'."""
        fake_video = tmp_path / PRESET_FILENAME
        fake_video.write_bytes(b"0123456789")  # 10 bytes

        with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
            # Router gracefully parses empty / single dash ranges by defaulting to 0 to file_size-1
            resp1 = client.get("/api/preset/video", headers={"Range": "bytes="})
            assert resp1.status_code in [200, 206, 416]

            resp2 = client.get("/api/preset/video", headers={"Range": "bytes=-"})
            assert resp2.status_code in [200, 206, 416]


# ============================================================================
# 5. Concurrency Stress Testing: Downloads, Caches, & Live Streaming
# ============================================================================


class TestConcurrencyAndLockingStress:
    """Stress test double-checked locking, race conditions, and streaming under concurrency."""

    @pytest.mark.asyncio
    async def test_ensure_video_cached_high_concurrency_single_download(self, tmp_path: Path):
        """50 simultaneous requests when cache is empty must download exactly once."""
        service = PresetService(cache_dir=tmp_path)
        video_file = tmp_path / PRESET_FILENAME
        assert not video_file.exists()

        download_count = 0

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_aiter_bytes(chunk_size=1024):
            nonlocal download_count
            download_count += 1
            # Add artificial latency to provoke race conditions
            await asyncio.sleep(0.05)
            yield b"HIGH_CONCURRENCY_DOWNLOAD_PAYLOAD"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream.return_value = mock_stream_ctx

        with patch("httpx.AsyncClient", return_value=mock_client):
            tasks = [
                asyncio.create_task(service.ensure_video_cached("io-2026-ucp"))
                for _ in range(50)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 50
            assert all(r == video_file for r in results)
            assert video_file.read_bytes() == b"HIGH_CONCURRENCY_DOWNLOAD_PAYLOAD"
            assert download_count == 1, f"Expected exactly 1 download, but observed {download_count}"

    @pytest.mark.asyncio
    async def test_get_cached_video_bytes_high_concurrency(self, tmp_path: Path):
        """50 concurrent callers requesting cached bytes must return identical bytes safely."""
        service = PresetService(cache_dir=tmp_path)
        video_file = tmp_path / PRESET_FILENAME
        expected_bytes = b"TEST_BYTES_CONCURRENT_ACCESS" * 1000
        video_file.write_bytes(expected_bytes)

        tasks = [
            asyncio.create_task(service.get_cached_video_bytes("io-2026-ucp"))
            for _ in range(50)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        assert all(r == expected_bytes for r in results)
        assert service._bytes_cache.get("io-2026-ucp") == expected_bytes

    @pytest.mark.asyncio
    async def test_ensure_url_cached_high_concurrency_single_download(self, tmp_path: Path):
        """30 concurrent callers for the same custom URL must download exactly once."""
        service = PresetService(cache_dir=tmp_path)
        test_url = "https://example.com/unique_video.mp4"

        download_count = 0

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_aiter_bytes(chunk_size=1024):
            nonlocal download_count
            download_count += 1
            await asyncio.sleep(0.03)
            yield b"CUSTOM_URL_BYTES"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream.return_value = mock_stream_ctx

        with patch("httpx.AsyncClient", return_value=mock_client):
            tasks = [
                asyncio.create_task(service.ensure_url_cached(test_url))
                for _ in range(30)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 30
            assert all(r.is_file() for r in results)
            assert results[0].read_bytes() == b"CUSTOM_URL_BYTES"
            assert download_count == 1

    @pytest.mark.asyncio
    async def test_live_server_video_streaming_under_burst_load(self):
        """Hit live running server (127.0.0.1:8000) with 50 concurrent Range requests."""
        live_url = "http://127.0.0.1:8000"
        async with httpx.AsyncClient(base_url=live_url, timeout=15.0) as client:
            try:
                health = await client.get("/api/health")
                if health.status_code != 200:
                    pytest.skip("Live server not reachable")
            except Exception:
                pytest.skip("Live server not reachable")

            ranges = [
                "bytes=0-1023",
                "bytes=1024-2047",
                "bytes=4096-8191",
                "bytes=-1024",
                "bytes=5000-10000",
            ]
            statuses = []

            async def send_range(idx: int):
                r_header = ranges[idx % len(ranges)]
                resp = await client.get("/api/preset/video", headers={"Range": r_header})
                statuses.append(resp.status_code)

            await asyncio.gather(*(send_range(i) for i in range(50)))

            assert len(statuses) == 50
            assert all(s == 206 for s in statuses), f"Failed statuses: {[s for s in statuses if s != 206]}"


# ============================================================================
# 6. Multi-Provider Video Payload Construction & TTL Cache
# ============================================================================


class TestMultiProviderPayloadAndCache:
    """Test GeminiFileUploadCache and provider payload routing."""

    def test_gemini_file_upload_cache_ttl_expiration(self):
        """TTL cache must return None after expiration timestamp."""
        cache = GeminiFileUploadCache(default_ttl_seconds=1.0)
        cache.set("key1", "video1", "uri-123", ttl_seconds=0.05)

        # Immediate fetch
        assert cache.get("key1", "video1") == "uri-123"

        # Different key or identifier
        assert cache.get("key2", "video1") is None
        assert cache.get("key1", "video2") is None

        # Wait for expiration
        time.sleep(0.06)
        assert cache.get("key1", "video1") is None

    def test_gemini_file_upload_cache_clear(self):
        """Clear empties all cached entries."""
        cache = GeminiFileUploadCache()
        cache.set("k", "v", "uri")
        assert cache.get("k", "v") == "uri"
        cache.clear()
        assert cache.get("k", "v") is None

    @pytest.mark.asyncio
    async def test_vertex_ai_preset_uses_inline_blob(self, tmp_path: Path):
        """Vertex AI preset payload uses mode='inline' and inline_data Blob."""
        service = PresetService(cache_dir=tmp_path)
        video_file = tmp_path / PRESET_FILENAME
        video_file.write_bytes(b"VERTEX_INLINE_BYTES")

        req = AnalyzeRequest(
            video_url="/api/preset/video",
            video_source_type="preset",
            prompt="Test prompt",
            credentials=CredentialsOverride(project="proj", location="global"),
        )
        mock_client = MagicMock()

        with patch("backend.app.services.video_analyzer.preset_service", service):
            payload = await prepare_video_payload(mock_client, provider="vertex_ai", request=req)
            assert payload.mode == "inline"
            assert payload.inline_bytes == b"VERTEX_INLINE_BYTES"

            part = payload.to_part("static")
            assert part.inline_data is not None
            assert part.inline_data.data == b"VERTEX_INLINE_BYTES"
            assert part.inline_data.mime_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_gemini_developer_api_preset_uses_files_api_with_caching(self, tmp_path: Path):
        """Developer API preset uploads once and reuses cache on second call."""
        service = PresetService(cache_dir=tmp_path)
        video_file = tmp_path / PRESET_FILENAME
        video_file.write_bytes(b"DEV_API_PRESET_BYTES")

        test_cache = GeminiFileUploadCache()

        req = AnalyzeRequest(
            video_url="/api/preset/video",
            video_source_type="preset",
            prompt="Test prompt",
            credentials=CredentialsOverride(api_key="my-api-key"),
        )

        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_file.uri = "https://generativelanguage.googleapis.com/v1beta/files/file_abc123"
        mock_file.state.name = "ACTIVE"

        mock_upload = AsyncMock(return_value=mock_file)
        mock_client.aio.files.upload = mock_upload

        with patch("backend.app.services.video_analyzer.preset_service", service), \
             patch("backend.app.services.video_analyzer.file_upload_cache", test_cache):

            # First call: triggers upload
            payload1 = await prepare_video_payload(
                mock_client, provider="gemini_api_key", request=req, api_key="my-api-key"
            )
            assert payload1.mode == "file"
            assert payload1.file_uri == "https://generativelanguage.googleapis.com/v1beta/files/file_abc123"
            assert mock_upload.call_count == 1

            # Second call with same key: reuses cache without second upload
            payload2 = await prepare_video_payload(
                mock_client, provider="gemini_api_key", request=req, api_key="my-api-key"
            )
            assert payload2.mode == "file"
            assert payload2.file_uri == "https://generativelanguage.googleapis.com/v1beta/files/file_abc123"
            assert mock_upload.call_count == 1, "Cache hit must prevent second upload"
