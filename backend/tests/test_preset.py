"""Unit tests for preset video metadata and HTTP Range streaming endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def test_get_presets(client: TestClient):
    """Verify /api/preset returns preset demo metadata matching contract."""
    response = client.get("/api/preset")
    assert response.status_code == 200
    data = response.json()

    assert "presets" in data
    assert len(data["presets"]) >= 3

    preset_ids = [p["id"] for p in data["presets"]]
    assert "sports-10m" in preset_ids

    sports_preset = next(p for p in data["presets"] if p["id"] == "sports-10m")
    assert "10-Min Video" in sports_preset["title"]
    assert sports_preset["duration_seconds"] == 600.0
    assert sports_preset["video_url"] == "/api/preset/video?preset_id=sports-10m"
    assert sports_preset["mime_type"] == "video/mp4"

    first_preset = data["presets"][0]
    assert first_preset["id"] == "pixel-bts-5m"
    assert "Google Pixel" in first_preset["title"]
    assert first_preset["video_url"] == "/api/preset/video?preset_id=pixel-bts-5m"
    assert first_preset["mime_type"] == "video/mp4"

    # Verify flat compatibility properties
    assert data["id"] == "pixel-bts-5m"
    assert data["status"] == "ready"


def test_stream_preset_video_sports_10m(client: TestClient, tmp_path: Path):
    """Verify streaming with preset_id=sports-10m passes correct preset to service."""
    fake_video = tmp_path / "sports_match_10m.mp4"
    fake_video.write_bytes(b"SPORTS_MATCH_10M_MOCK_STREAM_BYTES")

    with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)) as mock_ensure:
        response = client.get("/api/preset/video?preset_id=sports-10m", headers={"Range": "bytes=0-15"})
        assert response.status_code == 206
        assert response.content == b"SPORTS_MATCH_10M"
        mock_ensure.assert_awaited_once_with("sports-10m")


def test_stream_preset_video_full_content(client: TestClient, tmp_path: Path):
    """Verify /api/preset/video returns 200 OK without Range header."""
    fake_video = tmp_path / "KW_SxS-needle_Blog_V1.mp4"
    fake_video.write_bytes(b"VIDEO_HEADER_DATA_1234567890_TAIL")

    with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
        response = client.get("/api/preset/video")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "video/mp4"
        assert response.headers["Accept-Ranges"] == "bytes"
        assert response.content == b"VIDEO_HEADER_DATA_1234567890_TAIL"


def test_stream_preset_video_range_request(client: TestClient, tmp_path: Path):
    """Verify /api/preset/video returns 206 Partial Content with valid byte range."""
    raw_data = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    fake_video = tmp_path / "KW_SxS-needle_Blog_V1.mp4"
    fake_video.write_bytes(raw_data)
    total_len = len(raw_data)

    with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
        # Request bytes 0-9
        response = client.get("/api/preset/video", headers={"Range": "bytes=0-9"})
        assert response.status_code == 206
        assert response.headers["Content-Range"] == f"bytes 0-9/{total_len}"
        assert response.headers["Content-Length"] == "10"
        assert response.content == b"0123456789"

        # Request bytes 10-
        response = client.get("/api/preset/video", headers={"Range": "bytes=10-"})
        assert response.status_code == 206
        assert response.headers["Content-Range"] == f"bytes 10-{total_len - 1}/{total_len}"
        assert response.content == raw_data[10:]


def test_stream_preset_video_invalid_range(client: TestClient, tmp_path: Path):
    """Verify /api/preset/video returns 416 when requested range is out of bounds."""
    raw_data = b"SHORT_VIDEO"
    fake_video = tmp_path / "KW_SxS-needle_Blog_V1.mp4"
    fake_video.write_bytes(raw_data)

    with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
        response = client.get("/api/preset/video", headers={"Range": "bytes=100-200"})
        assert response.status_code == 416
        assert "bytes */11" in response.headers.get("Content-Range", "")


def test_stream_preset_video_suffix_range(client: TestClient, tmp_path: Path):
    """Verify /api/preset/video supports suffix range bytes=-N."""
    raw_data = b"0123456789"
    fake_video = tmp_path / "KW_SxS-needle_Blog_V1.mp4"
    fake_video.write_bytes(raw_data)

    with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
        response = client.get("/api/preset/video", headers={"Range": "bytes=-4"})
        assert response.status_code == 206
        assert response.headers["Content-Range"] == "bytes 6-9/10"
        assert response.content == b"6789"


def test_stream_preset_video_malformed_ranges(client: TestClient, tmp_path: Path):
    """Verify /api/preset/video rejects malformed Range headers."""
    fake_video = tmp_path / "KW_SxS-needle_Blog_V1.mp4"
    fake_video.write_bytes(b"DATA")

    with patch("backend.app.routers.preset.ensure_video_cached", new=AsyncMock(return_value=fake_video)):
        # Missing bytes= prefix
        res1 = client.get("/api/preset/video", headers={"Range": "words=0-2"})
        assert res1.status_code == 416

        # Non-numeric bounds
        res2 = client.get("/api/preset/video", headers={"Range": "bytes=abc-def"})
        assert res2.status_code == 416


@pytest.mark.asyncio
async def test_ensure_video_cached_existing_file():
    """Verify ensure_video_cached returns existing cached file immediately."""
    from backend.app.routers.preset import ensure_video_cached
    path = await ensure_video_cached()
    assert path.is_file()
    assert path.stat().st_size > 0
