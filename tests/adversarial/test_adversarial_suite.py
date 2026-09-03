"""Adversarial and Stress Testing Suite for Gemini 3.7 Flash Video Benchmark.

Covers:
1. Extreme & Adversarial Inputs:
   - Massive prompts (100KB, 1MB, 5MB)
   - Unicode edge cases (Bidi overrides, zero-width, zalgo, emojis, control chars, null bytes)
   - Injection vectors (XSS, SQLi, command injection, template syntax)
   - Malformed URLs and path traversals
   - Missing and invalid parameter types
2. Token Calculation Math & Arithmetic Edge Cases:
   - Zero baseline tokens (division-by-zero protection)
   - Inverted tokens (Agentic > Baseline)
   - Identical tokens
   - Negative tokens
   - Astronomical token counts (overflow resistance)
   - 1000-iteration differential fuzzing against formal oracle
3. Concurrency Stress Testing:
   - 100 and 250 concurrent requests to /api/health
   - 50 concurrent range streams to /api/preset/video
   - Adversarial malformed range requests under concurrency
   - Mixed endpoint concurrency under burst load (100 simultaneous requests)
4. GenAI Service Failure Modes & Telemetry Resilience:
   - Null usage_metadata
   - Empty candidates list
   - APIError exception handling
"""

import asyncio
import math
import random
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google.genai.errors import APIError

from backend.app.main import app
from backend.app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    ModelResult,
    TokenSavings,
    TokenUsage,
)
from backend.app.services.video_analyzer import (
    calculate_savings,
    execute_single_mode,
    resolve_video_uri,
)


# ============================================================================
# Category 1: Extreme & Adversarial Inputs
# ============================================================================

class TestAdversarialInputs:
    """Stress-test API request parsing and validation against adversarial payloads."""

    @pytest.mark.asyncio
    async def test_massive_prompt_1mb(self):
        """Verify API handles 1 MB prompt string without memory crash or 500 error."""
        massive_prompt = "What is happening in this video? " + ("A" * 1_000_000)
        payload = {
            "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
            "video_source_type": "url",
            "prompt": massive_prompt,
            "credentials": {"api_key": "test_adversarial_key"},
        }

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as client:
            t0 = time.perf_counter()
            response = await client.post("/api/analyze", json=payload)
            elapsed = time.perf_counter() - t0

            # Must never crash with 500 Internal Server Error
            assert response.status_code != 500, f"Server crashed with 500 on 1MB prompt: {response.text}"
            # Expect either 200 (processed/mocked) or 400/401/403 (bad credentials), handled cleanly
            assert response.status_code in [200, 400, 401, 403]
            assert elapsed < 5.0, f"1MB prompt parsing took too long: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_massive_prompt_5mb(self):
        """Verify API handles 5 MB prompt string without crashing."""
        massive_prompt = "Z" * 5_000_000
        payload = {
            "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
            "video_source_type": "url",
            "prompt": massive_prompt,
            "credentials": {"api_key": "test_adversarial_key"},
        }

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as client:
            response = await client.post("/api/analyze", json=payload)
            assert response.status_code != 500, f"Server crashed on 5MB prompt: {response.text}"
            assert response.status_code in [200, 400, 401, 403, 413, 422]

    @pytest.mark.asyncio
    async def test_special_unicode_complex(self):
        """Test with Bidi overrides, zero-width, Zalgo text, emojis, and control characters."""
        adversarial_prompts = [
            # BiDi override & control characters
            "Prompt with \u202E RTL override \u202D and \u2066 isolates \u2069",
            # Zero-width spaces and joiners
            "Zero\u200Bwidth\u200Cnon\u200Djoiner\uFEFFBOM",
            # Zalgo text / massive combining diacritics
            "H\u0300\u0301\u0302\u0303\u0304\u0305e\u0306\u0307\u0308\u0309\u030Al\u030B\u030C\u030D\u030El\u030F\u0310o\u0311",
            # High surrogate pairs, astronomical unicode & emojis
            "Emojis: 🚀🎥🔍⚡ \U0001F600 \U0001FA84 \U000E0001 \U0010FFFF",
            # Escape chars & raw control
            "Tabs \t Newlines \r\n Escaped \\\" quotes \\' and backslashes \\\\ \b \f",
            # Korean / CJK complex characters
            "한국어 질문: 2026년 구글 I/O 키노트에서 UCP 파트너 슬라이드의 세 번째 로고는 무엇인가요?",
        ]

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for prompt_str in adversarial_prompts:
                payload = {
                    "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
                    "video_source_type": "preset",
                    "prompt": prompt_str,
                    "credentials": {"api_key": "test_key"},
                }
                response = await client.post("/api/analyze", json=payload)
                assert response.status_code != 500, f"Crashed on prompt '{prompt_str[:30]}...': {response.text}"
                assert response.status_code in [200, 400, 401, 403]

    @pytest.mark.asyncio
    async def test_injection_payloads(self):
        """Test API resistance against XSS, SQLi, command injection, and template attacks."""
        injections = [
            "<script>alert(document.cookie)</script><svg/onload=alert('XSS')>",
            "'; DROP TABLE benchmark_results; SELECT * FROM users WHERE '1'='1",
            "$(cat /etc/passwd) `id` | rm -rf / ; ping -c 1 127.0.0.1",
            "{{ 7 * 7 }} ${7*7} <%= 7*7 %> #{7*7} *{7*7}",
            "__proto__.polluted = true; Object.prototype.isAdmin = true;",
            "%s%s%s%n%x%d format string test",
        ]

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for inj in injections:
                payload = {
                    "video_url": "https://storage.googleapis.com/test-bucket/video.mp4",
                    "video_source_type": "url",
                    "prompt": inj,
                    "credentials": {"api_key": "test_key"},
                }
                response = await client.post("/api/analyze", json=payload)
                assert response.status_code != 500, f"Server crashed on injection '{inj[:20]}': {response.text}"
                assert response.status_code in [200, 400, 401, 403]

    @pytest.mark.asyncio
    async def test_malformed_urls(self):
        """Test behavior when given non-HTTP/GCS schemes, path traversal, or malformed URLs."""
        malformed_urls = [
            "ftp://attacker.com/exploit.mp4",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "data:video/mp4;base64,AAAA",
            "http://[::1]:99999/video.mp4",
            "http://localhost/../../../../etc/passwd",
            "   ",
            "not_a_url_at_all",
            "http://" + ("sub." * 500) + "example.com/video.mp4",
        ]

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for url in malformed_urls:
                payload = {
                    "video_url": url,
                    "video_source_type": "url",
                    "prompt": "Analyze this video",
                    "credentials": {"api_key": "test_key"},
                }
                response = await client.post("/api/analyze", json=payload)
                # Must never 500 crash
                assert response.status_code != 500, f"Server crashed on URL '{url[:30]}': {response.text}"

    @pytest.mark.asyncio
    async def test_missing_and_invalid_parameters(self):
        """Verify strict 422 Unprocessable Entity responses for missing/malformed parameters."""
        bad_payloads = [
            {},  # Empty object
            {"video_url": "https://example.com/video.mp4"},  # Missing prompt
            {"prompt": None, "video_url": "https://example.com/video.mp4"},  # None prompt
            {"prompt": 12345, "video_url": "https://example.com/video.mp4"},  # Integer prompt
            {"prompt": ["list", "of", "strings"]},  # Array prompt
            {"prompt": {"nested": "dict"}},  # Dict prompt
            {"prompt": "valid", "video_url": None},  # None video_url
            {"prompt": "valid", "video_url": 99999},  # Int video_url
            {"prompt": "valid", "credentials": {"api_key": 12345}},  # Bad api_key type
            {"prompt": "valid", "credentials": {"project": ["bad_type"]}},  # Bad project type
        ]

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for bp in bad_payloads:
                response = await client.post("/api/analyze", json=bp)
                assert response.status_code == 422, f"Expected 422 for {bp}, got {response.status_code}: {response.text}"

    @pytest.mark.asyncio
    async def test_non_json_body_returns_422(self):
        """Verify passing raw malformed bytes with application/json header returns 422."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/analyze",
                content=b"THIS IS NOT VALID JSON {{{{",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_disallowed_http_methods(self):
        """Verify disallowed HTTP methods return 405 Method Not Allowed."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp_get_analyze = await client.get("/api/analyze")
            assert resp_get_analyze.status_code in [404, 405]

            resp_post_health = await client.post("/api/health")
            assert resp_post_health.status_code in [404, 405]

            resp_put_preset = await client.put("/api/preset")
            assert resp_put_preset.status_code in [404, 405]


# ============================================================================
# Category 2: Token Calculation Math & Arithmetic Edge Cases
# ============================================================================

class TestTokenArithmeticEdgeCases:
    """Stress-test token calculations against mathematical boundaries and oracles."""

    @staticmethod
    def oracle_savings(b_prompt: int, a_prompt: int, b_total: int, a_total: int) -> dict:
        """Formal mathematical oracle for savings calculations."""
        # Input reduction
        if b_prompt <= 0:
            prompt_saved = 0
            input_pct = 0.0
        else:
            prompt_saved = max(0, b_prompt - a_prompt)
            input_pct = round((prompt_saved / b_prompt) * 100.0, 1)

        # Total reduction
        if b_total <= 0:
            total_saved = 0
            total_pct = 0.0
        else:
            total_saved = max(0, b_total - a_total)
            total_pct = round((total_saved / b_total) * 100.0, 1)

        return {
            "prompt_tokens_saved": prompt_saved,
            "input_reduction_percent": input_pct,
            "total_tokens_saved": total_saved,
            "total_reduction_percent": total_pct,
        }

    def test_zero_baseline_division_by_zero_prevention(self):
        """Verify zero baseline tokens does NOT raise ZeroDivisionError and returns 0.0%."""
        baseline = ModelResult(
            media_processing="static",
            tokens=TokenUsage(total=0, prompt=0, candidates=0, thoughts=0),
        )
        agentic = ModelResult(
            media_processing="agentic",
            tokens=TokenUsage(total=0, prompt=0, candidates=0, thoughts=0),
        )

        savings = calculate_savings(baseline, agentic)
        assert savings.prompt_tokens_saved == 0
        assert savings.input_reduction_percent == 0.0
        assert savings.total_tokens_saved == 0
        assert savings.total_reduction_percent == 0.0

    def test_zero_baseline_with_positive_agentic(self):
        """Verify zero baseline with non-zero agentic tokens returns 0.0% savings safely."""
        baseline = ModelResult(
            media_processing="static",
            tokens=TokenUsage(total=0, prompt=0, candidates=0, thoughts=0),
        )
        agentic = ModelResult(
            media_processing="agentic",
            tokens=TokenUsage(total=5000, prompt=1000, candidates=50, thoughts=3950),
        )

        savings = calculate_savings(baseline, agentic)
        assert savings.prompt_tokens_saved == 0
        assert savings.input_reduction_percent == 0.0
        assert savings.total_tokens_saved == 0
        assert savings.total_reduction_percent == 0.0

    def test_inverted_tokens_agentic_uses_more_than_baseline(self):
        """Verify that when Agentic uses MORE tokens, savings are clamped to 0 (no negative savings)."""
        baseline = ModelResult(
            media_processing="static",
            tokens=TokenUsage(total=5000, prompt=4000, candidates=1000, thoughts=0),
        )
        agentic = ModelResult(
            media_processing="agentic",
            tokens=TokenUsage(total=20000, prompt=8000, candidates=2000, thoughts=10000),
        )

        savings = calculate_savings(baseline, agentic)
        assert savings.prompt_tokens_saved == 0, "Saved prompt tokens must not be negative"
        assert savings.input_reduction_percent == 0.0, "Input reduction must not be negative"
        assert savings.total_tokens_saved == 0, "Saved total tokens must not be negative"
        assert savings.total_reduction_percent == 0.0, "Total reduction must not be negative"

    def test_identical_token_counts(self):
        """Verify identical token counts produce exactly 0.0% savings and 0 saved tokens."""
        baseline = ModelResult(
            media_processing="static",
            tokens=TokenUsage(total=10000, prompt=8000, candidates=2000, thoughts=0),
        )
        agentic = ModelResult(
            media_processing="agentic",
            tokens=TokenUsage(total=10000, prompt=8000, candidates=2000, thoughts=0),
        )

        savings = calculate_savings(baseline, agentic)
        assert savings.prompt_tokens_saved == 0
        assert savings.input_reduction_percent == 0.0
        assert savings.total_tokens_saved == 0
        assert savings.total_reduction_percent == 0.0

    def test_100_percent_savings(self):
        """Verify 0 agentic prompt tokens yields exactly 100.0% input reduction."""
        baseline = ModelResult(
            media_processing="static",
            tokens=TokenUsage(total=10000, prompt=8000, candidates=2000, thoughts=0),
        )
        agentic = ModelResult(
            media_processing="agentic",
            tokens=TokenUsage(total=2000, prompt=0, candidates=2000, thoughts=0),
        )

        savings = calculate_savings(baseline, agentic)
        assert savings.prompt_tokens_saved == 8000
        assert savings.input_reduction_percent == 100.0
        assert savings.total_tokens_saved == 8000
        assert savings.total_reduction_percent == 80.0

    def test_astronomical_token_numbers_no_overflow(self):
        """Verify calculation does not overflow on numbers >= 10^18."""
        b_prompt = 10**18
        a_prompt = 2 * 10**17
        b_total = 10**19
        a_total = 5 * 10**18

        baseline = ModelResult(
            media_processing="static",
            tokens=TokenUsage(total=b_total, prompt=b_prompt, candidates=0, thoughts=0),
        )
        agentic = ModelResult(
            media_processing="agentic",
            tokens=TokenUsage(total=a_total, prompt=a_prompt, candidates=0, thoughts=0),
        )

        savings = calculate_savings(baseline, agentic)
        assert savings.prompt_tokens_saved == 8 * 10**17
        assert savings.input_reduction_percent == 80.0
        assert savings.total_tokens_saved == 5 * 10**18
        assert savings.total_reduction_percent == 50.0

    def test_differential_fuzzing_1000_iterations(self):
        """Differential Testing: Fuzz 1,000 randomized token distributions against mathematical oracle."""
        rng = random.Random(42)

        for i in range(1000):
            # Biased generation covering edge boundaries: 0, 1, small, large, inverted
            b_prompt = rng.choice([0, 1, rng.randint(0, 100), rng.randint(100, 1_000_000)])
            a_prompt = rng.choice([0, 1, rng.randint(0, 100), rng.randint(100, 1_000_000)])
            b_total = rng.choice([0, 1, rng.randint(0, 100), rng.randint(100, 2_000_000)])
            a_total = rng.choice([0, 1, rng.randint(0, 100), rng.randint(100, 2_000_000)])

            baseline = ModelResult(
                media_processing="static",
                tokens=TokenUsage(total=b_total, prompt=b_prompt, candidates=0, thoughts=0),
            )
            agentic = ModelResult(
                media_processing="agentic",
                tokens=TokenUsage(total=a_total, prompt=a_prompt, candidates=0, thoughts=0),
            )

            actual = calculate_savings(baseline, agentic)
            expected = self.oracle_savings(b_prompt, a_prompt, b_total, a_total)

            assert actual.prompt_tokens_saved == expected["prompt_tokens_saved"], f"Mismatch at #{i}"
            assert actual.input_reduction_percent == expected["input_reduction_percent"], f"Mismatch at #{i}"
            assert actual.total_tokens_saved == expected["total_tokens_saved"], f"Mismatch at #{i}"
            assert actual.total_reduction_percent == expected["total_reduction_percent"], f"Mismatch at #{i}"

            # Invariants
            assert 0.0 <= actual.input_reduction_percent <= 100.0
            assert 0.0 <= actual.total_reduction_percent <= 100.0
            assert actual.prompt_tokens_saved >= 0
            assert actual.total_tokens_saved >= 0


# ============================================================================
# Category 3: Concurrency Stress Test
# ============================================================================

class TestConcurrencyStress:
    """Stress-test concurrent request handling on health, presets, and video streaming."""

    @pytest.mark.asyncio
    async def test_health_concurrency_burst_100(self):
        """Burst 100 simultaneous async requests to /api/health."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            t0 = time.perf_counter()

            async def send_health(idx: int):
                resp = await client.get("/api/health")
                return resp.status_code, resp.json()

            tasks = [send_health(i) for i in range(100)]
            results = await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - t0

            assert len(results) == 100
            for status, body in results:
                assert status == 200
                assert body == {"status": "ok", "version": "1.0.0"}

            # Throughput check: 100 requests should complete in < 2.5 seconds
            rps = 100 / elapsed
            assert elapsed < 2.5, f"100 health requests took {elapsed:.2f}s (< 2.5s expected)"
            print(f"\n[BENCHMARK] 100 Health burst: {elapsed:.3f}s ({rps:.1f} req/s)")

    @pytest.mark.asyncio
    async def test_health_concurrency_burst_250(self):
        """Burst 250 simultaneous async requests to /api/health."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            t0 = time.perf_counter()

            async def send_health(idx: int):
                resp = await client.get("/api/health")
                return resp.status_code

            tasks = [send_health(i) for i in range(250)]
            statuses = await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - t0

            assert len(statuses) == 250
            assert all(s == 200 for s in statuses), "Some requests failed under 250 concurrent load"
            rps = 250 / elapsed
            print(f"\n[BENCHMARK] 250 Health burst: {elapsed:.3f}s ({rps:.1f} req/s)")

    @pytest.mark.asyncio
    async def test_video_streaming_concurrency_50(self):
        """Send 50 concurrent range chunk requests to /api/preset/video."""
        ranges = [
            "bytes=0-1023",
            "bytes=1024-2047",
            "bytes=2048-4095",
            "bytes=4096-8191",
            "bytes=100000-110239",
            "bytes=200000-205119",
            "bytes=-1024",
            "bytes=-2048",
            "bytes=0-511",
            "bytes=512-1023",
        ] * 5  # 50 total

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            t0 = time.perf_counter()

            async def fetch_range(r_header: str):
                resp = await client.get("/api/preset/video", headers={"Range": r_header})
                return resp.status_code, len(resp.content), resp.headers.get("Content-Range")

            tasks = [fetch_range(r) for r in ranges]
            results = await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - t0

            assert len(results) == 50
            for status, content_len, crange in results:
                assert status == 206, f"Expected 206, got {status}"
                assert content_len > 0, "Stream returned empty chunk"
                assert crange is not None, "Missing Content-Range header"

            print(f"\n[BENCHMARK] 50 Concurrent Video Range streams: {elapsed:.3f}s")

    @pytest.mark.asyncio
    async def test_video_streaming_adversarial_ranges_concurrent(self):
        """Send adversarial / malformed range headers concurrently."""
        adversarial_ranges = [
            "bytes=9999999999-",          # Out of bounds start -> 416
            "bytes=5000-100",             # start > end -> 416
            "bytes=invalid-format",       # ValueError -> 416
            "not_bytes=0-100",            # Missing 'bytes=' -> 416
            "bytes=0-0",                  # Single byte -> 206 (len=1)
            "bytes=-9999999999",          # Suffix > file size -> clamped to 0-(file_size-1) -> 206
            "bytes=0-10, 20-30",          # Multipart range -> ValueError -> 416
            "bytes=--50",                 # Negative start -> 416
        ] * 4  # 32 total

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async def test_range(r: str):
                resp = await client.get("/api/preset/video", headers={"Range": r})
                return resp.status_code

            tasks = [test_range(r) for r in adversarial_ranges]
            statuses = await asyncio.gather(*tasks)

            assert len(statuses) == 32
            # Every request must return either 416 or 206, NEVER 500
            for s in statuses:
                assert s in [206, 416], f"Unexpected status code {s} for adversarial range"

    @pytest.mark.asyncio
    async def test_mixed_endpoints_concurrency(self):
        """Simultaneous mixed burst of 100 requests across health, presets, settings, and video."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async def call_health():
                r = await client.get("/api/health")
                return "health", r.status_code

            async def call_settings():
                r = await client.get("/api/settings")
                return "settings", r.status_code

            async def call_preset():
                r = await client.get("/api/preset")
                return "preset", r.status_code

            async def call_video():
                r = await client.get("/api/preset/video", headers={"Range": "bytes=0-511"})
                return "video", r.status_code

            tasks = []
            for _ in range(40):
                tasks.append(call_health())
            for _ in range(20):
                tasks.append(call_settings())
            for _ in range(20):
                tasks.append(call_preset())
            for _ in range(20):
                tasks.append(call_video())

            random.shuffle(tasks)

            t0 = time.perf_counter()
            results = await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - t0

            assert len(results) == 100
            for endpoint_type, status in results:
                expected_status = 206 if endpoint_type == "video" else 200
                assert status == expected_status, f"Endpoint {endpoint_type} returned {status}"

            rps = 100 / elapsed
            print(f"\n[BENCHMARK] 100 Mixed endpoint burst: {elapsed:.3f}s ({rps:.1f} req/s)")


# ============================================================================
# Category 4: GenAI Service Failure Modes & Telemetry Resilience
# ============================================================================

class TestGenAIServiceEdgeCases:
    """Stress-test GenAI response parsing under anomalous API behavior."""

    @pytest.mark.asyncio
    async def test_execute_single_mode_null_usage_metadata(self):
        """Verify execute_single_mode handles null usage_metadata gracefully."""
        mock_response = MagicMock()
        mock_response.text = "Generated analysis answer."
        mock_response.usage_metadata = None
        mock_response.candidates = [
            MagicMock(content=MagicMock(parts=[MagicMock(thought=False, text="Generated analysis answer.")]))
        ]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await execute_single_mode(
            client=mock_client,
            model="gemini-3.7-flash",
            video_uri="gs://test-bucket/video.mp4",
            prompt="Analyze this",
            media_processing="agentic",
        )

        assert result.status == "success"
        assert result.text == "Generated analysis answer."
        assert result.tokens.total == 0
        assert result.tokens.prompt == 0
        assert result.tokens.candidates == 0
        assert result.tokens.thoughts == 0

    @pytest.mark.asyncio
    async def test_execute_single_mode_empty_candidates_list(self):
        """Verify execute_single_mode handles empty candidates list without IndexError."""
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=100, candidates_token_count=0, thoughts_token_count=0, total_token_count=100
        )
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await execute_single_mode(
            client=mock_client,
            model="gemini-3.7-flash",
            video_uri="gs://test-bucket/video.mp4",
            prompt="Analyze this",
            media_processing="static",
        )

        assert result.status == "success"
        assert result.text == ""
        assert result.thoughts is None
        assert result.tokens.prompt == 100

    @pytest.mark.asyncio
    async def test_execute_single_mode_api_error_capture(self):
        """Verify execute_single_mode captures APIError and returns status='error' without raising."""
        mock_client = MagicMock()
        # Simulate Google APIError
        err = APIError(
            429,
            {"error": {"message": "Resource exhausted: Quota exceeded for gemini-3.7-flash", "status": "RESOURCE_EXHAUSTED"}},
        )
        mock_client.aio.models.generate_content = AsyncMock(side_effect=err)

        result = await execute_single_mode(
            client=mock_client,
            model="gemini-3.7-flash",
            video_uri="gs://test-bucket/video.mp4",
            prompt="Analyze this",
            media_processing="agentic",
        )

        assert result.status == "error"
        assert result.text == ""
        assert result.tokens.total == 0
        assert "Resource exhausted" in (result.error or "")
        assert result.execution_time_seconds >= 0.0
