"""Settings and health check router."""

from __future__ import annotations

from fastapi import APIRouter
from backend.app.config import settings
from backend.app.schemas.settings import HealthResponse, SettingsResponse

router = APIRouter(tags=["System & Settings"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check endpoint."""
    return HealthResponse(status="ok", version="1.0.0")


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Return active provider and credential status."""
    resolved = settings.resolve_credentials()
    has_api_key = settings.has_gemini_api_key()
    vertex_project = settings.get_vertex_project()
    has_vertex = bool(vertex_project)

    active_provider = resolved.provider
    active_mode = "unconfigured"
    if active_provider == "gemini_api_key":
        active_mode = "api_key"
    elif active_provider == "vertex_ai":
        active_mode = "vertex"

    masked_key = None
    if has_api_key:
        raw_key = settings.get_gemini_api_key() or ""
        if len(raw_key) > 8:
            masked_key = f"{raw_key[:4]}...{raw_key[-4:]}"
        else:
            masked_key = "********"

    return SettingsResponse(
        active_provider=active_provider,
        has_gemini_api_key=has_api_key,
        has_vertex_project=has_vertex,
        vertex_project=vertex_project,
        vertex_location=settings.get_vertex_location(),
        active_mode=active_mode,
        gemini_api_key_configured=has_api_key,
        gemini_api_key_masked=masked_key,
        adc_available=settings.has_adc(),
    )
