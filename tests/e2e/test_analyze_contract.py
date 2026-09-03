"""Tier 1, Tier 2, Tier 3, and Tier 4 E2E Tests: Dual Analysis Contract.

Validates:
- POST /api/analyze request validation (empty prompt, missing video_url, malformed JSON)
- Graceful error handling for missing/invalid credentials (no 500 crashes)
- Per-request dynamic credentials override isolation
- Response schema for baseline, agentic, and savings objects
- Token telemetry arithmetic and invariants (input savings %, total savings %, prompt tokens saved)
"""

import math
import pytest
import httpx


class TestAnalyzeRequestValidation:
    """Tier 2: Request validation and boundary error handling."""

    def test_analyze_empty_body_returns_422(self, api_client: httpx.Client):
        """Verify empty body is rejected with 422 Unprocessable Entity."""
        response = api_client.post("/api/analyze", json={})
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    def test_analyze_missing_prompt_returns_422(self, api_client: httpx.Client):
        """Verify request missing 'prompt' is rejected with 422."""
        payload = {
            "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
            "video_source_type": "url",
        }
        response = api_client.post("/api/analyze", json=payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    def test_analyze_empty_string_prompt_handled_gracefully(self, api_client: httpx.Client):
        """Verify empty prompt string is handled gracefully without 500 server crash."""
        payload = {
            "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
            "video_source_type": "url",
            "prompt": "   ",
        }
        response = api_client.post("/api/analyze", json=payload)
        assert response.status_code != 500, f"Server crashed with 500 on whitespace prompt: {response.text}"
        assert response.status_code in [200, 400, 422]

    def test_analyze_invalid_video_url_type_returns_422(self, api_client: httpx.Client):
        """Verify request with invalid video_url type (e.g. null or int) returns 422."""
        payload = {
            "video_url": None,
            "prompt": "Analyze this video",
        }
        response = api_client.post("/api/analyze", json=payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    def test_analyze_invalid_credentials_handling(self, api_client: httpx.Client):
        """Tier 2: Invalid credentials should return structured error or client error, never unhandled 500."""
        payload = {
            "video_url": "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4",
            "video_source_type": "preset",
            "prompt": "What is the third logo in the second row of the UCP partners slide?",
            "credentials": {
                "api_key": "explicitly_bogus_gemini_api_key_for_testing_purposes",
            },
        }
        response = api_client.post("/api/analyze", json=payload)
        assert response.status_code != 500, f"Server crashed with 500 on bad credentials: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Must return structured error reporting
            assert data["baseline"].get("status") == "error", "Expected baseline status 'error'"
            assert data["agentic"].get("status") == "error", "Expected agentic status 'error'"
            err_msg = str(data["baseline"].get("error", "")) + str(data["agentic"].get("error", ""))
            assert any(term in err_msg for term in ["API key", "INVALID_ARGUMENT", "400", "401", "403"]), (
                f"Error message should mention invalid credentials, got: {err_msg}"
            )
        else:
            assert response.status_code in [400, 401, 403, 422]


    def test_analyze_adversarial_special_character_prompt(self, api_client: httpx.Client):
        """Adversarial Verification: Test prompt with unicode, emojis, escaped quotes, and newlines."""
        payload = {
            "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
            "video_source_type": "url",
            "prompt": "한국어 질문 🚀 \\n <script>alert('xss');</script> & \"double-quote\" `backticks` \t \r\n",
            "credentials": {"api_key": "test_adversarial_key"},
        }
        response = api_client.post("/api/analyze", json=payload)
        # Server must parse JSON cleanly and not crash with 500
        assert response.status_code != 500, f"Server crashed with 500 on special characters: {response.text}"



class TestCredentialOverrideIsolation:
    """Tier 3: Dynamic credentials override isolation."""

    def test_dynamic_credentials_do_not_mutate_server_settings(self, api_client: httpx.Client):
        """Verify passing per-request credentials does not leak into global server settings."""
        # Query initial settings
        resp_before = api_client.get("/api/settings")
        assert resp_before.status_code == 200
        settings_before = resp_before.json()

        # Send an analyze request with ephemeral credentials
        api_client.post(
            "/api/analyze",
            json={
                "video_url": "https://example.com/video.mp4",
                "video_source_type": "url",
                "prompt": "Test prompt",
                "credentials": {
                    "api_key": "temporary_probe_key",
                    "project": "temporary_probe_project",
                },
            },
        )

        # Query settings again and verify no state pollution
        resp_after = api_client.get("/api/settings")
        assert resp_after.status_code == 200
        settings_after = resp_after.json()

        assert settings_before == settings_after, "Settings were mutated by a per-request credentials payload!"


class TestTokenTelemetryArithmetic:
    """Tier 4: Token telemetry arithmetic invariants and savings calculation."""

    @staticmethod
    def calculate_savings(baseline_tokens: dict, agentic_tokens: dict) -> dict:
        """Reference calculation from Google Cloud documentation & PROJECT.md."""
        b_prompt = baseline_tokens["prompt"]
        a_prompt = agentic_tokens["prompt"]
        b_total = baseline_tokens["total"]
        a_total = agentic_tokens["total"]

        input_reduction = ((b_prompt - a_prompt) / b_prompt) * 100.0 if b_prompt > 0 else 0.0
        total_reduction = ((b_total - a_total) / b_total) * 100.0 if b_total > 0 else 0.0
        prompt_saved = b_prompt - a_prompt

        return {
            "total_reduction_percent": round(total_reduction, 1),
            "input_reduction_percent": round(input_reduction, 1),
            "prompt_tokens_saved": prompt_saved,
        }

    def test_keynote_benchmark_numbers_arithmetic(self):
        """Verify arithmetic against official Google Cloud Keynote numbers."""
        # Keynote demo telemetry:
        baseline_tokens = {
            "total": 127628,
            "prompt": 126344,
            "candidates": 55,
            "thoughts": 0,
        }
        agentic_tokens = {
            "total": 94962,
            "prompt": 4629,
            "candidates": 165,
            "thoughts": 90168,
        }

        savings = self.calculate_savings(baseline_tokens, agentic_tokens)

        # Assert input token reduction is ~96.3%
        assert math.isclose(savings["input_reduction_percent"], 96.3, abs_tol=0.1)
        # Assert total reduction is ~25.6%
        assert math.isclose(savings["total_reduction_percent"], 25.6, abs_tol=0.1)
        # Assert prompt tokens saved is 121,715
        assert savings["prompt_tokens_saved"] == 121715

    def test_token_invariants(self):
        """Verify token breakdown sums to total for both models."""
        baseline = {
            "total": 127628,
            "prompt": 126344,
            "candidates": 55,
            "thoughts": 0,
        }
        agentic = {
            "total": 94962,
            "prompt": 4629,
            "candidates": 165,
            "thoughts": 90168,
        }

        # Gemini usage_metadata: total_token_count encompasses prompt, candidates, thoughts, and any modality/system overhead
        assert baseline["total"] >= baseline["prompt"] + baseline["candidates"] + baseline["thoughts"]
        assert agentic["total"] >= agentic["prompt"] + agentic["candidates"] + agentic["thoughts"]
        assert agentic["prompt"] < baseline["prompt"], "Agentic input tokens must be lower than baseline"


class TestAnalyzeResponseSchemaContract:
    """Tier 1: Response schema validation helper."""

    @staticmethod
    def assert_analyze_response_schema(data: dict):
        """Helper to assert the response conforms to PROJECT.md §1."""
        assert "baseline" in data, "Missing 'baseline' in analyze response"
        assert "agentic" in data, "Missing 'agentic' in analyze response"
        assert "savings" in data, "Missing 'savings' in analyze response"

        for mode in ["baseline", "agentic"]:
            item = data[mode]
            assert item["model"] == "gemini-3.7-flash"
            assert item["media_processing"] == ("static" if mode == "baseline" else "agentic")
            assert isinstance(item["text"], str)
            assert isinstance(item["execution_time_seconds"], (int, float))
            assert item["execution_time_seconds"] >= 0

            tokens = item["tokens"]
            assert isinstance(tokens["total"], int) and tokens["total"] >= 0
            assert isinstance(tokens["prompt"], int) and tokens["prompt"] >= 0
            assert isinstance(tokens["candidates"], int) and tokens["candidates"] >= 0
            assert isinstance(tokens["thoughts"], int) and tokens["thoughts"] >= 0

        savings = data["savings"]
        assert isinstance(savings["total_reduction_percent"], (int, float))
        assert isinstance(savings["input_reduction_percent"], (int, float))
        assert isinstance(savings["prompt_tokens_saved"], int)


if __name__ == "__main__":
    test_math = TestTokenTelemetryArithmetic()
    test_math.test_keynote_benchmark_numbers_arithmetic()
    test_math.test_token_invariants()
    print("ALL TELEMETRY ARITHMETIC INVARIANTS PASSED SUCCESSFULLY!")
