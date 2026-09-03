"""Unit tests for PresetService: metadata, disk caching, concurrency, and streaming."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.schemas.preset import PresetItem
from backend.app.services.preset_service import (
    PRESET_FILENAME,
    PresetService,
    get_preset_service,
)


def _create_mock_client(mock_response):
    """Create a mock httpx.AsyncClient supporting async with client and async with client.stream."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client.stream.return_value = mock_stream_ctx
    return mock_client


def test_preset_service_get_preset_by_id():
    service = PresetService()
    p1 = service.get_preset_by_id("pixel-bts-5m")
    assert p1 is not None
    assert p1.id == "pixel-bts-5m"
    assert "Google Pixel" in p1.title

    p2 = service.get_preset_by_id("sustainability-4m")
    assert p2 is not None
    assert p2.id == "sustainability-4m"

    missing = service.get_preset_by_id("non-existent-preset")
    assert missing is None


def test_preset_service_list_presets():
    service = PresetService()
    presets = service.list_presets()
    assert len(presets) >= 2
    assert presets[0].id == "pixel-bts-5m"


def test_preset_service_primary_preset():
    service = PresetService()
    primary = service.get_primary_preset()
    assert primary.id == "pixel-bts-5m"


def test_preset_service_preset_list_response():
    service = PresetService()
    resp = service.get_preset_list_response()
    assert resp.id == "pixel-bts-5m"
    assert len(resp.presets) >= 2
    assert resp.status == "ready"


def test_get_preset_service_singleton():
    s1 = get_preset_service()
    s2 = get_preset_service()
    assert s1 is s2


@pytest.mark.asyncio
async def test_preset_service_ensure_video_cached_existing(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)
    video_file = tmp_path / PRESET_FILENAME
    video_file.write_bytes(b"EXISTING_VIDEO_DATA")

    result = await service.ensure_video_cached("io-2026-ucp")
    assert result == video_file
    assert result.read_bytes() == b"EXISTING_VIDEO_DATA"


@pytest.mark.asyncio
async def test_preset_service_ensure_video_cached_download(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)
    video_file = tmp_path / PRESET_FILENAME
    assert not video_file.exists()

    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_aiter_bytes(chunk_size=1024):
        yield b"CHUNK_1_"
        yield b"CHUNK_2_TEST"

    mock_response.aiter_bytes = mock_aiter_bytes
    mock_client = _create_mock_client(mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await service.ensure_video_cached("io-2026-ucp")
        assert result == video_file
        assert result.read_bytes() == b"CHUNK_1_CHUNK_2_TEST"


@pytest.mark.asyncio
async def test_preset_service_ensure_video_cached_upstream_error(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)

    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_client = _create_mock_client(mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await service.ensure_video_cached("io-2026-ucp")
        assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_preset_service_get_cached_video_bytes(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)
    video_file = tmp_path / PRESET_FILENAME
    video_file.write_bytes(b"BYTES_FOR_INLINE_TEST")

    bytes_data = await service.get_cached_video_bytes("io-2026-ucp")
    assert bytes_data == b"BYTES_FOR_INLINE_TEST"
    # Second call should use in-memory cache
    assert service._bytes_cache.get("io-2026-ucp") == b"BYTES_FOR_INLINE_TEST"
    bytes_data_cached = await service.get_cached_video_bytes("io-2026-ucp")
    assert bytes_data_cached == b"BYTES_FOR_INLINE_TEST"


@pytest.mark.asyncio
async def test_preset_service_ensure_url_cached(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)
    test_url = "https://example.com/videos/sample.mp4"

    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_aiter_bytes(chunk_size=1024):
        yield b"URL_DOWNLOAD_CHUNK"

    mock_response.aiter_bytes = mock_aiter_bytes
    mock_client = _create_mock_client(mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await service.ensure_url_cached(test_url)
        assert result.is_file()
        assert result.read_bytes() == b"URL_DOWNLOAD_CHUNK"


def test_preset_service_stream_video_slice(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)
    test_file = tmp_path / "stream_test.bin"
    test_file.write_bytes(b"0123456789ABCDEF")

    chunks = list(service.stream_video_slice(test_file, start=4, length=6, chunk_size=2))
    assert b"".join(chunks) == b"456789"


@pytest.mark.asyncio
async def test_preset_service_concurrency_locking(tmp_path: Path):
    service = PresetService(cache_dir=tmp_path)
    video_file = tmp_path / PRESET_FILENAME

    download_count = 0

    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_aiter_bytes(chunk_size=1024):
        nonlocal download_count
        download_count += 1
        await asyncio.sleep(0.02)
        yield b"CONCURRENT_BYTES"

    mock_response.aiter_bytes = mock_aiter_bytes
    mock_client = _create_mock_client(mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        tasks = [
            asyncio.create_task(service.ensure_video_cached("io-2026-ucp"))
            for _ in range(8)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r == video_file for r in results)
        assert video_file.read_bytes() == b"CONCURRENT_BYTES"
        assert download_count == 1
