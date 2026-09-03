"""Pydantic schemas for application settings and health endpoints."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    """Response containing current credential status and active provider."""

    active_provider: str = Field(
        ...,
        description="Active provider type: 'gemini_api_key' | 'vertex_ai' | 'none'",
    )
    has_gemini_api_key: bool = Field(
        ...,
        description="Whether a Gemini API key is configured.",
    )
    has_vertex_project: bool = Field(
        ...,
        description="Whether a Vertex AI project ID is configured.",
    )
    vertex_project: Optional[str] = Field(
        default=None,
        description="Configured Vertex AI project ID.",
    )
    vertex_location: Optional[str] = Field(
        default=None,
        description="Configured Vertex AI location.",
    )

    # Convenience aliases for frontend compatibility
    active_mode: Optional[str] = None
    gemini_api_key_configured: Optional[bool] = None
    gemini_api_key_masked: Optional[str] = None
    adc_available: Optional[bool] = None


class HealthResponse(BaseModel):
    """Status check response."""

    status: str = Field(default="ok", description="Service health status.")
    version: str = Field(default="1.0.0", description="Service version.")
