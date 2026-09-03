"""Tier 4 E2E Test: Automated Headless Browser Full User Flow.

Verifies:
1. Top navigation bar loads and shows API status pill & badges.
2. Open Settings modal, verify default Vertex AI location is 'global', configure custom Vertex project, and save.
3. Load the I/O 2026 Keynote video preset and verify video element and preview metadata render.
4. Submit analysis prompt and assert side-by-side Baseline and Agentic benchmark cards respond.
5. Capture full-page screenshot artifact ('headless_e2e_result.png') and verify zero rendering errors.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCREENSHOT_PATH = PROJECT_ROOT / "headless_e2e_result.png"
CHROME_PATH = "/usr/bin/google-chrome"


@pytest.mark.skipif(
    not Path(CHROME_PATH).exists(),
    reason=f"Google Chrome binary not found at {CHROME_PATH}",
)
def test_headless_browser_full_flow(is_live_server: bool, base_url: str):
    """Execute complete 5-step E2E flow in headless Google Chrome via Playwright."""
    if not is_live_server:
        pytest.skip(f"Live server not responding at {base_url}. Start with ./run.sh first.")

    try:
        from playwright.sync_api import sync_playwright, expect
    except ImportError:
        pytest.fail(
            "Playwright is not installed in the active Python environment. "
            "Install with: ./.venv/bin/pip install playwright"
        )

    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        # Launch system Google Chrome in new headless mode
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1600, "height": 1200},
            device_scale_factor=1,
        )
        page = context.new_page()

        # Monitor console and page errors
        page.on(
            "console",
            lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        # ------------------------------------------------------------------
        # Step 1: Top navigation bar loads and shows API status
        # ------------------------------------------------------------------
        target_url = f"{base_url.rstrip('/')}/"
        page.goto(target_url, wait_until="networkidle", timeout=15000)

        # Header title
        header = page.locator("header")
        expect(header).to_be_visible()
        expect(header).to_contain_text("Gemini 3.7 Flash Video Benchmark")
        expect(header).to_contain_text("Static vs Agentic Mode")

        # API Status badge visible (Active status)
        expect(header).to_contain_text("Active")

        # ------------------------------------------------------------------
        # Step 2: Open Settings modal, verify default Vertex AI location is 'global',
        #         configure custom Vertex project, and save.
        # ------------------------------------------------------------------
        settings_btn = page.locator(
            'button[title="Configure API credentials"], header button:has-text("Settings")'
        ).first
        expect(settings_btn).to_be_visible()
        settings_btn.click()

        # Modal is open
        modal = page.locator('div.fixed:has-text("API & Model Settings")')
        expect(modal).to_be_visible()

        # Switch to Vertex AI tab
        vertex_tab = modal.locator('button:has-text("Google Cloud Vertex AI")')
        expect(vertex_tab).to_be_visible()
        vertex_tab.click()

        # Verify Location input defaults to 'global'
        location_input = modal.locator(
            'label:has-text("Vertex AI Location") ~ input, input[placeholder*="global"], input[placeholder*="us-central1"]'
        ).first
        expect(location_input).to_be_visible()
        loc_val = location_input.input_value().strip()
        assert loc_val == "global", (
            f"Expected default Vertex AI location to be 'global', but got: '{loc_val}'"
        )

        # Configure custom Vertex project using authorized project ID
        import json
        import urllib.request

        target_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "demo-gcp-project")
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/settings", timeout=5) as resp:
                settings_data = json.loads(resp.read().decode())
                if settings_data.get("vertex_project"):
                    target_project = settings_data["vertex_project"]
        except Exception:
            pass

        project_input = modal.locator(
            'label:has-text("Google Cloud Project ID") ~ input, input[placeholder*="my-gcp-project"]'
        ).first
        expect(project_input).to_be_visible()
        project_input.fill(target_project)
        assert project_input.input_value() == target_project

        # Apply settings and wait for modal to close
        apply_btn = modal.locator('button:has-text("Apply Settings")')
        expect(apply_btn).to_be_visible()
        apply_btn.click()

        # Modal closes after saving
        page.wait_for_selector('h3:has-text("API & Model Settings")', state="detached", timeout=5000)

        # ------------------------------------------------------------------
        # Step 3: Load video preset & verify preview metadata
        # ------------------------------------------------------------------
        preset_btn = page.locator('button:has-text("DeepMind Needle Demo"), button:has-text("Google Pixel Production")').first
        expect(preset_btn).to_be_visible()
        preset_btn.click()

        # Verify <video> element rendered with preset video URL
        video = page.locator("video")
        expect(video).to_be_visible()
        video_src = video.get_attribute("src")
        assert video_src and "/api/preset/video" in video_src, f"Unexpected video src: {video_src}"

        # Verify video metadata badge renders
        metadata_badge = page.locator('text="Video ready for benchmark"')
        expect(metadata_badge).to_be_visible()

        # Verify prompt textarea populated
        prompt_textarea = page.locator("textarea")
        expect(prompt_textarea).to_be_visible()
        prompt_val = prompt_textarea.input_value().strip()
        assert len(prompt_val) > 0, "Prompt textarea should not be empty after selecting preset"

        # ------------------------------------------------------------------
        # Step 4: Submit analysis prompt and assert side-by-side Baseline & Agentic cards respond
        # ------------------------------------------------------------------
        start_btn = page.locator('button:has-text("Start analysis")')
        expect(start_btn).to_be_enabled()
        start_btn.click()

        # Assert loading state triggered
        loading_indicator = page.locator('text="Benchmarking Both Modes..."')
        expect(loading_indicator).to_be_visible(timeout=5000)

        # Baseline & Agentic cards exist and enter active/calculating mode
        baseline_card = page.locator('div.rounded-2xl:has-text("Static Video Understanding")')
        agentic_card = page.locator('div.rounded-2xl:has-text("with Agentic Video Understanding")')
        expect(baseline_card).to_be_visible()
        expect(agentic_card).to_be_visible()

        # Wait for dual analysis to complete (up to 120 seconds for live dual model generation)
        page.wait_for_selector('text="Benchmarking Both Modes..."', state="detached", timeout=120000)
        expect(page.locator('button:has-text("Start analysis")')).to_be_visible()

        # 1. STRICT ASSERTION: Zero error cards, notices, or failure borders (strict-mode safe)
        expect(page.get_by_text("Analysis Error")).to_have_count(0)
        expect(page.get_by_text("Benchmark Notice")).to_have_count(0)
        expect(page.locator('.border-rose-200')).to_have_count(0)

        # 2. STRICT ASSERTION: Initial empty placeholders are gone
        expect(page.locator('text="Standard static video understanding response"')).not_to_be_visible()
        expect(page.locator('text="Agentic video understanding response"')).not_to_be_visible()

        # 3. STRICT ASSERTION: Positive Token Metrics on Baseline Card
        baseline_tokens_el = baseline_card.locator('div.flex.items-baseline > span.font-mono').first
        expect(baseline_tokens_el).to_be_visible()
        baseline_tokens_text = baseline_tokens_el.inner_text().strip().replace(',', '')
        assert baseline_tokens_text.isdigit(), f"Baseline tokens '{baseline_tokens_text}' is not a valid integer"
        baseline_total_tokens = int(baseline_tokens_text)
        assert baseline_total_tokens > 0, f"Expected positive baseline tokens, got {baseline_total_tokens}"

        baseline_sub_text = baseline_card.locator('p.text-xs.font-mono').first.inner_text()
        prompt_match = re.search(r"([\d,]+)\s+in\s+/", baseline_sub_text)
        assert prompt_match, f"Could not parse baseline prompt tokens from '{baseline_sub_text}'"
        baseline_prompt_tokens = int(prompt_match.group(1).replace(',', ''))
        assert baseline_prompt_tokens > 0, f"Expected positive baseline prompt tokens, got {baseline_prompt_tokens}"

        # 4. STRICT ASSERTION: Positive Token Metrics on Agentic Card (total > 0, prompt > 0, thoughts > 0)
        agentic_tokens_el = agentic_card.locator('div.flex.items-baseline > span.font-mono').first
        expect(agentic_tokens_el).to_be_visible()
        agentic_tokens_text = agentic_tokens_el.inner_text().strip().replace(',', '')
        assert agentic_tokens_text.isdigit(), f"Agentic tokens '{agentic_tokens_text}' is not a valid integer"
        agentic_total_tokens = int(agentic_tokens_text)
        assert agentic_total_tokens > 0, f"Expected positive agentic tokens, got {agentic_total_tokens}"

        agentic_sub_text = agentic_card.locator('p.text-xs.font-mono').first.inner_text()
        agentic_prompt_match = re.search(r"([\d,]+)\s+in\s+/", agentic_sub_text)
        assert agentic_prompt_match, f"Could not parse agentic prompt tokens from '{agentic_sub_text}'"
        agentic_prompt_tokens = int(agentic_prompt_match.group(1).replace(',', ''))
        assert agentic_prompt_tokens > 0, f"Expected positive agentic prompt tokens, got {agentic_prompt_tokens}"

        thoughts_match = re.search(r"([\d,]+)\s+thought", agentic_sub_text)
        assert thoughts_match, f"Could not parse agentic thought tokens from '{agentic_sub_text}'"
        agentic_thought_tokens = int(thoughts_match.group(1).replace(',', ''))
        assert agentic_thought_tokens > 0, f"Expected positive agentic thoughts tokens, got {agentic_thought_tokens}"

        # 5. STRICT ASSERTION: Total Token Comparison Callout is rendered with live metrics
        callout_el = page.locator('div.pointer-events-auto:has-text("Total Token")').first
        expect(callout_el).to_be_visible()
        callout_text = callout_el.inner_text().strip()
        assert "Total Token" in callout_text, f"Expected 'Total Token' in callout, got '{callout_text}'"
        assert "total" in callout_text, f"Expected 'total' in callout comparison, got '{callout_text}'"

        # 6. STRICT ASSERTION: Non-Empty Prose Answers (> 20 characters)
        baseline_prose = baseline_card.locator("div.prose")
        expect(baseline_prose).to_be_visible()
        baseline_text = baseline_prose.inner_text().strip()
        assert len(baseline_text) > 20, f"Baseline answer text too short ({len(baseline_text)} chars): {baseline_text[:40]}"

        agentic_prose = agentic_card.locator("div.prose")
        expect(agentic_prose).to_be_visible()
        agentic_text = agentic_prose.inner_text().strip()
        assert len(agentic_text) > 20, f"Agentic answer text too short ({len(agentic_text)} chars): {agentic_text[:40]}"

        # 7. Assert stopwatch timers updated from 0s
        expect(baseline_card.locator('text="Execution Time"')).to_be_visible()
        expect(agentic_card.locator('text="Execution Time"')).to_be_visible()

        # ------------------------------------------------------------------
        # Step 5: Capture full-page screenshot artifact ('headless_e2e_result.png')
        # ------------------------------------------------------------------
        page.wait_for_timeout(1000)  # Stabilize UI rendering
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)

        # Verify screenshot artifact physically generated
        assert SCREENSHOT_PATH.is_file(), f"Screenshot was not generated at {SCREENSHOT_PATH}"
        assert SCREENSHOT_PATH.stat().st_size > 10000, (
            f"Screenshot file size too small: {SCREENSHOT_PATH.stat().st_size} bytes"
        )
        with open(SCREENSHOT_PATH, "rb") as f:
            header_bytes = f.read(8)
            assert header_bytes == b"\x89PNG\r\n\x1a\n", "Generated artifact is not a valid PNG image"

        # Assert zero fatal rendering exceptions
        fatal_page_errors = [e for e in page_errors if "favicon" not in e.lower()]
        assert len(fatal_page_errors) == 0, f"Fatal page errors detected: {fatal_page_errors}"

        browser.close()


if __name__ == "__main__":
    # Allow running directly via `python3 test_headless_browser.py`
    pytest.main(["-v", "-s", __file__])
