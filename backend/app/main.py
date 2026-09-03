"""FastAPI application entry point.

Configures CORS, registers API routers for analysis, presets, and settings,
and mounts compiled frontend static assets from frontend/dist with SPA fallback routing.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routers.analyze import router as analyze_router
from backend.app.routers.preset import router as preset_router
from backend.app.routers.settings import router as settings_router
from backend.app.schemas.settings import HealthResponse

app = FastAPI(
    title="Gemini 3.7 Flash Video Benchmark API",
    description="Side-by-side benchmark comparing Static vs Agentic Video Understanding",
    version="1.0.0",
)

# Enable CORS for all origins during development and production serving
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes under /api
app.include_router(settings_router, prefix="/api")
app.include_router(preset_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")


# Also provide direct /health alias
@app.get("/health", response_model=HealthResponse, tags=["System & Settings"])
async def root_health() -> HealthResponse:
    """Direct root health endpoint alias."""
    return HealthResponse(status="ok", version="1.0.0")


# Frontend static distribution path
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"

if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_or_static(full_path: str):
    """Serve frontend static assets or return index.html for SPA routing."""
    # Never intercept API requests
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="API endpoint not found")

    # Serve existing file from dist
    if FRONTEND_DIST.is_dir():
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))

        index_file = FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))

    # Friendly informational payload when frontend is not yet built
    return JSONResponse(
        content={
            "service": "Gemini 3.7 Flash Video Benchmark API",
            "status": "online",
            "health_check": "/api/health",
            "presets": "/api/preset",
            "settings": "/api/settings",
            "docs": "/docs",
            "frontend": "frontend/dist not yet compiled. Run 'npm run build' in frontend directory.",
        },
        status_code=200,
    )
