"""Pytest fixtures and configuration for E2E tests."""

import os
import sys
from pathlib import Path
from typing import Generator
import pytest
import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8000")


def check_live_server(url: str) -> bool:
    """Check if the backend server is running and responding to health check."""
    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(f"{url.rstrip('/')}/api/health")
            return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def is_live_server() -> bool:
    """Returns True if a live server is running on DEFAULT_BASE_URL."""
    return check_live_server(DEFAULT_BASE_URL)


@pytest.fixture(scope="session")
def base_url(is_live_server: bool) -> str:
    """Return the active base URL."""
    if is_live_server:
        return DEFAULT_BASE_URL
    return "http://testserver"


@pytest.fixture(scope="session")
def api_client(is_live_server: bool) -> Generator[httpx.Client, None, None]:
    """Provide an HTTP client connected to either live server or ASGI app."""
    if is_live_server:
        with httpx.Client(base_url=DEFAULT_BASE_URL, timeout=60.0) as client:
            yield client
    else:
        # Attempt to import backend FastAPI app for in-process testing
        try:
            from starlette.testclient import TestClient
            from backend.app.main import app
            with TestClient(app, base_url="http://testserver") as client:
                yield client
        except ImportError as exc:
            pytest.fail(
                f"Live server not responding at {DEFAULT_BASE_URL} and backend app could not be imported: {exc}"
            )

