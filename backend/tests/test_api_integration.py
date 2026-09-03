"""Integration tests for FastAPI application endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


def test_post_analyze_success_contract(client: TestClient, dummy_static_response, dummy_agentic_response):
    """Verify POST /api/analyze matches PROJECT.md contract exactly."""
    async def mock_generate(model, contents, config):
        part = contents[0]
        proc = str(getattr(part, "media_processing", "")).upper()
        if "STATIC" in proc:
            return dummy_static_response
        return dummy_agentic_response

    mock_client = AsyncMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=mock_generate)

    with patch("backend.app.services.video_analyzer.get_genai_client", return_value=mock_client):
        payload = {
            "video_url": "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4",
            "video_source_type": "preset",
            "prompt": "What is the third logo in the second row of the Universal Commerce Protocol (UCP) partners slide?",
            "credentials": {
                "api_key": "test_key",
            },
        }

        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Contract assertion
        assert "baseline" in data
        assert "agentic" in data
        assert "savings" in data

        # Baseline fields
        baseline = data["baseline"]
        assert baseline["model"] == "gemini-3.7-flash"
        assert baseline["media_processing"] == "static"
        assert "Partner X" in baseline["text"]
        assert "tokens" in baseline
        assert baseline["tokens"]["prompt"] == 120000
        assert baseline["tokens"]["candidates"] == 60

        # Agentic fields
        agentic = data["agentic"]
        assert agentic["model"] == "gemini-3.7-flash"
        assert agentic["media_processing"] == "agentic"
        assert agentic["tokens"]["prompt"] == 4800
        assert agentic["tokens"]["thoughts"] == 85000

        # Savings fields
        savings = data["savings"]
        assert savings["total_reduction_percent"] > 0
        assert savings["input_reduction_percent"] == 96.0
        assert savings["prompt_tokens_saved"] == 115200


def test_post_analyze_missing_credentials(client: TestClient):
    """Verify POST /api/analyze returns 400 with actionable setup instructions when unconfigured."""
    with patch("backend.app.services.video_analyzer.settings.resolve_credentials") as mock_resolve:
        from backend.app.config import ResolvedCredentials

        mock_resolve.return_value = ResolvedCredentials(provider="none", is_valid=False)

        payload = {
            "video_url": "/api/preset/video",
            "prompt": "Analyze this video",
        }

        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"] == "credentials_missing"
        assert "instructions" in data["detail"]


def test_post_analyze_validation_error(client: TestClient):
    """Verify POST /api/analyze returns 422 if prompt is missing."""
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422


def test_root_serves_spa(client: TestClient):
    """Verify root / serves index.html when frontend dist is present."""
    response = client.get("/")
    assert response.status_code == 200
    assert "<!doctype html>" in response.text.lower() or "root" in response.text.lower()


def test_root_fallback_when_dist_absent(client: TestClient, tmp_path):
    """Verify root / returns 200 with informative JSON when dist is absent."""
    non_existent = tmp_path / "non_existent_dist"
    with patch("backend.app.main.FRONTEND_DIST", non_existent):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "/api/health" in data["health_check"]


def test_post_analyze_custom_thinking_level(client: TestClient, dummy_static_response, dummy_agentic_response):
    """Verify POST /api/analyze accepts thinking_level and propagates it to results."""
    mock_client = AsyncMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=dummy_agentic_response)

    with patch("backend.app.services.video_analyzer.get_genai_client", return_value=mock_client):
        payload = {
            "video_url": "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4",
            "video_source_type": "preset",
            "prompt": "Test prompt",
            "thinking_level": "low",
            "credentials": {"api_key": "test_key"},
        }

        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["baseline"]["thinking_level"] == "low"
        assert data["agentic"]["thinking_level"] == "low"
