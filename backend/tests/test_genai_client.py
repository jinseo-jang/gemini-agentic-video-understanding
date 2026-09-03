"""Unit tests for GenAI client factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from backend.app.config import CredentialsOverride, ResolvedCredentials
from backend.app.services.genai_client import (
    CredentialsMissingError,
    create_genai_client,
    get_genai_client,
)


@patch("backend.app.services.genai_client.genai.Client")
def test_create_genai_client_with_api_key(mock_client_cls):
    """Verify Developer API client initialization with API key."""
    create_genai_client(api_key="test_api_key_xyz")
    mock_client_cls.assert_called_once_with(api_key="test_api_key_xyz")


@patch("backend.app.services.genai_client.genai.Client")
def test_create_genai_client_with_vertex(mock_client_cls):
    """Verify Vertex AI client initialization with project and location."""
    create_genai_client(project="my-project-123", location="us-east4")

    assert mock_client_cls.call_count == 1
    call_kwargs = mock_client_cls.call_args[1]
    assert call_kwargs["vertexai"] is True
    assert call_kwargs["project"] == "my-project-123"
    assert call_kwargs["location"] == "us-east4"
    assert call_kwargs["http_options"].api_version == "v1beta1"


def test_create_genai_client_raises_when_unconfigured():
    """Verify CredentialsMissingError is raised when no credentials are provided."""
    with patch("backend.app.services.genai_client.settings.resolve_credentials") as mock_resolve:
        mock_resolve.return_value = ResolvedCredentials(
            provider="none",
            is_valid=False,
        )
        with pytest.raises(CredentialsMissingError):
            create_genai_client()


@patch("backend.app.services.genai_client.genai.Client")
def test_get_genai_client_with_override(mock_client_cls):
    """Verify get_genai_client correctly resolves override object."""
    override = CredentialsOverride(api_key="custom_override_key")
    get_genai_client(override=override)
    mock_client_cls.assert_called_once_with(api_key="custom_override_key")


@patch("backend.app.services.genai_client.genai.Client")
def test_create_genai_client_vertex_default_global_location(mock_client_cls, monkeypatch):
    """Verify Vertex AI client defaults to 'global' location when omitted."""
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("VERTEX_LOCATION", raising=False)
    create_genai_client(project="my-project-123")

    assert mock_client_cls.call_count == 1
    call_kwargs = mock_client_cls.call_args[1]
    assert call_kwargs["vertexai"] is True
    assert call_kwargs["location"] == "global"


@patch("backend.app.services.genai_client.genai.Client")
def test_get_genai_client_fallback_location_global(mock_client_cls):
    """Verify get_genai_client falls back to 'global' if vertex_location is None."""
    resolved = ResolvedCredentials(
        provider="vertex_ai",
        vertex_project="my-project-123",
        vertex_location=None,
        is_valid=True,
    )
    get_genai_client(resolved=resolved)
    call_kwargs = mock_client_cls.call_args[1]
    assert call_kwargs["location"] == "global"

