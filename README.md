# Gemini 3.7 Flash Video Benchmark: Static vs Agentic Processing

A full-stack, real-time benchmark application comparing **Gemini 3.7 Flash** in **Static Video Understanding** (`media_processing="static"`) versus **Agentic Video Understanding** (`media_processing="agentic"`).

---

## 🌟 Overview

Google Cloud's **Gemini 3.7 Flash** introduces **Agentic Video Understanding**, allowing the model to autonomously inspect and navigate video frames using adaptive tool calls rather than uniformly sampling the entire video upfront into prompt tokens.

This application provides a side-by-side comparison interface to benchmark:
- **Token Efficiency**: Compares total tokens, prompt tokens, tool use frame tokens, and thought tokens.
- **Latency & Wall-Clock Timing**: Independent real-time stopwatches tracking generation speed.
- **Thinking Intensity**: Configurable thinking levels (`minimal`, `low`, `medium`, `high`).
- **Response Quality**: Formatted Markdown outputs showing extracted information and timestamps.

---

## 🏗️ Architecture

```
+-----------------------------------------------------------------------------------+
| Frontend: React + Vite + Tailwind CSS SPA                                         |
|                                                                                   |
|  [TopNav: Title | Mode Pill | API Status Badge | Settings Modal]                  |
|  +---------------------------+-------------------------------------------------+  |
|  | Left Input Panel          | Right Side-by-Side Comparison Panel             |  |
|  | - Video Preset Selector   | - Baseline Card (Static, Gray, Tokens breakdown)|  |
|  | - Video Preview Player    | - Agentic Card (Agentic, Blue, Tokens breakdown)|  |
|  | - Prompt & Preset Ideas   | - Floating Total Token Reduction Callout        |  |
|  | - Thinking Level Selector | - Independent Real-Time Stopwatches             |  |
|  | - Start Analysis Action   |                                                 |  |
|  +---------------------------+-------------------------------------------------+  |
+----------------------------------------+------------------------------------------+
                                         | HTTP REST API
                                         v
+-----------------------------------------------------------------------------------+
| Backend: FastAPI (Python 3.13 / Uvicorn on 0.0.0.0:8000)                          |
|                                                                                   |
|  - GET  /api/health            -> Service health status                           |
|  - GET  /api/settings          -> Active provider & credential status             |
|  - GET  /api/preset            -> Video metadata for demo clips                   |
|  - GET  /api/preset/video      -> Stream local MP4 (HTTP 206 Range supported)     |
|  - POST /api/analyze           -> Dual parallel generation via asyncio.gather     |
|  - Static Files Mount (/)      -> Serves compiled frontend/dist SPA               |
+-----------------------------------------------------------------------------------+
                                         | google-genai SDK (v1beta1)
                                         v
+-----------------------------------------------------------------------------------+
| Google GenAI Platform (Gemini 3.7 Flash)                                          |
| - Gemini Developer API (API Key) OR Vertex AI (ADC / Project / global location)   |
| - Baseline: media_processing="static"                                             |
| - Agentic:  media_processing="agentic"                                            |
+-----------------------------------------------------------------------------------+
```

---

## 🚀 Quick Start

### Prerequisites
- **Python**: 3.10 or higher
- **Node.js**: 18 or higher (with `npm`)

### 1. Launch with Unified Runner (`run.sh`)
The repository includes a single executable runner (`run.sh`) that automates virtual environment creation, dependency installation, frontend compilation, and server startup:

```bash
./run.sh
```

The application will build the frontend bundle and start the FastAPI server on:
- **Web UI**: [http://localhost:8000](http://localhost:8000)
- **Health Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 2. Configure Credentials
You can provide credentials either via environment variables or directly in the Web UI:

#### Option A: Vertex AI (Recommended)
```bash
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="global"  # Gemini 3.7 Flash requires 'global'
gcloud auth application-default login
./run.sh
```

#### Option B: Gemini Developer API
```bash
export GEMINI_API_KEY="your-gemini-api-key"
./run.sh
```

#### Option C: In-App Settings Modal
Click the **Gear icon** in the top navigation bar to enter your Gemini API Key or Vertex AI Project ID on the fly.

---

## 🧪 Testing

### Backend Unit Tests
Run the 59 automated test suites covering API contracts, preset streaming, credential resolution, and token telemetry:

```bash
PYTHONPATH=. .venv/bin/pytest backend/tests -v
```

### End-to-End Headless Browser Verification
Run the Playwright-driven end-to-end browser verification suite:

```bash
./tests/e2e/run_headless_e2e.sh
```

---

## 📂 Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entry point & static mounting
│   │   ├── config.py                # Environment configuration & credential resolution
│   │   ├── routers/
│   │   │   ├── analyze.py           # Dual static/agentic analysis endpoint
│   │   │   ├── health.py            # Service health checks
│   │   │   ├── preset.py            # Demo video metadata & HTTP 206 streaming
│   │   │   └── settings.py          # Credential status & configuration endpoints
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   └── services/
│   │       ├── genai_client.py      # GenAI client factory & authentication
│   │       ├── preset_service.py    # Demo video caching & byte streaming
│   │       └── video_analyzer.py    # Core analysis runner & token math
│   ├── requirements.txt             # Python backend dependencies
│   └── tests/                       # Pytest backend test suite
├── frontend/
│   ├── src/
│   │   ├── components/              # React components (SxS Cards, Callout, Controls)
│   │   ├── services/                # Backend API client
│   │   ├── types/                   # TypeScript interface definitions
│   │   ├── App.tsx                  # Main layout container
│   │   └── main.tsx                 # React entry point
│   ├── package.json                 # Frontend dependencies & build scripts
│   └── vite.config.ts               # Vite build configuration
├── scripts/
│   └── test_agentic_video.py        # Standalone CLI benchmarking utility
├── tests/
│   ├── adversarial/                 # Edge-case & stress test suite
│   └── e2e/                         # Headless browser & contract E2E tests
├── data/cache/                      # Local video cache directory
├── run.sh                           # Unified runner script
├── PROJECT.md                       # Architectural details and interface contracts
└── README.md                        # Documentation
```

---

## 📄 License
This project is licensed under the Apache License, Version 2.0.
