"""Dual video analysis benchmark router."""

from __future__ import annotations

from fastapi import APIRouter
from backend.app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from backend.app.services.video_analyzer import analyze_video

router = APIRouter(tags=["Analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def run_analysis(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run dual parallel benchmark analysis comparing Static vs Agentic mode.

    Triggers concurrent requests using asyncio.gather to Gemini 3.7 Flash,
    extracts token telemetry from usage_metadata, measures execution times,
    and returns comprehensive side-by-side metrics.
    """
    return await analyze_video(request)
