"""Unit tests for configuration and dynamic credential resolution."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from backend.app.config import CredentialsOverride, Settings, settings


def test_resolve_credentials_with_request_api_key_override():
    """Verify that a request API key override takes highest precedence."""
    override = CredentialsOverride(api_key="AIzaSy_custom_test_key")
    resolved = settings.resolve_credentials(override)

    assert resolved.provider == "gemini_api_key"
    assert resolved.api_key == "AIzaSy_custom_test_key"
    assert resolved.is_valid is True


def test_resolve_credentials_with_request_vertex_override():
    """Verify that a request Vertex AI override takes precedence."""
    override = CredentialsOverride(
        project="custom-vertex-project",
        location="asia-northeast3",
    )
    resolved = settings.resolve_credentials(override)

    assert resolved.provider == "vertex_ai"
    assert resolved.vertex_project == "custom-vertex-project"
    assert resolved.vertex_location == "asia-northeast3"
    assert resolved.is_valid is True


def test_resolve_credentials_ambient_gemini_api_key(monkeypatch):
    """Verify resolution of ambient GEMINI_API_KEY from environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "env_test_api_key_123")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    s = Settings()
    resolved = s.resolve_credentials(None)

    assert resolved.provider == "gemini_api_key"
    assert resolved.api_key == "env_test_api_key_123"
    assert resolved.is_valid is True


def test_resolve_credentials_ambient_vertex(monkeypatch):
    """Verify resolution of Vertex AI project when no API key is present."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-cloud-project-99")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")

    s = Settings()
    resolved = s.resolve_credentials(None)

    assert resolved.provider == "vertex_ai"
    assert resolved.vertex_project == "my-cloud-project-99"
    assert resolved.vertex_location == "global"
    assert resolved.is_valid is True


def test_resolve_credentials_default_vertex_location(monkeypatch):
    """Verify default vertex location is 'global' when unset in environment."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("VERTEX_LOCATION", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-cloud-project-99")

    s = Settings()
    resolved = s.resolve_credentials(None)
    assert resolved.vertex_location == "global"
    assert resolved.is_valid is True


def test_resolve_credentials_none_configured(monkeypatch):
    """Verify fallback to 'none' when no credentials exist."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("CLOUDSDK_CORE_PROJECT", raising=False)

    s = Settings()
    with patch.object(s, "get_vertex_project", return_value=None):
        resolved = s.resolve_credentials(None)
        assert resolved.provider == "none"
        assert resolved.is_valid is False
