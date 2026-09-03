"""Unit tests for settings and health endpoints."""

from __future__ import annotations

from unittest.mock import patch
from fastapi.testclient import TestClient


def test_api_health(client: TestClient):
    """Verify /api/health returns status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_root_health(client: TestClient):
    """Verify root /health endpoint alias returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_get_settings_gemini_key_active(client: TestClient, monkeypatch):
    """Verify /api/settings reports gemini_api_key when API key is set."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_test_1234567890")
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()

    assert data["active_provider"] == "gemini_api_key"
    assert data["has_gemini_api_key"] is True
    assert "AIza" in data["gemini_api_key_masked"]


def test_get_settings_vertex_active(client: TestClient, monkeypatch):
    """Verify /api/settings reports vertex_ai when vertex project is configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-vertex-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()

    assert data["active_provider"] == "vertex_ai"
    assert data["has_vertex_project"] is True
    assert data["vertex_project"] == "test-vertex-project"
    assert data["vertex_location"] == "global"


def test_get_settings_default_vertex_location_is_global(client: TestClient, monkeypatch):
    """Verify /api/settings returns vertex_location 'global' by default."""
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("VERTEX_LOCATION", raising=False)

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["vertex_location"] == "global"

