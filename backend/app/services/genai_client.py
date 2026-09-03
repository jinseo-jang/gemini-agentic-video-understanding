"""GenAI Client Factory supporting Gemini Developer API and Vertex AI.

Produces initialized genai.Client instances with appropriate authentication,
endpoints, and API versions based on dynamic configuration or per-request overrides.
"""

from __future__ import annotations

from typing import Optional
from google import genai
from google.genai import types

from backend.app.config import CredentialsOverride, ResolvedCredentials, settings


class CredentialsMissingError(Exception):
    """Raised when neither Gemini API Key nor Vertex AI credentials are available."""

    def __init__(
        self,
        message: str = (
            "No valid credentials found. Please set GEMINI_API_KEY, configure "
            "GOOGLE_CLOUD_PROJECT with Application Default Credentials (ADC), "
            "or provide credentials in Settings."
        ),
    ):
        super().__init__(message)
        self.message = message


def create_genai_client(
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> genai.Client:
    """Create a genai.Client from explicit arguments or ambient settings.

    Args:
        api_key: Optional Gemini Developer API Key.
        project: Optional Google Cloud Project ID for Vertex AI.
        location: Optional Vertex AI location (defaults to global).

    Returns:
        genai.Client configured for either Developer API or Vertex AI.

    Raises:
        CredentialsMissingError: If no valid credentials could be resolved.
    """
    override = CredentialsOverride(api_key=api_key, project=project, location=location)
    resolved = settings.resolve_credentials(override)

    if not resolved.is_valid:
        raise CredentialsMissingError()

    if resolved.provider == "gemini_api_key":
        return genai.Client(api_key=resolved.api_key)

    if resolved.provider == "vertex_ai":
        loc = resolved.vertex_location or "global"
        return genai.Client(
            vertexai=True,
            project=resolved.vertex_project,
            location=loc,
            http_options=types.HttpOptions(api_version="v1beta1"),
        )

    raise CredentialsMissingError()


def get_genai_client(
    override: Optional[CredentialsOverride] = None,
    resolved: Optional[ResolvedCredentials] = None,
) -> genai.Client:
    """Factory wrapper resolving credentials and constructing a genai.Client.

    Args:
        override: Optional per-request override credentials.
        resolved: Optional pre-resolved credentials bundle.

    Returns:
        Configured genai.Client.
    """
    if resolved is None:
        resolved = settings.resolve_credentials(override)

    if not resolved.is_valid:
        raise CredentialsMissingError()

    if resolved.provider == "gemini_api_key":
        return genai.Client(api_key=resolved.api_key)

    if resolved.provider == "vertex_ai":
        loc = resolved.vertex_location or "global"
        return genai.Client(
            vertexai=True,
            project=resolved.vertex_project,
            location=loc,
            http_options=types.HttpOptions(api_version="v1beta1"),
        )

    raise CredentialsMissingError()
