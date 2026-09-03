"""Preset metadata and video streaming router with HTTP Range support."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from backend.app.schemas.preset import PresetListResponse
from backend.app.services.preset_service import (
    DEFAULT_DURATION,
    DEFAULT_PRESETS,
    DEFAULT_SIZE_BYTES,
    DEFAULT_SIZE_MB,
    PRESET_FILENAME,
    PRESETS,
    REFERENCE_VIDEO_URL,
    PresetService,
    get_preset_service,
    preset_service,
)

router = APIRouter(tags=["Presets"])


# Module-level references for 100% backward compatibility with unit tests
ensure_video_cached = preset_service.ensure_video_cached
get_cached_video_path = preset_service.get_cached_video_path
file_iterator = preset_service.stream_video_slice


@router.get("/preset", response_model=PresetListResponse)
async def get_presets(
    service: PresetService = Depends(get_preset_service),
) -> PresetListResponse:
    """Return available preset demo videos and default prompts."""
    return service.get_preset_list_response()


@router.get("/preset/video")
async def stream_preset_video(
    request: Request,
    preset_id: Optional[str] = None,
    range: Optional[str] = Header(None, alias="Range"),
    service: PresetService = Depends(get_preset_service),
):
    """Stream reference video supporting HTTP 206 Partial Content (Range requests)."""
    # If module-level ensure_video_cached was monkey-patched (e.g. in unit tests),
    # honor the patched function; otherwise delegate to injected service.
    if ensure_video_cached is not preset_service.ensure_video_cached:
        try:
            video_path = await ensure_video_cached(preset_id)
        except TypeError:
            video_path = await ensure_video_cached()
    else:
        video_path = await service.ensure_video_cached(preset_id)

    file_size = video_path.stat().st_size

    if not range:
        # Full content response (HTTP 200 OK)
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
        }
        return StreamingResponse(
            service.stream_video_slice(video_path, 0, file_size),
            status_code=status.HTTP_200_OK,
            headers=headers,
        )

    # Parse Range: bytes=start-end
    range_str = range.strip()
    if not range_str.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid Range header format")

    byte_range = range_str[6:].strip()
    parts = byte_range.split("-")
    try:
        start_str = parts[0].strip()
        end_str = parts[1].strip() if len(parts) > 1 else ""

        if not start_str and end_str:
            # Suffix byte range: bytes=-500 (last 500 bytes)
            suffix_len = int(end_str)
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        content_length = (end - start) + 1
        headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
        }

        return StreamingResponse(
            service.stream_video_slice(video_path, start, content_length),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers=headers,
        )

    except ValueError:
        raise HTTPException(status_code=416, detail="Invalid Range byte boundaries")
