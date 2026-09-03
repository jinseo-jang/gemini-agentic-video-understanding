"""Adversarial and Empirical Stress Test Suite for Backend Location & Credential Resolution.

Tests:
1. Environment Variable Precedence (GOOGLE_CLOUD_LOCATION vs VERTEX_LOCATION vs default 'global')
2. Request Body Overrides vs Environment Variables (nested credentials, top-level fields, API key vs Vertex)
3. Empty String and Whitespace Fallbacks to 'global' (strip logic, falsy fallbacks)
4. GenAI Client Instantiation Parameters under Corner Cases (v1beta1 api_version, vertexai flag, project, location)
5. 1000-Iteration Differential Fuzzing against Formal Precedence Oracle
6. FastAPI Live Endpoints (/api/settings and /api/analyze) under Location Stress Payloads
"""

from __future__ import annotations

import os
import random
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.config import CredentialsOverride, ResolvedCredentials, Settings
from backend.app.main import app
from backend.app.schemas.analyze import AnalyzeRequest
from backend.app.services.genai_client import (
    CredentialsMissingError,
    create_genai_client,
    get_genai_client,
)


# ============================================================================
# Section 1: Environment Variable Precedence
# ============================================================================

class TestEnvVarPrecedence:
    """Stress-test environment variable precedence and resolution hierarchy."""

    def test_default_when_all_unset(self, monkeypatch):
        """When neither GOOGLE_CLOUD_LOCATION nor VERTEX_LOCATION is set, defaults to 'global'."""
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)
        s = Settings()
        assert s.get_vertex_location() == "global"

    def test_google_cloud_location_only(self, monkeypatch):
        """GOOGLE_CLOUD_LOCATION is used when set alone."""
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)
        s = Settings()
        assert s.get_vertex_location() == "us-central1"

    def test_vertex_location_only(self, monkeypatch):
        """VERTEX_LOCATION is used when GOOGLE_CLOUD_LOCATION is unset."""
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.setenv("VERTEX_LOCATION", "europe-west4")
        s = Settings()
        assert s.get_vertex_location() == "europe-west4"

    def test_google_cloud_location_precedes_vertex_location(self, monkeypatch):
        """GOOGLE_CLOUD_LOCATION takes precedence over VERTEX_LOCATION when both set."""
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-east4")
        monkeypatch.setenv("VERTEX_LOCATION", "europe-west1")
        s = Settings()
        assert s.get_vertex_location() == "us-east4"

    def test_empty_google_cloud_location_falls_back_to_vertex_location(self, monkeypatch):
        """Empty string in GOOGLE_CLOUD_LOCATION falls back to VERTEX_LOCATION."""
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "")
        monkeypatch.setenv("VERTEX_LOCATION", "asia-northeast1")
        s = Settings()
        assert s.get_vertex_location() == "asia-northeast1"

    def test_empty_both_env_vars_falls_back_to_global(self, monkeypatch):
        """Both env vars set to empty string fall back to 'global'."""
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "")
        monkeypatch.setenv("VERTEX_LOCATION", "")
        s = Settings()
        assert s.get_vertex_location() == "global"

    def test_custom_settings_default_location(self, monkeypatch):
        """Settings instance with custom default respects that default when env unset."""
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)
        s = Settings(default_vertex_location="australia-southeast1")
        assert s.get_vertex_location() == "australia-southeast1"

    def test_ambient_vertex_resolution_respects_env_precedence(self, monkeypatch):
        """ResolvedCredentials correctly receives the precedence location."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-proj-001")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west3")
        monkeypatch.setenv("VERTEX_LOCATION", "us-central1")

        s = Settings()
        resolved = s.resolve_credentials(None)
        assert resolved.provider == "vertex_ai"
        assert resolved.vertex_project == "test-proj-001"
        assert resolved.vertex_location == "europe-west3"


# ============================================================================
# Section 2: Request Body Overrides vs Environment Variables
# ============================================================================

class TestRequestBodyOverrides:
    """Stress-test per-request overrides against ambient environment configuration."""

    def test_request_vertex_location_overrides_env_location(self, monkeypatch):
        """Request location override takes precedence over GOOGLE_CLOUD_LOCATION and default."""
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        monkeypatch.setenv("VERTEX_LOCATION", "europe-west4")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")

        s = Settings()
        override = CredentialsOverride(
            project="override-project",
            location="asia-east1",
        )
        resolved = s.resolve_credentials(override)
        assert resolved.provider == "vertex_ai"
        assert resolved.vertex_project == "override-project"
        assert resolved.vertex_location == "asia-east1"

    def test_request_api_key_overrides_ambient_vertex(self, monkeypatch):
        """API key in request override switches provider to gemini_api_key regardless of vertex env."""
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")

        s = Settings()
        override = CredentialsOverride(
            api_key="AIzaOverrideKey123",
            project="override-project",  # Ignored because api_key takes priority 1
            location="us-central1",
        )
        resolved = s.resolve_credentials(override)
        assert resolved.provider == "gemini_api_key"
        assert resolved.api_key == "AIzaOverrideKey123"

    def test_request_vertex_overrides_ambient_api_key(self, monkeypatch):
        """Vertex project in request override takes priority over ambient GEMINI_API_KEY (Priority 2 vs 3)."""
        monkeypatch.setenv("GEMINI_API_KEY", "ambient_gemini_key")
        s = Settings()
        override = CredentialsOverride(
            project="request-vertex-proj",
            location="europe-west1",
        )
        resolved = s.resolve_credentials(override)
        assert resolved.provider == "vertex_ai"
        assert resolved.vertex_project == "request-vertex-proj"
        assert resolved.vertex_location == "europe-west1"

    def test_analyze_request_top_level_and_nested_credentials(self):
        """AnalyzeRequest correctly extracts effective credentials from nested and top-level."""
        # Case A: Top-level only
        req1 = AnalyzeRequest(
            prompt="test",
            vertex_project="top-proj",
            vertex_location="europe-west9",
        )
        eff1 = req1.get_effective_credentials()
        assert eff1.project == "top-proj"
        assert eff1.location == "europe-west9"

        # Case B: Nested overrides top-level
        req2 = AnalyzeRequest(
            prompt="test",
            vertex_project="top-proj",
            vertex_location="top-loc",
            credentials=CredentialsOverride(
                project="nested-proj",
                location="nested-loc",
            ),
        )
        eff2 = req2.get_effective_credentials()
        assert eff2.project == "nested-proj"
        assert eff2.location == "nested-loc"

        # Case C: Partial nested merges with top-level
        req3 = AnalyzeRequest(
            prompt="test",
            vertex_project="top-proj",
            credentials=CredentialsOverride(
                location="nested-loc-only",
            ),
        )
        eff3 = req3.get_effective_credentials()
        assert eff3.project == "top-proj"
        assert eff3.location == "nested-loc-only"


# ============================================================================
# Section 3: Empty String and Whitespace Fallback to 'global'
# ============================================================================

class TestWhitespaceAndEmptyStringFallback:
    """Stress-test edge cases involving empty strings, whitespace, and padding."""

    @pytest.mark.parametrize(
        "raw_location,expected_location",
        [
            ("", "global"),
            ("   ", "global"),
            (" \t \n ", "global"),
            ("  europe-west4  ", "europe-west4"),
            (" global ", "global"),
            ("  us-central1\n", "us-central1"),
        ],
    )
    def test_request_location_whitespace_handling(
        self, raw_location: str, expected_location: str, monkeypatch
    ):
        """Request override location with whitespace or empty string falls back to global (when env unset)."""
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)

        s = Settings()
        override = CredentialsOverride(
            project="test-project",
            location=raw_location,
        )
        resolved = s.resolve_credentials(override)
        assert resolved.vertex_location == expected_location

    @pytest.mark.parametrize(
        "raw_location",
        ["", "   ", " \t\r\n "]
    )
    def test_create_genai_client_whitespace_location_falls_back_to_global(
        self, raw_location: str, monkeypatch
    ):
        """create_genai_client with empty or whitespace location defaults to global."""
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)

        with patch("backend.app.services.genai_client.genai.Client") as mock_client:
            create_genai_client(project="test-proj", location=raw_location)
            assert mock_client.call_count == 1
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["vertexai"] is True
            assert call_kwargs["project"] == "test-proj"
            assert call_kwargs["location"] == "global"

    def test_get_genai_client_with_none_location_falls_back_to_global(self):
        """get_genai_client falls back to 'global' when vertex_location is None."""
        resolved = ResolvedCredentials(
            provider="vertex_ai",
            vertex_project="test-proj",
            vertex_location=None,
            is_valid=True,
        )
        with patch("backend.app.services.genai_client.genai.Client") as mock_client:
            get_genai_client(resolved=resolved)
            assert mock_client.call_args[1]["location"] == "global"

    def test_get_genai_client_with_empty_string_location_falls_back_to_global(self):
        """get_genai_client falls back to 'global' when vertex_location is empty string."""
        resolved = ResolvedCredentials(
            provider="vertex_ai",
            vertex_project="test-proj",
            vertex_location="",
            is_valid=True,
        )
        with patch("backend.app.services.genai_client.genai.Client") as mock_client:
            get_genai_client(resolved=resolved)
            assert mock_client.call_args[1]["location"] == "global"


# ============================================================================
# Section 4: GenAI Client Instantiation Corner Cases
# ============================================================================

class TestGenAIClientInstantiation:
    """Verify parameters passed to google.genai.Client under all boundary conditions."""

    @patch("backend.app.services.genai_client.genai.Client")
    def test_vertex_ai_client_contract(self, mock_client):
        """Vertex AI client must receive vertexai=True, location, project, and v1beta1 api_version."""
        create_genai_client(project="my-p1", location="asia-northeast3")
        assert mock_client.call_count == 1
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["vertexai"] is True
        assert call_kwargs["project"] == "my-p1"
        assert call_kwargs["location"] == "asia-northeast3"
        assert hasattr(call_kwargs["http_options"], "api_version")
        assert call_kwargs["http_options"].api_version == "v1beta1"

    @patch("backend.app.services.genai_client.genai.Client")
    def test_developer_api_client_contract(self, mock_client):
        """Developer API client must receive api_key only, without vertexai parameters."""
        create_genai_client(api_key="AIzaKeyStandard")
        assert mock_client.call_count == 1
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs == {"api_key": "AIzaKeyStandard"}
        assert "vertexai" not in call_kwargs
        assert "location" not in call_kwargs

    def test_unconfigured_credentials_raises_error(self, monkeypatch):
        """When neither API key nor Vertex AI project is set, raises CredentialsMissingError."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GCP_PROJECT", raising=False)
        monkeypatch.delenv("CLOUDSDK_CORE_PROJECT", raising=False)

        with patch.object(Settings, "get_vertex_project", return_value=None):
            with pytest.raises(CredentialsMissingError) as exc_info:
                create_genai_client()
            assert "No valid credentials found" in str(exc_info.value)

    def test_whitespace_project_and_key_raises_error(self, monkeypatch):
        """Passing all-whitespace credentials raises CredentialsMissingError."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        with patch.object(Settings, "get_vertex_project", return_value=None):
            with pytest.raises(CredentialsMissingError):
                create_genai_client(api_key="   ", project="   ", location="   ")


# ============================================================================
# Section 5: Differential Fuzzing against Formal Precedence Oracle
# ============================================================================

def formal_precedence_oracle(
    env_gcloc: Optional[str],
    env_vtloc: Optional[str],
    env_proj: Optional[str],
    env_key: Optional[str],
    req_loc: Optional[str],
    req_proj: Optional[str],
    req_key: Optional[str],
) -> Dict[str, Any]:
    """Formal specification oracle for credential and location resolution."""
    # 1. Request API Key
    if req_key and req_key.strip():
        return {
            "provider": "gemini_api_key",
            "api_key": req_key.strip(),
            "vertex_project": None,
            "vertex_location": None,
            "is_valid": True,
        }

    # 2. Request Vertex Project
    if req_proj and req_proj.strip():
        # Determine location
        if req_loc and req_loc.strip():
            loc = req_loc.strip()
        else:
            # Fall back to env location or global
            loc = env_gcloc or env_vtloc or "global"
        return {
            "provider": "vertex_ai",
            "api_key": None,
            "vertex_project": req_proj.strip(),
            "vertex_location": loc,
            "is_valid": True,
        }

    # 3. Ambient Gemini API Key
    if env_key and env_key.strip():
        return {
            "provider": "gemini_api_key",
            "api_key": env_key.strip(),
            "vertex_project": None,
            "vertex_location": None,
            "is_valid": True,
        }

    # 4. Ambient Vertex Project
    if env_proj and env_proj.strip():
        loc = env_gcloc or env_vtloc or "global"
        return {
            "provider": "vertex_ai",
            "api_key": None,
            "vertex_project": env_proj.strip(),
            "vertex_location": loc,
            "is_valid": True,
        }

    # 5. None configured
    return {
        "provider": "none",
        "api_key": None,
        "vertex_project": None,
        "vertex_location": None,
        "is_valid": False,
    }


class TestDifferentialFuzzing:
    """1,000-iteration randomized differential fuzzing against formal specification oracle."""

    LOCATIONS = [None, "", "us-central1", "europe-west4", "global", "asia-northeast3"]
    PROJECTS = [None, "", "fuzz-proj-alpha", "enterprise-corp-prod"]
    KEYS = [None, "", "AIzaSyFakeFuzzKey1", "AIzaSyFakeFuzzKey2"]

    def test_1000_fuzz_iterations(self, monkeypatch):
        """Fuzz 1000 random credential/location combinations and compare against oracle."""
        rng = random.Random(42)
        failures = []

        for i in range(1000):
            env_gcloc = rng.choice(self.LOCATIONS)
            env_vtloc = rng.choice(self.LOCATIONS)
            env_proj = rng.choice(self.PROJECTS)
            env_key = rng.choice(self.KEYS)

            req_loc = rng.choice(self.LOCATIONS)
            req_proj = rng.choice(self.PROJECTS)
            req_key = rng.choice(self.KEYS)

            # Set environment
            if env_gcloc is not None:
                monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", env_gcloc)
            else:
                monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)

            if env_vtloc is not None:
                monkeypatch.setenv("VERTEX_LOCATION", env_vtloc)
            else:
                monkeypatch.delenv("VERTEX_LOCATION", raising=False)

            if env_proj is not None:
                monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", env_proj)
            else:
                monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
            monkeypatch.delenv("GCP_PROJECT", raising=False)
            monkeypatch.delenv("CLOUDSDK_CORE_PROJECT", raising=False)

            if env_key is not None:
                monkeypatch.setenv("GEMINI_API_KEY", env_key)
            else:
                monkeypatch.delenv("GEMINI_API_KEY", raising=False)
            monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

            s = Settings()
            # Mock get_vertex_project to only check env vars without executing gcloud subprocess
            with patch.object(
                s,
                "get_vertex_project",
                return_value=env_proj.strip() if (env_proj and env_proj.strip()) else None,
            ):
                override = CredentialsOverride(
                    api_key=req_key,
                    project=req_proj,
                    location=req_loc,
                )
                actual = s.resolve_credentials(override)
                expected = formal_precedence_oracle(
                    env_gcloc=env_gcloc,
                    env_vtloc=env_vtloc,
                    env_proj=env_proj,
                    env_key=env_key,
                    req_loc=req_loc,
                    req_proj=req_proj,
                    req_key=req_key,
                )

                # Assert equivalence
                if (
                    actual.provider != expected["provider"]
                    or actual.is_valid != expected["is_valid"]
                    or actual.vertex_project != expected["vertex_project"]
                    or actual.vertex_location != expected["vertex_location"]
                    or actual.api_key != expected["api_key"]
                ):
                    failures.append({
                        "iteration": i,
                        "inputs": {
                            "env_gcloc": env_gcloc,
                            "env_vtloc": env_vtloc,
                            "env_proj": env_proj,
                            "env_key": env_key,
                            "req_loc": req_loc,
                            "req_proj": req_proj,
                            "req_key": req_key,
                        },
                        "expected": expected,
                        "actual": actual.model_dump(),
                    })

        assert not failures, f"Differential fuzzing found {len(failures)} mismatches: {failures[:3]}"


# ============================================================================
# Section 6: Live FastAPI HTTP Endpoints (/api/settings, /api/analyze)
# ============================================================================

class TestLiveHTTPEndpointsLocationStress:
    """Stress-test live ASGI HTTP endpoints for location reporting and override processing."""

    @pytest.mark.anyio
    async def test_api_settings_reports_global_by_default(self, monkeypatch):
        """GET /api/settings returns vertex_location='global' when env vars are unset."""
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/settings")
            assert resp.status_code == 200
            data = resp.json()
            assert data["vertex_location"] == "global"

    @pytest.mark.anyio
    async def test_api_settings_reports_regional_env_location(self, monkeypatch):
        """GET /api/settings returns regional location when configured in env."""
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/settings")
            assert resp.status_code == 200
            data = resp.json()
            assert data["vertex_location"] == "europe-west4"

    @pytest.mark.anyio
    async def test_post_analyze_location_override_passed_to_client(self, monkeypatch):
        """POST /api/analyze passes explicit location override to Vertex AI client."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)

        with patch("backend.app.services.video_analyzer.get_genai_client") as mock_get_client, \
             patch("backend.app.services.video_analyzer.execute_single_mode") as mock_exec:
            mock_client_instance = MagicMock()
            mock_get_client.return_value = mock_client_instance

            # Mock successful single mode execution
            from backend.app.schemas.analyze import ModelResult, TokenUsage
            dummy_result = ModelResult(
                model="gemini-3.7-flash",
                media_processing="static",
                text="sample response",
                execution_time_seconds=0.5,
                tokens=TokenUsage(total=100, prompt=80, candidates=20, thoughts=0),
            )
            mock_exec.return_value = dummy_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "prompt": "Analyze test video",
                    "video_url": "https://storage.googleapis.com/test/video.mp4",
                    "credentials": {
                        "project": "my-vertex-test-project",
                        "location": "europe-west1",
                    },
                }
                resp = await client.post("/api/analyze", json=payload)
                assert resp.status_code == 200

                # Verify get_genai_client received the exact override with location europe-west1
                assert mock_get_client.call_count == 1
                call_kwargs = mock_get_client.call_args[1]
                override_arg = call_kwargs["override"]
                resolved_arg = call_kwargs["resolved"]
                assert override_arg.location == "europe-west1"
                assert resolved_arg.vertex_location == "europe-west1"
                assert resolved_arg.vertex_project == "my-vertex-test-project"


# ============================================================================
# Section 7: In-Depth Edge Cases & Failure Mode Analysis
# ============================================================================

class TestEdgeCasesAndCornerCases:
    """Stress-test edge conditions to confirm exact behaviors and potential pitfalls."""

    def test_whitespace_env_var_leakage_to_client(self, monkeypatch):
        """When GOOGLE_CLOUD_LOCATION='   ', verify how get_vertex_location and Client behave.

        Finding: Because '   ' is a truthy non-empty string in Python,
        get_vertex_location() does not strip environment variables and returns '   '.
        This causes genai.Client to receive 'location': '   '.
        """
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "   ")
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-alpha")

        s = Settings()
        assert s.get_vertex_location() == "   "

        with patch("backend.app.services.genai_client.genai.Client") as mock_client:
            create_genai_client(project="proj-alpha")
            assert mock_client.call_count == 1
            call_kwargs = mock_client.call_args[1]
            # Empirically records that whitespace is passed through to client
            assert call_kwargs["location"] == "   "

    def test_location_only_override_behavior_without_project(self, monkeypatch):
        """When caller provides override with location='europe-west4' but no project.

        Finding: Priority 2 requires override.project to be truthy. If override.project
        is None, resolution falls through to Priority 4 (ambient project), which
        unconditionally assigns self.get_vertex_location() (ambient location), ignoring
        override.location.
        """
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "ambient-corp-project")

        s = Settings()
        override = CredentialsOverride(location="europe-west4")
        resolved = s.resolve_credentials(override)

        # Empirical proof: override.location is ignored because override.project is None!
        assert resolved.provider == "vertex_ai"
        assert resolved.vertex_project == "ambient-corp-project"
        assert resolved.vertex_location == "global"  # Falls back to ambient get_vertex_location(), NOT europe-west4

    def test_create_genai_client_location_only_without_project(self, monkeypatch):
        """create_genai_client(location='europe-west4') without project falls back to ambient location."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "ambient-corp-project")

        with patch("backend.app.services.genai_client.genai.Client") as mock_client:
            create_genai_client(location="europe-west4")
            call_kwargs = mock_client.call_args[1]
            # Empirically verify that location='global' is used because location-only override is not applied
            assert call_kwargs["location"] == "global"

    @pytest.mark.anyio
    async def test_post_analyze_request_whitespace_location_falls_back_to_global(self, monkeypatch):
        """POST /api/analyze with whitespace location cleanly falls back to 'global'."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("VERTEX_LOCATION", raising=False)

        with patch("backend.app.services.video_analyzer.get_genai_client") as mock_get_client, \
             patch("backend.app.services.video_analyzer.execute_single_mode") as mock_exec:
            mock_client_instance = MagicMock()
            mock_get_client.return_value = mock_client_instance

            from backend.app.schemas.analyze import ModelResult, TokenUsage
            dummy_result = ModelResult(
                model="gemini-3.7-flash",
                media_processing="static",
                text="sample response",
                execution_time_seconds=0.5,
                tokens=TokenUsage(total=100, prompt=80, candidates=20, thoughts=0),
            )
            mock_exec.return_value = dummy_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "prompt": "Analyze test video",
                    "video_url": "https://storage.googleapis.com/test/video.mp4",
                    "credentials": {
                        "project": "my-vertex-test-project",
                        "location": "   ",
                    },
                }
                resp = await client.post("/api/analyze", json=payload)
                assert resp.status_code == 200

                # Verify resolved location cleanly fell back to 'global'
                call_kwargs = mock_get_client.call_args[1]
                resolved_arg = call_kwargs["resolved"]
                assert resolved_arg.vertex_location == "global"

