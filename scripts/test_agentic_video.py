#!/usr/bin/env python3
"""Gemini 3.7 Flash: Agentic Video Understanding 토큰 사용량 직접 측정 CLI 스크립트.

사용법 예시:
  # 1. 기본 실행 (Agentic 모드)
  ./.venv/bin/python3 scripts/test_agentic_video.py

  # 2. YouTube URL로 실행 (Static vs Agentic 나란히 비교)
  ./.venv/bin/python3 scripts/test_agentic_video.py --video "https://www.youtube.com/watch?v=LzExSq9DU9w" --mode both --thinking-level low

  # 3. 사고 강도(thinking-level) 설정 (minimal, low, medium, high)
  ./.venv/bin/python3 scripts/test_agentic_video.py --thinking-level low

  # 4. 다른 비디오 및 프롬프트 지정
  ./.venv/bin/python3 scripts/test_agentic_video.py --video data/cache/KW_SxS-needle_Blog_V1.mp4 --prompt "What is the utility displaying the locomotive?"
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types


def run_single_mode(
    client: genai.Client,
    video_part: types.Part,
    prompt: str,
    mode: str,
    thinking_level: str = "high",
) -> dict:
    """단일 모드(agentic 또는 static)로 Gemini 3.7 Flash를 호출하고 토큰 메트릭을 반환합니다."""
    print("\n" + "=" * 70)
    print(f"🚀 Gemini 3.7 Flash 실행 중: [{mode.upper()} 모드]")
    print(f"• 사고 강도 (thinking_level): {thinking_level.upper()}")
    print("=" * 70)

    # Thinking 설정 (Gemini 3.7 Flash 공식 규격: ThinkingLevel Enum)
    level_enum = types.ThinkingLevel[thinking_level.upper()]
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=level_enum,
            include_thoughts=True,
        )
    )

    # 모델 호출 및 소요 시간 측정
    start_time = time.perf_counter()
    print("⏳ 모델 추론 중... (잠시만 기다려주세요)")
    
    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=[video_part, prompt],
        config=config,
    )
    elapsed_time = round(time.perf_counter() - start_time, 2)

    # usage_metadata에서 세부 토큰 추출
    meta = response.usage_metadata
    prompt_tokens = getattr(meta, "prompt_token_count", 0) or 0
    candidates_tokens = getattr(meta, "candidates_token_count", 0) or 0
    thoughts_tokens = getattr(meta, "thoughts_token_count", 0) or 0
    tool_tokens = getattr(meta, "tool_use_prompt_token_count", 0) or 0
    total_tokens = getattr(meta, "total_token_count", 0) or 0

    # 사고(thought) 요약 추출
    thought_text = ""
    if response and response.candidates and response.candidates[0].content:
        parts = response.candidates[0].content.parts or []
        thought_snippets = [p.text for p in parts if getattr(p, "thought", False) and p.text]
        if thought_snippets:
            thought_text = "\n".join(thought_snippets)

    return {
        "mode": mode,
        "elapsed_time": elapsed_time,
        "text": response.text or "",
        "thought_text": thought_text,
        "tokens": {
            "prompt": prompt_tokens,
            "tool_use": tool_tokens,
            "thoughts": thoughts_tokens,
            "candidates": candidates_tokens,
            "total": total_tokens,
        },
    }


def print_mode_result(res: dict):
    """단일 실행 결과와 토큰을 보기 쉽게 포맷팅하여 출력합니다."""
    mode = res["mode"].upper()
    tokens = res["tokens"]

    print("\n" + "=" * 70)
    print(f"📝 [{mode} 모드 - 모델 응답 텍스트]")
    print("=" * 70)
    text = res["text"].strip()
    if len(text) > 1000:
        print(text[:1000] + f"\n... [생략: 전체 길이 {len(text)}자]")
    else:
        print(text)

    print("\n" + "-" * 70)
    print(f"📊 [{mode} 모드 - 토큰 사용량 (usage_metadata)]")
    print("-" * 70)
    print(f"⏱ 소요 시간           : {res['elapsed_time']} 초")
    print(f"1️⃣ 초기 입력 토큰 (Prompt)      : {tokens['prompt']:,} 토큰")
    print(f"2️⃣ 도구 호출 토큰 (Tool Use)    : {tokens['tool_use']:,} 토큰 (에이전트 프레임 조회)")
    print(f"3️⃣ 모델 추론 토큰 (Thoughts)    : {tokens['thoughts']:,} 토큰 (사고 과정)")
    print(f"4️⃣ 최종 답변 토큰 (Candidates)  : {tokens['candidates']:,} 토큰")
    print("-" * 70)
    print(f"🏷 총 사용 토큰   (Total)       : {tokens['total']:,} 토큰")
    print("=" * 70)


def print_comparison_table(static_res: dict, agentic_res: dict):
    """Static과 Agentic의 토큰 사용량을 1:1로 비교하는 테이블을 출력합니다."""
    s_tok = static_res["tokens"]
    a_tok = agentic_res["tokens"]

    prompt_saved = s_tok["prompt"] - a_tok["prompt"]
    prompt_saved_pct = (prompt_saved / s_tok["prompt"] * 100) if s_tok["prompt"] > 0 else 0

    video_data_static = s_tok["prompt"]
    video_data_agentic = a_tok["prompt"] + a_tok["tool_use"]
    video_saved = video_data_static - video_data_agentic
    video_saved_pct = (video_saved / video_data_static * 100) if video_data_static > 0 else 0

    print("\n" + "=" * 80)
    print("⚖️  [Static vs Agentic 토큰 1:1 비교 분석표]")
    print("=" * 80)
    print(f"{'항목':<28} | {'STATIC (Baseline)':<18} | {'AGENTIC':<18} | {'변화량 (절감률)'}")
    print("-" * 80)
    print(f"{'초기 입력 (Prompt In)':<28} | {s_tok['prompt']:>14,} 토큰 | {a_tok['prompt']:>14,} 토큰 | {prompt_saved_pct:>+6.1f}% ({prompt_saved:+,}개)")
    print(f"{'동적 도구 로드 (Tool Use)':<28} | {s_tok['tool_use']:>14,} 토큰 | {a_tok['tool_use']:>14,} 토큰 | {'(에이전트 조회)'}")
    print(f"{'순수 영상 데이터 (In + Tool)':<28} | {video_data_static:>14,} 토큰 | {video_data_agentic:>14,} 토큰 | {video_saved_pct:>+6.1f}% ({video_saved:+,}개)")
    print(f"{'사고/추론 (Thoughts)':<28} | {s_tok['thoughts']:>14,} 토큰 | {a_tok['thoughts']:>14,} 토큰 | {a_tok['thoughts'] - s_tok['thoughts']:+,}개")
    print(f"{'최종 출력 (Candidates)':<28} | {s_tok['candidates']:>14,} 토큰 | {a_tok['candidates']:>14,} 토큰 | {a_tok['candidates'] - s_tok['candidates']:+,}개")
    print("-" * 80)
    total_diff = a_tok["total"] - s_tok["total"]
    print(f"{'총 사용 토큰 (Total)':<28} | {s_tok['total']:>14,} 토큰 | {a_tok['total']:>14,} 토큰 | {total_diff:+,} 토큰")
    print(f"{'소요 시간 (Execution Time)':<28} | {static_res['elapsed_time']:>14.1f} 초 | {agentic_res['elapsed_time']:>14.1f} 초 | {agentic_res['elapsed_time'] - static_res['elapsed_time']:>+6.1f} 초")
    print("=" * 80 + "\n")


def build_video_part(video_source: str, mode: str) -> types.Part:
    """비디오 소스(YouTube URL, GCS 또는 로컬 파일)에 맞춰 types.Part를 빌드합니다."""
    # 1. YouTube URL 지원
    if "youtube.com" in video_source.lower() or "youtu.be" in video_source.lower():
        print(f"🔗 YouTube 비디오 감지: {video_source}")
        return types.Part(
            file_data=types.FileData(
                file_uri=video_source,
                mime_type="video/mp4",
            ),
            media_processing=mode,
        )

    # 2. GCS URI 지원
    if video_source.startswith("gs://"):
        return types.Part(
            file_data=types.FileData(
                file_uri=video_source,
                mime_type="video/mp4",
            ),
            media_processing=mode,
        )

    # 3. 로컬 파일
    video_path = Path(video_source)
    if not video_path.exists():
        alt_path = Path(__file__).resolve().parent.parent / video_source
        if alt_path.exists():
            video_path = alt_path
        else:
            raise FileNotFoundError(f"비디오 파일을 찾을 수 없습니다: {video_source}")

    video_bytes = video_path.read_bytes()
    size_mb = len(video_bytes) / (1024 * 1024)
    print(f"📦 비디오 파일 로드 완료: {video_path.name} ({size_mb:.2f} MB)")

    return types.Part(
        inline_data=types.Blob(
            data=video_bytes,
            mime_type="video/mp4",
        ),
        media_processing=mode,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Gemini 3.7 Flash: Agentic Video Understanding 토큰 사용량 측정 도구"
    )
    parser.add_argument(
        "--video",
        default="data/cache/behind_the_scenes_pixel.mp4",
        help="로컬 mp4 파일 경로, YouTube URL 또는 gs:// URI (기본: 5분 Pixel 영상)",
    )
    parser.add_argument(
        "--prompt",
        default="Describe the main cameras, equipment, and filming setups used in this shoot.",
        help="질문 프롬프트",
    )
    parser.add_argument(
        "--mode",
        choices=["agentic", "static", "both"],
        default="agentic",
        help="실행 모드: 'agentic', 'static', 또는 'both' (나란히 비교, 기본: agentic)",
    )
    parser.add_argument(
        "--thinking-level",
        choices=["minimal", "low", "medium", "high"],
        default="medium",
        help="사고 강도 (Gemini 3.7 공식 규격: minimal, low, medium, high / 기본: medium)",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="Google Cloud 프로젝트 ID (미지정 시 GOOGLE_CLOUD_PROJECT 환경변수 또는 gcloud 기본값 사용)",
    )
    parser.add_argument(
        "--location",
        default="global",
        help="Vertex AI 리전 (Gemini 3.7 Flash는 'global' 필수)",
    )

    args = parser.parse_args()

    # Project & Auth 해석
    project_id = args.project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id and shutil.which("gcloud"):
        try:
            res = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                val = res.stdout.strip()
                if val and val != "(unset)":
                    project_id = val
        except Exception:
            pass

    api_key = os.environ.get("GEMINI_API_KEY")
    if not project_id and api_key:
        client = genai.Client(api_key=api_key)
        auth_desc = "Gemini Developer API (GEMINI_API_KEY)"
    else:
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=args.location,
        )
        auth_desc = f"Vertex AI (프로젝트: {project_id}, 리전: {args.location})"

    print("\n" + "#" * 70)
    print("🎬 Gemini 3.7 Flash Video Understanding 토큰 벤치마크")
    print(f"• 인증: {auth_desc}")
    print(f"• 대상 비디오: {args.video}")
    print(f"• 프롬프트: {args.prompt}")
    print(f"• 사고 강도: {args.thinking_level.upper()}")
    print("#" * 70)

    if args.mode == "both":
        # Static 실행
        part_static = build_video_part(args.video, "static")
        static_res = run_single_mode(
            client, part_static, args.prompt, "static", args.thinking_level
        )
        print_mode_result(static_res)

        # Agentic 실행
        part_agentic = build_video_part(args.video, "agentic")
        agentic_res = run_single_mode(
            client, part_agentic, args.prompt, "agentic", args.thinking_level
        )
        print_mode_result(agentic_res)

        # 비교 분석표 출력
        print_comparison_table(static_res, agentic_res)

    else:
        part = build_video_part(args.video, args.mode)
        res = run_single_mode(
            client, part, args.prompt, args.mode, args.thinking_level
        )
        print_mode_result(res)


if __name__ == "__main__":
    main()
