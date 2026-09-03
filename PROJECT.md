# Project: Gemini 3.7 Flash Video Understanding Benchmark (Static vs Agentic)

## Architecture Overview
The application is a full-stack web benchmark platform demonstrating side-by-side performance of **Gemini 3.7 Flash** in **Static** (`media_processing="static"`) vs **Agentic** (`media_processing="agentic"`) video understanding mode.

```
+-----------------------------------------------------------------------------------+
| Browser: React + Vite + Tailwind CSS SPA                                          |
|                                                                                   |
|  [TopNav: Title | Mode Pill | API Status Badge | Settings Modal]                  |
|  +---------------------------+-------------------------------------------------+  |
|  | Left Input Panel          | Right Side-by-Side Comparison Panel             |  |
|  | - Video Selector (Preset/ | - Baseline Card (Static, Gray, Tokens in/out,   |  |
|  |   YouTube URL)            |   Markdown response, Stopwatch timer)           |  |
|  | - Video Preview Player    | - Agentic Card (Agentic, Blue outline, Tokens   |  |
|  | - Metadata info badge     |   in/out/thought, Markdown, Stopwatch timer)    |  |
|  | - Prompt textarea & clear | - Floating Callout (Total & Input Token Savings)|  |
|  | - Start analysis button   |                                                 |  |
|  +---------------------------+-------------------------------------------------+  |
+----------------------------------------+------------------------------------------+
                                         | HTTP REST API
                                         v
+-----------------------------------------------------------------------------------+
| Backend: FastAPI (Python 3.13, Uvicorn on 0.0.0.0:8000)                           |
|                                                                                   |
|  - GET  /api/health            -> Status check {"status": "ok"}                   |
|  - GET  /api/settings          -> Check configured credentials & active provider  |
|  - GET  /api/preset            -> Video metadata for I/O Keynote demo clip        |
|  - GET  /api/preset/video      -> Stream local MP4 / range-supported clip         |
|  - POST /api/analyze           -> Concurrent dual analysis via asyncio.gather:    |
|                                     * Static baseline call                        |
|                                     * Agentic call                                |
|  - Static Files Mount (/)      -> Serves frontend/dist for single-server delivery  |
+----------------------------------------+------------------------------------------+
                                         | google-genai SDK (v1beta1)
                                         v
+-----------------------------------------------------------------------------------+
| Google GenAI Platform (Gemini 3.7 Flash)                                          |
| - Gemini Developer API (api_key) OR Vertex AI (project, location)                 |
| - Baseline: types.Part(file_data=..., media_processing="static")                  |
| - Agentic:  types.Part(file_data=..., media_processing="agentic")                 |
| - Metrics: prompt_token_count, candidates_token_count, thoughts_token_count       |
+-----------------------------------------------------------------------------------+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | FastAPI Base Application | Initialize FastAPI app, CORS, error handling, health check endpoint (`/api/health`) | M1: Backend API | ORIGINAL_REQUEST §R1 |
| 2 | GenAI Client Factory & Credential Provider | Dynamic authentication via environment variables (`GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT`) or custom headers/payload | M1: Backend API | ORIGINAL_REQUEST §R1 |
| 3 | Dual Parallel Analysis Engine | Concurrent execution of static vs agentic video calls using `asyncio.gather` and `client.aio.models.generate_content` | M1: Backend API | ORIGINAL_REQUEST §R1 |
| 4 | Token Telemetry Extractor | Accurate extraction of `total_token_count`, `prompt_token_count`, `candidates_token_count`, `thoughts_token_count`, and wall-clock latency | M1: Backend API | ORIGINAL_REQUEST §R1 |
| 5 | Preset Metadata & Video Serving | Preset metadata endpoint (`/api/preset`) and cached streaming endpoint for Google I/O keynote clip | M1: Backend API | ORIGINAL_REQUEST §R1 |
| 6 | React + Vite + Tailwind Setup | Scaffold modern SPA with responsive layout, icons (`lucide-react`), and markdown renderer | M2: Frontend UI | ORIGINAL_REQUEST §R2 |
| 7 | Top Navigation Bar & Settings Modal | Header with status pills, live credential indicator, and modal to configure API keys / Vertex AI credentials | M2: Frontend UI | ORIGINAL_REQUEST §R2 |
| 8 | Video Input & Preview Player | Preset selector (Search + Shopping, Antigravity) + YouTube URL input, HTML5 video player, metadata badge | M2: Frontend UI | ORIGINAL_REQUEST §R2 |
| 9 | Prompt Controller & Action Button | Prompt textarea with clear button, preset suggestions, and dark pill Start Analysis button | M2: Frontend UI | ORIGINAL_REQUEST §R2 |
| 10 | SxS Comparison Cards & Stopwatches | Side-by-side Baseline vs Agentic cards, independent real-time stopwatches, formatted responses | M2: Frontend UI | ORIGINAL_REQUEST §R2 |
| 11 | Token Reduction Callout Badge | Dynamic badge displaying overall token savings and input token reduction percentage | M2: Frontend UI | ORIGINAL_REQUEST §R2 |
| 12 | Unified Packaging (`run.sh`) | Single script to install Python/npm dependencies, build frontend, and launch FastAPI on `0.0.0.0:8000` | M3: Integration | ORIGINAL_REQUEST §R3 |
| 13 | Static Asset Serving & SPA Routing | Mount `frontend/dist` on root `/` with fallback route handling in FastAPI | M3: Integration | ORIGINAL_REQUEST §R3 |
| 14 | E2E Testing Suite (Tiers 1-4) | Comprehensive test suite covering health, presets, credentials, dual analysis, token math, and UI build | M4: E2E Testing | Acceptance Criteria |
| 15 | Dedicated Preset Service Layer | Thread-safe disk caching, atomic downloads, raw video byte access | M7: Video Ingestion | ORIGINAL_REQUEST §R1 (Follow-up) |
| 16 | Multi-Provider Video Payload Builder | Provider-aware video part construction (raw bytes on Vertex AI, File API on Dev API) | M7: Video Ingestion | ORIGINAL_REQUEST §R2 (Follow-up) |
| 17 | Frontend UX Guardrails | Active provider detection, YouTube warnings on Vertex AI, safe button states | M7: Video Ingestion | ORIGINAL_REQUEST §R3 (Follow-up) |
| 18 | Headless Browser Verification Hardening | Zero error card assertion, positive token telemetry, screenshot capture | M7: Video Ingestion | ORIGINAL_REQUEST §R4 (Follow-up) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend API Service | FastAPI server, google-genai integration, parallel static/agentic analysis, token telemetry, preset endpoints | None | DONE |
| M2 | Frontend Application | React SPA, Vite, Tailwind CSS, TopNav, Settings modal, Video preview, SxS comparison cards, stopwatches, savings badge | M1 (contracts) | DONE |
| M3 | Packaging & Integration | `run.sh` script, frontend build pipeline, static file serving on `0.0.0.0:8000`, environment configuration | M1, M2 | DONE |
| M4 | E2E Verification & Audit | Opaque-box E2E test execution, adversarial edge-case hardening, forensic audit verification | M1, M2, M3 | DONE |
| M7 | Multi-Provider Video Ingestion & GCS 403 Fix | Preset service, inline_data for Vertex, File API for Dev API, UX guardrails, hardened headless E2E | M1, M2, M3, M4 | DONE |

## Interface Contracts

### 1. `POST /api/analyze`
**Request Body**:
```json
{
  "video_url": "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/KW_SxS-needle_Blog_V1.mp4",
  "video_source_type": "preset" | "url" | "youtube",
  "prompt": "What is the third logo in the second row of the Universal Commerce Protocol (UCP) partners slide?",
  "credentials": {
    "api_key": "optional_gemini_api_key",
    "project": "optional_vertex_project",
    "location": "optional_vertex_location"
  }
}
```

**Response Body**:
```json
{
  "baseline": {
    "model": "gemini-3.7-flash",
    "media_processing": "static",
    "text": "The third logo in the second row is...",
    "execution_time_seconds": 21.45,
    "tokens": {
      "total": 127628,
      "prompt": 126344,
      "candidates": 55,
      "thoughts": 0
    }
  },
  "agentic": {
    "model": "gemini-3.7-flash",
    "media_processing": "agentic",
    "text": "Based on the UCP partners slide...",
    "execution_time_seconds": 29.12,
    "tokens": {
      "total": 94962,
      "prompt": 4629,
      "candidates": 165,
      "thoughts": 90168
    }
  },
  "savings": {
    "total_reduction_percent": 25.6,
    "input_reduction_percent": 96.3,
    "prompt_tokens_saved": 121715
  }
}
```

### 2. `GET /api/preset`
**Response Body**:
```json
{
  "presets": [
    {
      "id": "io-2026-ucp",
      "title": "Search + Shopping | I/O 2026 Keynote",
      "subtitle": "Universal Commerce Protocol (UCP) slide benchmark",
      "size_mb": 25.90,
      "mime_type": "video/mp4",
      "duration_seconds": 58.67,
      "video_url": "/api/preset/video",
      "default_prompt": "What is the third logo in the second row of the Universal Commerce Protocol (UCP) partners slide and who is presenting that slide?"
    },
    {
      "id": "antigravity-locomotive",
      "title": "Google Antigravity I/O Keynote",
      "subtitle": "OS terminal demo clip",
      "size_mb": 25.90,
      "mime_type": "video/mp4",
      "duration_seconds": 58.67,
      "video_url": "/api/preset/video",
      "default_prompt": "In the OS terminal demo, what is the utility being used to display the locomotive?"
    }
  ]
}
```

### 3. `GET /api/settings`
**Response Body**:
```json
{
  "active_provider": "gemini_api_key" | "vertex_ai" | "none",
  "has_gemini_api_key": true,
  "has_vertex_project": false,
  "vertex_project": null,
  "vertex_location": null
}
```

### 4. `GET /api/health`
**Response Body**:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

## Code Layout
```
./
├── README.md                           # Project overview, architecture & quick start
├── PROJECT.md                          # Global architectural index and contracts
├── run.sh                              # Unified single-script installer, builder & runner
├── backend/
│   ├── requirements.txt                # Python dependencies (google-genai>=2.21.0, fastapi, uvicorn, etc.)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point & static asset mounting
│   │   ├── config.py                   # Environment settings & credentials resolution
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── analyze.py              # POST /api/analyze parallel execution
│   │   │   ├── preset.py               # GET /api/preset & video stream
│   │   │   └── settings.py             # GET /api/settings & health
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── genai_client.py         # Google GenAI client factory (Vertex AI / Dev API)
│   │   │   └── video_analyzer.py       # Dual parallel analysis engine with timing & metrics
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── analyze.py              # Pydantic request/response schemas
│   │       └── preset.py               # Preset metadata schemas
│   └── tests/
│       ├── test_api.py                 # Backend unit & integration tests
│       └── test_video_analyzer.py      # Telemetry & parsing verification tests
├── frontend/
│   ├── package.json                    # Node dependencies (react, vite, tailwindcss, lucide-react)
│   ├── vite.config.ts                  # Vite build configuration (output to dist)
│   ├── tailwind.config.js              # Tailwind styling configuration
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                     # Main layout & dual analysis state container
│       ├── components/
│       │   ├── TopNav.tsx              # Navigation bar, status pills & settings trigger
│       │   ├── SettingsModal.tsx       # Dynamic credential configuration dialog
│       │   ├── VideoInputPanel.tsx     # Presets, URL input, preview player, prompt textarea
│       │   ├── VideoPlayer.tsx         # HTML5 / YouTube iframe wrapper
│       │   ├── ComparisonPanel.tsx     # Side-by-Side container
│       │   ├── BaselineCard.tsx        # Neutral card, tokens, stopwatch, response
│       │   ├── AgenticCard.tsx         # Blue highlighted card, tokens, stopwatch, response
│       │   ├── SavingsCallout.tsx      # Token reduction overlay callout badge
│       │   └── Stopwatch.tsx           # High-precision millisecond-accurate timer
│       ├── services/
│       │   └── api.ts                  # Backend API client
│       └── types/
│           └── index.ts                # TypeScript interfaces for API contracts
└── tests/
    └── e2e/
        ├── run_e2e.sh                  # Comprehensive E2E test runner
        └── test_full_flow.py           # Opaque-box E2E tests for API and UI assets
```
