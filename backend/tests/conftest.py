"""Pytest fixtures and test configuration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


class DummyUsageMetadata:
    """Mock usage metadata matching google.genai response structure."""

    def __init__(
        self,
        prompt_token_count: int = 1000,
        candidates_token_count: int = 100,
        thoughts_token_count: int = 0,
        tool_use_prompt_token_count: int = 0,
        total_token_count: int = 1100,
    ):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.thoughts_token_count = thoughts_token_count
        self.tool_use_prompt_token_count = tool_use_prompt_token_count
        self.total_token_count = total_token_count


class DummyPart:
    """Mock content part."""

    def __init__(self, text: str, thought: bool = False):
        self.text = text
        self.thought = thought


class DummyContent:
    """Mock candidate content."""

    def __init__(self, parts: list):
        self.parts = parts


class DummyCandidate:
    """Mock candidate."""

    def __init__(self, parts: list):
        self.content = DummyContent(parts)


class DummyGenerateContentResponse:
    """Mock Gemini generate content response."""

    def __init__(
        self,
        text: str,
        usage_metadata: DummyUsageMetadata,
        thought_text: str = "",
    ):
        self.text = text
        self.usage_metadata = usage_metadata
        parts = []
        if thought_text:
            parts.append(DummyPart(text=thought_text, thought=True))
        parts.append(DummyPart(text=text, thought=False))
        self.candidates = [DummyCandidate(parts)]


@pytest.fixture
def dummy_static_response() -> DummyGenerateContentResponse:
    """Dummy response mimicking static video processing."""
    return DummyGenerateContentResponse(
        text="The third logo in the second row is Partner X.",
        usage_metadata=DummyUsageMetadata(
            prompt_token_count=120000,
            candidates_token_count=60,
            thoughts_token_count=0,
            total_token_count=120060,
        ),
    )


@pytest.fixture
def dummy_agentic_response() -> DummyGenerateContentResponse:
    """Dummy response mimicking agentic video processing with ~96% savings."""
    return DummyGenerateContentResponse(
        text="Based on the UCP slide, the third logo in the second row is Partner X.",
        usage_metadata=DummyUsageMetadata(
            prompt_token_count=4800,
            candidates_token_count=150,
            thoughts_token_count=85000,
            tool_use_prompt_token_count=7000,
            total_token_count=96950,
        ),
        thought_text="Analyzing video frames at 00:32... Found UCP slide at 00:35...",
    )
