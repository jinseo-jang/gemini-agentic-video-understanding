"""FastAPI router modules."""

from backend.app.routers.analyze import router as analyze_router
from backend.app.routers.preset import router as preset_router
from backend.app.routers.settings import router as settings_router

__all__ = ["analyze_router", "preset_router", "settings_router"]
