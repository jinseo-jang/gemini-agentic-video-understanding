"""Configuration and credential resolution module.

Provides dynamic detection and resolution of Gemini Developer API keys and
Vertex AI project/location credentials, supporting both ambient environment
settings and per-request overrides.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load any .env file in the project root or backend directory
_backend_dir = Path(__file__).resolve().parent.parent
_root_dir = _backend_dir.parent
for env_path in (_backend_dir / ".env", _root_dir / ".env"):
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)


class CredentialsOverride(BaseModel):
    """Optional per-request credential overrides from UI or API caller."""

    api_key: Optional[str] = Field(
        default=None,
        description="Optional Gemini Developer API key overriding environment.",
    )
    project: Optional[str] = Field(
        default=None,
        description="Optional Google Cloud Project ID overriding environment.",
    )
    location: Optional[str] = Field(
        default=None,
        description="Optional Vertex AI location overriding environment.",
    )


class ResolvedCredentials(BaseModel):
    """Resolved credentials bundle ready for client factory ingestion."""

    provider: str = Field(
        description="Active provider type: 'gemini_api_key' | 'vertex_ai' | 'none'"
    )
    api_key: Optional[str] = None
    vertex_project: Optional[str] = None
    vertex_location: Optional[str] = None
    has_adc: bool = False
    is_valid: bool = False


class Settings:
    """Application-level configuration and environment state."""

    def __init__(
        self,
        default_model: str = "gemini-3.7-flash",
        default_vertex_location: str = "global",
        cache_dir: Optional[Path] = None,
    ):
        self.default_model = default_model
        self.default_vertex_location = default_vertex_location
        self.cache_dir = cache_dir or (_root_dir / "data" / "cache")

    def has_gemini_api_key(self) -> bool:
        """Check if an ambient Gemini API key is configured."""
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    def get_gemini_api_key(self) -> Optional[str]:
        """Get the ambient Gemini API key if present."""
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def has_adc(self) -> bool:
        """Check if Application Default Credentials (ADC) are available."""
        custom_adc = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if custom_adc and Path(custom_adc).is_file():
            return True
        default_adc = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
        return default_adc.is_file()

    def get_vertex_project(self) -> Optional[str]:
        """Get the ambient Google Cloud project ID."""
        project = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT")
            or os.getenv("CLOUDSDK_CORE_PROJECT")
        )
        if project:
            return project

        # Fallback to gcloud config get-value project if gcloud CLI is installed
        if shutil.which("gcloud"):
            try:
                res = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=2,
                )
                if res.returncode == 0:
                    val = res.stdout.strip()
                    if val and val != "(unset)":
                        return val
            except Exception:
                pass
        return None

    def get_vertex_location(self) -> str:
        """Get configured Vertex AI location, defaulting to global."""
        return (
            os.getenv("GOOGLE_CLOUD_LOCATION")
            or os.getenv("VERTEX_LOCATION")
            or self.default_vertex_location
        )

    def resolve_credentials(
        self, override: Optional[CredentialsOverride] = None
    ) -> ResolvedCredentials:
        """Resolve credentials dynamically based on precedence rules.

        Precedence:
        1. Request override API key -> gemini_api_key
        2. Request override Project ID -> vertex_ai
        3. Environment GEMINI_API_KEY / GOOGLE_API_KEY -> gemini_api_key
        4. Environment/ADC Vertex AI project -> vertex_ai
        5. Unconfigured -> none
        """
        adc_present = self.has_adc()

        # Priority 1: Request override API key
        if override and override.api_key and override.api_key.strip():
            return ResolvedCredentials(
                provider="gemini_api_key",
                api_key=override.api_key.strip(),
                has_adc=adc_present,
                is_valid=True,
            )

        # Priority 2: Request override Vertex Project
        if override and override.project and override.project.strip():
            loc = (
                override.location.strip()
                if override.location and override.location.strip()
                else self.get_vertex_location()
            )
            return ResolvedCredentials(
                provider="vertex_ai",
                vertex_project=override.project.strip(),
                vertex_location=loc,
                has_adc=adc_present,
                is_valid=True,
            )

        # Priority 3: Ambient Gemini API key
        ambient_key = self.get_gemini_api_key()
        if ambient_key and ambient_key.strip():
            return ResolvedCredentials(
                provider="gemini_api_key",
                api_key=ambient_key.strip(),
                has_adc=adc_present,
                is_valid=True,
            )

        # Priority 4: Vertex AI project from env/gcloud
        vertex_proj = self.get_vertex_project()
        if vertex_proj and (adc_present or os.getenv("GOOGLE_GENAI_USE_ENTERPRISE")):
            return ResolvedCredentials(
                provider="vertex_ai",
                vertex_project=vertex_proj,
                vertex_location=self.get_vertex_location(),
                has_adc=adc_present,
                is_valid=True,
            )

        # Priority 5: If vertex project exists even without explicit ADC file check
        if vertex_proj:
            return ResolvedCredentials(
                provider="vertex_ai",
                vertex_project=vertex_proj,
                vertex_location=self.get_vertex_location(),
                has_adc=adc_present,
                is_valid=True,
            )

        # None configured
        return ResolvedCredentials(
            provider="none",
            has_adc=adc_present,
            is_valid=False,
        )


# Global settings singleton
settings = Settings()
