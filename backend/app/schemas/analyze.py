"""Pydantic schemas for video analysis requests, responses, and token telemetry."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from backend.app.config import CredentialsOverride


class TokenUsage(BaseModel):
    """Detailed token telemetry extracted from response.usage_metadata."""

    total: int = Field(default=0, description="Total tokens consumed.")
    prompt: int = Field(default=0, description="Input/prompt tokens (video + text).")
    candidates: int = Field(default=0, description="Output candidate tokens.")
    thoughts: int = Field(default=0, description="Reasoning / thinking tokens.")
    tool_use: int = Field(default=0, description="Tool / video frame inspection tokens consumed in agentic mode.")


class ModelResult(BaseModel):
    """Execution result and telemetry for a single mode (static or agentic)."""

    model: str = Field(default="gemini-3.7-flash", description="Model used.")
    media_processing: str = Field(
        description="Media processing mode: 'static' or 'agentic'."
    )
    text: str = Field(default="", description="Generated output response text.")
    execution_time_seconds: float = Field(
        default=0.0, description="High-precision wall-clock latency in seconds."
    )
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    thoughts: Optional[str] = Field(
        default=None, description="Extracted reasoning thought process text."
    )
    thinking_level: Optional[str] = Field(
        default=None, description="Thinking level configured for execution: minimal, low, medium, high."
    )
    status: Optional[str] = Field(
        default="success", description="Status of generation: 'success' | 'error'."
    )
    error: Optional[str] = Field(
        default=None, description="Error message if generation failed."
    )


class TokenSavings(BaseModel):
    """Calculated token savings comparing static baseline against agentic mode."""

    total_reduction_percent: float = Field(
        default=0.0, description="Percentage of total tokens saved."
    )
    input_reduction_percent: float = Field(
        default=0.0, description="Percentage of prompt/input tokens saved."
    )
    prompt_tokens_saved: int = Field(
        default=0, description="Net prompt tokens saved."
    )
    total_tokens_saved: Optional[int] = Field(
        default=0, description="Net total tokens saved."
    )


class AnalyzeRequest(BaseModel):
    """Incoming request for dual benchmark video analysis."""

    video_url: str = Field(
        default="https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4",
        description="URL or GCS URI of video to analyze.",
    )
    video_source_type: Optional[str] = Field(
        default=None,
        description="Source type: 'preset' | 'url' | 'youtube' | 'gcs'.",
    )
    # Also support alternate field name video_source
    video_source: Optional[str] = Field(
        default=None,
        description="Alias for video_source_type.",
    )
    prompt: str = Field(
        ...,
        description="Prompt question to ask the model about the video.",
    )
    model: Optional[str] = Field(
        default="gemini-3.7-flash",
        description="Gemini model identifier.",
    )
    thinking_level: Optional[str] = Field(
        default="medium",
        description="Thinking level for Gemini 3.7 Flash: 'minimal' | 'low' | 'medium' | 'high'.",
    )
    credentials: Optional[CredentialsOverride] = Field(
        default=None,
        description="Optional dynamic credentials overriding server configuration.",
    )
    # Direct top-level credentials support
    api_key: Optional[str] = Field(
        default=None,
        description="Optional top-level Gemini Developer API key.",
    )
    vertex_project: Optional[str] = Field(
        default=None,
        description="Optional top-level Vertex AI project ID.",
    )
    vertex_location: Optional[str] = Field(
        default=None,
        description="Optional top-level Vertex AI location.",
    )

    def get_effective_credentials(self) -> CredentialsOverride:
        """Merge nested and top-level credentials override fields."""
        base_api = self.api_key
        base_proj = self.vertex_project
        base_loc = self.vertex_location

        if self.credentials:
            if self.credentials.api_key:
                base_api = self.credentials.api_key
            if self.credentials.project:
                base_proj = self.credentials.project
            if self.credentials.location:
                base_loc = self.credentials.location

        return CredentialsOverride(
            api_key=base_api,
            project=base_proj,
            location=base_loc,
        )

    def get_effective_source_type(self) -> str:
        """Get canonical source type."""
        return (self.video_source_type or self.video_source or "preset").lower()


class AnalyzeResponse(BaseModel):
    """Side-by-side benchmark response containing Baseline, Agentic, and Savings."""

    baseline: ModelResult
    agentic: ModelResult
    savings: TokenSavings
    token_savings_percent: Optional[float] = Field(
        default=None,
        description="Convenience alias for input_reduction_percent.",
    )
