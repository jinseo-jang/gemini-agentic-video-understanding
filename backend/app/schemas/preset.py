"""Pydantic schemas for preset video metadata."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class PresetItem(BaseModel):
    """Metadata item for a preset demo video."""

    id: str
    title: str
    subtitle: str
    size_mb: float
    mime_type: str = "video/mp4"
    duration_seconds: float
    video_url: str
    source_url: Optional[str] = None
    filename: Optional[str] = None
    default_prompt: str


class PresetListResponse(BaseModel):
    """Response containing list of presets and flat metadata for the primary preset."""

    presets: List[PresetItem] = Field(default_factory=list)

    # Flat aliases for primary preset (ensures compatibility with both contract variants)
    id: Optional[str] = None
    title: Optional[str] = None
    filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    size_bytes: Optional[int] = None
    size_formatted: Optional[str] = None
    mime_type: Optional[str] = None
    media_url: Optional[str] = None
    source_url: Optional[str] = None
    default_prompt: Optional[str] = None
    status: Optional[str] = "ready"
