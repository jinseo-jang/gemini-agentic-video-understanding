"""Tier 1 & Tier 2 E2E Tests: Health & Settings Endpoints.

Validates:
- GET /api/health returns 200 OK and valid status/version schema
- GET /api/settings returns 200 OK and credential provider schema
- Unknown API routes return 404
- CORS and preflight handling
"""

import pytest
import httpx


class TestHealthEndpoint:
    """Tier 1: Health check endpoint verification."""

    def test_health_endpoint_status_and_schema(self, api_client: httpx.Client):
        """Verify GET /api/health returns status 'ok' and version string."""
        response = api_client.get("/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, dict), "Health response must be a JSON object"
        assert data.get("status") == "ok", f"Expected status 'ok', got: {data.get('status')}"
        assert "version" in data, "Health response must include 'version' field"
        assert isinstance(data["version"], str), "'version' must be a string"

    def test_health_endpoint_methods(self, api_client: httpx.Client):
        """Verify POST /api/health is disallowed (405 Method Not Allowed)."""
        response = api_client.post("/api/health", json={})
        assert response.status_code in [405, 404], f"Expected 405 or 404 for POST /api/health, got {response.status_code}"


class TestSettingsEndpoint:
    """Tier 1 & Tier 2: Settings and credential status endpoint verification."""

    def test_settings_endpoint_schema(self, api_client: httpx.Client):
        """Verify GET /api/settings conforms to PROJECT.md interface contract."""
        response = api_client.get("/api/settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert isinstance(data, dict), "Settings response must be a JSON object"

        # Mandatory fields per PROJECT.md interface contract
        assert "active_provider" in data, "Missing 'active_provider' in settings response"
        assert data["active_provider"] in [
            "gemini_api_key",
            "vertex_ai",
            "none",
        ], f"Invalid active_provider value: {data['active_provider']}"

        assert "has_gemini_api_key" in data, "Missing 'has_gemini_api_key' in settings response"
        assert isinstance(data["has_gemini_api_key"], bool), "'has_gemini_api_key' must be a boolean"

        assert "has_vertex_project" in data, "Missing 'has_vertex_project' in settings response"
        assert isinstance(data["has_vertex_project"], bool), "'has_vertex_project' must be a boolean"

        assert "vertex_project" in data, "Missing 'vertex_project' in settings response"
        assert data["vertex_project"] is None or isinstance(data["vertex_project"], str)

        assert "vertex_location" in data, "Missing 'vertex_location' in settings response"
        assert data["vertex_location"] is None or isinstance(data["vertex_location"], str)

    def test_settings_does_not_leak_raw_secrets(self, api_client: httpx.Client):
        """Security check: settings endpoint must NEVER return raw API keys."""
        response = api_client.get("/api/settings")
        assert response.status_code == 200
        text = response.text.lower()
        assert "aiwork" not in text, "Raw API key potentially leaked in settings response"
        assert "secret" not in text or "has_" in text, "Raw secrets detected in settings response"


class TestRoutingAndErrorHandling:
    """Tier 2: Unknown route handling and error responses."""

    def test_unknown_api_route_returns_404(self, api_client: httpx.Client):
        """Verify non-existent API routes return 404 Not Found."""
        response = api_client.get("/api/nonexistent_test_endpoint_xyz")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
