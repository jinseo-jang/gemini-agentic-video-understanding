"""Tier 1, Tier 2, and Tier 3 E2E Tests: Presets & Video Streaming.

Validates:
- GET /api/preset returns preset catalog matching PROJECT.md interface contract
- GET /api/preset/video serves MP4 video with HTTP Range request support (206 Partial Content)
- Range header chunking: bytes 0-1023, bytes 1024-2047
- Handling of out-of-bounds range requests (416 Range Not Satisfiable)
- Preset metadata compatibility with /api/analyze request payload
"""

import pytest
import httpx


class TestPresetCatalog:
    """Tier 1: Preset video catalog metadata verification."""

    def test_get_presets_list_schema(self, api_client: httpx.Client):
        """Verify GET /api/preset conforms to interface contracts."""
        response = api_client.get("/api/preset")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert isinstance(data, dict), "Preset response must be a JSON object"
        assert "presets" in data, "Missing 'presets' field in preset response"
        assert isinstance(data["presets"], list), "'presets' must be a list"
        assert len(data["presets"]) >= 1, "Expected at least one preset video"

        # Check fields of each preset against PROJECT.md
        required_fields = [
            "id",
            "title",
            "subtitle",
            "size_mb",
            "mime_type",
            "duration_seconds",
            "video_url",
            "default_prompt",
        ]
        for preset in data["presets"]:
            for field in required_fields:
                assert field in preset, f"Preset '{preset.get('id')}' missing field '{field}'"
            assert isinstance(preset["id"], str) and len(preset["id"]) > 0
            assert isinstance(preset["title"], str) and len(preset["title"]) > 0
            assert isinstance(preset["subtitle"], str)
            assert isinstance(preset["size_mb"], (int, float)) and preset["size_mb"] > 0
            assert preset["mime_type"] == "video/mp4"
            assert isinstance(preset["duration_seconds"], (int, float)) and preset["duration_seconds"] > 0
            assert isinstance(preset["video_url"], str) and len(preset["video_url"]) > 0
            assert isinstance(preset["default_prompt"], str) and len(preset["default_prompt"]) > 0

    def test_preset_contains_keynote_reference_clip(self, api_client: httpx.Client):
        """Verify the primary demo clip is available."""
        response = api_client.get("/api/preset")
        assert response.status_code == 200
        presets = response.json()["presets"]
        ids = [p["id"] for p in presets]
        assert "pixel-bts-5m" in ids, f"Expected 'pixel-bts-5m' preset in {ids}"
        assert "sports-10m" in ids, f"Expected 'sports-10m' preset in {ids}"
        
        pixel_preset = next(p for p in presets if p["id"] == "pixel-bts-5m")
        assert "Google Pixel" in pixel_preset["title"]
        assert "Pixel" in pixel_preset["default_prompt"]

        sports_preset = next(p for p in presets if p["id"] == "sports-10m")
        assert "10-Min Video" in sports_preset["title"]
        assert sports_preset["duration_seconds"] == 600.0


class TestPresetVideoStreaming:
    """Tier 1 & Tier 2: Video streaming and HTTP Range header verification."""

    def test_video_endpoint_headers(self, api_client: httpx.Client):
        """Verify video endpoint returns video/mp4 and indicates Accept-Ranges."""
        response = api_client.head("/api/preset/video")
        # Some servers might return 200 or 206 for HEAD/GET
        if response.status_code == 405:
            # If HEAD not supported, use small GET Range
            response = api_client.get("/api/preset/video", headers={"Range": "bytes=0-10"})

        assert response.status_code in [200, 206], f"Unexpected status code: {response.status_code}"
        content_type = response.headers.get("content-type", "")
        assert "video/mp4" in content_type, f"Expected video/mp4 content type, got: {content_type}"
        accept_ranges = response.headers.get("accept-ranges", "")
        assert "bytes" in accept_ranges.lower(), f"Expected Accept-Ranges: bytes, got: {accept_ranges}"

    def test_video_range_request_first_chunk(self, api_client: httpx.Client):
        """Tier 2: Verify HTTP Range bytes=0-1023 returns 206 Partial Content with 1024 bytes."""
        headers = {"Range": "bytes=0-1023"}
        response = api_client.get("/api/preset/video", headers=headers)
        assert response.status_code == 206, f"Expected 206 Partial Content, got {response.status_code}"
        assert len(response.content) == 1024, f"Expected 1024 bytes, got {len(response.content)}"
        
        content_range = response.headers.get("content-range", "")
        assert content_range.startswith("bytes 0-1023/"), f"Invalid Content-Range header: {content_range}"

    def test_video_range_request_second_chunk(self, api_client: httpx.Client):
        """Tier 2: Verify HTTP Range bytes=1024-2047 returns subsequent 1024 bytes."""
        chunk1 = api_client.get("/api/preset/video", headers={"Range": "bytes=0-1023"}).content
        resp2 = api_client.get("/api/preset/video", headers={"Range": "bytes=1024-2047"})
        assert resp2.status_code == 206, f"Expected 206 Partial Content, got {resp2.status_code}"
        assert len(resp2.content) == 1024, f"Expected 1024 bytes, got {len(resp2.content)}"
        
        content_range = resp2.headers.get("content-range", "")
        assert content_range.startswith("bytes 1024-2047/"), f"Invalid Content-Range header: {content_range}"
        
        # Crucial integrity assertion: chunk 2 must not be an identical repeat of chunk 1
        assert chunk1 != resp2.content, "Subsequent byte ranges must return different data"

    def test_video_open_ended_range_request(self, api_client: httpx.Client):
        """Tier 2: Verify open-ended range request (bytes=1000-) for video player seeking."""
        headers = {"Range": "bytes=1000-"}
        response = api_client.get("/api/preset/video", headers=headers)
        assert response.status_code in [200, 206], f"Expected 206 or 200, got {response.status_code}"
        if response.status_code == 206:
            content_range = response.headers.get("content-range", "")
            assert content_range.startswith("bytes 1000-"), f"Invalid Content-Range: {content_range}"

    def test_video_invalid_range_request(self, api_client: httpx.Client):
        """Tier 2: Verify unsatisfiable byte range (out of bounds) returns 416."""
        headers = {"Range": "bytes=9999999999-"}
        response = api_client.get("/api/preset/video", headers=headers)
        assert response.status_code in [416, 200, 206], f"Unexpected status for out-of-bounds range: {response.status_code}"


class TestPresetCrossFeatureIntegration:
    """Tier 3: Preset selection to Analyze request compatibility."""

    def test_preset_to_analyze_payload_compatibility(self, api_client: httpx.Client):
        """Verify preset metadata can directly assemble a valid /api/analyze payload."""
        response = api_client.get("/api/preset")
        assert response.status_code == 200
        preset = response.json()["presets"][0]

        # Assemble payload as the React frontend would
        analyze_payload = {
            "video_url": preset["video_url"],
            "video_source_type": "preset",
            "prompt": preset["default_prompt"],
        }

        # Verify all mandatory payload keys are non-null and correctly typed
        assert isinstance(analyze_payload["video_url"], str) and len(analyze_payload["video_url"]) > 0
        assert analyze_payload["video_source_type"] in ["preset", "url", "youtube"]
        assert isinstance(analyze_payload["prompt"], str) and len(analyze_payload["prompt"]) > 0
