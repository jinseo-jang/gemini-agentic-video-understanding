# Gemini 3.7 Flash Video Benchmark: Static vs Agentic Processing

A web application for benchmarking **Gemini 3.7 Flash** in **Static Video Understanding** (`media_processing="static"`) against **Agentic Video Understanding** (`media_processing="agentic"`).

<p align="center">
  <img src="docs/images/demo_screenshot.png" alt="Gemini 3.7 Flash Video Benchmark Preview" width="100%">
</p>

---

## Overview

In **Agentic Video Understanding**, Gemini 3.7 Flash inspects and navigates video frames on demand through internal tool calls, rather than uniformly sampling the entire video into input tokens up front. As highlighted in the [Google DeepMind announcement](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-agentic-video-in-gemini/), pairing the model's reasoning with dynamic video inspection tools reduces token consumption by up to 88% and lowers costs while improving retrieval accuracy, especially for long-form content.

This application benchmarks the two approaches side by side:
- **Token Usage**: Compares total, prompt, tool frame, and thinking tokens.
- **Latency**: Measures wall-clock execution time with independent timers.
- **Thinking Budget**: Tests configurable thinking levels (`minimal`, `low`, `medium`, `high`).
- **Extraction Quality**: Displays timestamps and descriptions returned by each mode.

For further background on the underlying research and benchmarks, see the official announcement:
- [Introducing Agentic Video Understanding in Gemini (Google Blog)](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-agentic-video-in-gemini/)

---

## Agentic Video API Usage

Using Agentic Video Understanding in the official `google-genai` SDK is straightforward. Specify `media_processing="agentic"` when creating the video `Part`:

```python
from google import genai
from google.genai import types

# 1. Initialize Client (Vertex AI or Gemini Developer API)
client = genai.Client(
    vertexai=True,
    project="your-gcp-project-id",
    location="global",  # Gemini 3.7 Flash requires 'global'
)

# 2. Build Video Part with Agentic Processing
# Supports YouTube URLs, Cloud Storage (gs://), or inline raw bytes
video_part = types.Part(
    file_data=types.FileData(
        file_uri="https://www.youtube.com/watch?v=LzExSq9DU9w",
        mime_type="video/mp4",
    ),
    media_processing="agentic",  # Use "static" for standard baseline
)

# 3. Call Gemini 3.7 Flash with Thinking Budget
response = client.models.generate_content(
    model="gemini-3.7-flash",
    contents=[
        video_part,
        "Summarize the key announcements in this video with timestamps.",
    ],
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.LOW,  # minimal, low, medium, high
            include_thoughts=True,
        )
    ),
)

# 4. Extract Detailed Token Telemetry
usage = response.usage_metadata
print(f"Prompt Tokens (In):     {usage.prompt_token_count}")
print(f"Tool Tokens (Frames):   {usage.tool_use_prompt_token_count}")
print(f"Thinking Tokens:        {usage.thoughts_token_count}")
print(f"Candidate Tokens (Out): {usage.candidates_token_count}")
print(f"Total Tokens:           {usage.total_token_count}")
print(f"\nResponse:\n{response.text}")
```

### Static vs Agentic Processing Modes

| Feature | Static Mode (`media_processing="static"`) | Agentic Mode (`media_processing="agentic"`) |
| :--- | :--- | :--- |
| **Frame Ingestion** | Uniformly samples video at 1 FPS into initial prompt | Low-framerate initial overview, queries frames on demand |
| **Input Prompt Tokens** | Proportional to video duration (~250-300 tokens/sec) | Minimal upfront (~200-300 tokens), plus dynamic tool tokens |
| **Tool Calling** | Disabled | Internal video navigation and frame inspection tools |
| **Optimal Use Case** | Short clips (under 1 minute), fixed-overview tasks | Long-form video (10m to 1h+), needle-in-a-haystack search |

---

## Token Savings Dynamics: Video Duration & Thinking Levels

Token savings between Static and Agentic modes depend on two key factors:

### 1. Video Duration Impact
- **Short Clips (under 2 minutes)**: In static mode, a 1-minute clip costs ~15,000 prompt tokens. Agentic mode uses fewer prompt tokens, but tool queries and thoughts represent a larger relative fraction of total tokens. Total savings are modest.
- **Long-Form Video (10 minutes to 1+ hour)**: In static mode, a 10-minute video consumes ~150,000 prompt tokens and a 1-hour video consumes 900,000+ prompt tokens. In agentic mode, upfront prompt tokens stay under 300 tokens, and the model only fetches the specific frames it needs. This produces **90% to 99%+ input prompt token reduction**, leading to dramatic latency and cost benefits.

### 2. Thinking Budget (`thinking_level`) Impact
- Thinking tokens are counted as reasoning outputs (`thoughts`), separate from input `prompt` tokens.
- **Input Prompt Token Reduction**: Remains consistently high (90% to 99%+) regardless of the thinking level because the video ingestion mechanism is unchanged.
- **Total Token Reduction**: Varies with the thinking budget:
  - `minimal` / `low`: Constrains reasoning tokens, maximizing overall token reduction and minimizing latency.
  - `medium` / `high`: Grants the model deeper reasoning capacity to cross-reference multiple timestamps and synthesize complex answers, which increases thought token count while maintaining prompt token savings.

---

## Quick Start

### Prerequisites
- **Python**: 3.10 or higher
- **Node.js**: 18 or higher (with `npm`)

### 1. Launch with Unified Runner (`run.sh`)
The `run.sh` script sets up the Python virtual environment, installs backend and frontend dependencies, compiles the frontend, and starts the server:

```bash
./run.sh
```

The application builds the frontend bundle and starts the FastAPI server on:
- **Web UI**: [http://localhost:8000](http://localhost:8000)
- **Health Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 2. Configure Credentials
Set credentials through environment variables or directly in the Web UI:

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
Click the **Gear icon** in the top navigation bar to enter your Gemini API Key or Vertex AI Project ID.

---

## Testing & CLI Benchmark

### 1. Standalone CLI Benchmark Script (`scripts/test_agentic_video.py`)
You can measure token savings directly from the command line without launching the web server. The script supports local MP4 files, Google Cloud Storage URIs (`gs://`), and YouTube URLs:

```bash
# Basic run in Agentic mode (default 5-minute demo video)
./.venv/bin/python3 scripts/test_agentic_video.py

# Benchmark a YouTube video side by side (Static vs Agentic)
./.venv/bin/python3 scripts/test_agentic_video.py \
  --video "https://www.youtube.com/watch?v=LzExSq9DU9w" \
  --prompt "Summarize the key topic of this video in 2 sentences." \
  --mode both \
  --thinking-level low

# Benchmark a local video with custom thinking level
./.venv/bin/python3 scripts/test_agentic_video.py \
  --video data/cache/sports_match_10m.mp4 \
  --prompt "At what timestamp does the opening goal happen?" \
  --mode both \
  --thinking-level medium
```

### 2. Backend Unit Tests
Run the pytest suite covering API contracts, video streaming, credentials, and token accounting:

```bash
PYTHONPATH=. .venv/bin/pytest backend/tests -v
```

### End-to-End Browser Tests
Run the Playwright headless browser test suite:

```bash
./tests/e2e/run_headless_e2e.sh
```

---

## License
This project is licensed under the Apache License, Version 2.0.
