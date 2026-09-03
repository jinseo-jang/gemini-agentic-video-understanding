# Test Infrastructure Specification: Gemini 3.7 Flash Video Benchmark

## 1. Overview & Testing Philosophy
This document formalizes the End-to-End (E2E) testing infrastructure for the **Gemini 3.7 Flash Video Understanding Benchmark** application. 

The test suite enforces an **opaque-box testing paradigm**:
- Tests interact strictly through public interfaces: HTTP REST endpoints (`/api/*`), HTTP headers, request/response bodies, and production artifact trees (`frontend/dist/`).
- No internal private state or monkey-patching of business logic is permitted during E2E verification.
- Zero-simulation principle: Verification validates real schema contracts, cryptographic/range-based streaming bytes, accurate token arithmetic, and actual compiled assets.

---

## 2. Four-Tier Opaque-Box Test Architecture

```
+---------------------------------------------------------------------------------------+
|                                    E2E TEST SUITE                                     |
+---------------------------------------------------------------------------------------+
|  Tier 1: Feature Coverage                                                             |
|  - Health check endpoint contract (GET /api/health)                                    |
|  - Settings & credential discovery (GET /api/settings)                                |
|  - Preset metadata catalog (GET /api/preset)                                          |
|  - Dual analysis endpoint contract (POST /api/analyze)                                |
|  - Frontend static bundle presence & structure (frontend/dist/index.html)             |
+---------------------------------------------------------------------------------------+
|  Tier 2: Boundary & Corner Cases                                                      |
|  - Empty & whitespace prompts (HTTP 400 / 422 validation)                              |
|  - Malformed JSON request bodies                                                      |
|  - Invalid / unreachable video URIs                                                   |
|  - Unauthenticated / missing credentials behavior                                     |
|  - HTTP Range header streaming (206 Partial Content, Content-Range, 416 Invalid)      |
+---------------------------------------------------------------------------------------+
|  Tier 3: Cross-Feature Interactions                                                   |
|  - Preset catalog -> Default prompt & video URL -> Analyze request workflow           |
|  - Dynamic per-request credentials override isolation (no state leakage across reqs)   |
|  - Multi-preset switching integrity                                                   |
+---------------------------------------------------------------------------------------+
|  Tier 4: Real-World Scenarios                                                         |
|  - End-to-end token telemetry arithmetic verification (input savings %, total savings)|
|  - Invariant validation: total = prompt + candidates + thoughts                       |
|  - Wall-clock execution time non-zero and floating-point validity                     |
|  - Simulated response verification matching keynote baseline numbers                 |
+---------------------------------------------------------------------------------------+
```

### Tier 1: Feature Coverage
Validates the fundamental functional contract of each API and static asset.
1. **`GET /api/health`**:
   - Status code: `200 OK`
   - Content-Type: `application/json`
   - Schema: `{"status": "ok", "version": <string>}`
2. **`GET /api/settings`**:
   - Status code: `200 OK`
   - Schema: includes `active_provider`, `has_gemini_api_key`, `has_vertex_project`, `vertex_project`, `vertex_location`.
3. **`GET /api/preset`**:
   - Status code: `200 OK`
   - Schema: returns a `presets` array containing metadata objects with keys: `id`, `title`, `subtitle`, `size_mb`, `mime_type`, `duration_seconds`, `video_url`, `default_prompt`.
4. **`POST /api/analyze` Contract**:
   - Status code: `200 OK` (when valid credentials/mocks configured) or `400/401/422` with structured error details.
   - Schema verification for both `baseline` (`media_processing="static"`) and `agentic` (`media_processing="agentic"`), including token breakdowns (`total`, `prompt`, `candidates`, `thoughts`) and `savings` (`total_reduction_percent`, `input_reduction_percent`, `prompt_tokens_saved`).
5. **Frontend Static Distribution**:
   - Target file: `frontend/dist/index.html`
   - Assertions: File exists, contains `<div id="root">`, HTML5 doctype, and asset link/script tags (`<script type="module" ...>`).

### Tier 2: Boundary & Corner Cases
Exercises error handlers, validation layers, and stream protocols under adverse conditions.
1. **Validation Rejection**:
   - Empty prompt string (`""` or `"   "`): Returns `422 Unprocessable Entity` or `400 Bad Request`.
   - Missing required fields (e.g. omitted `video_url`): Returns `422 Unprocessable Entity`.
   - Malformed JSON payload: Returns `422 Unprocessable Entity`.
2. **Authentication & Credential Boundaries**:
   - Explicitly empty or invalid API key provided in per-request credentials: Returns structured error or HTTP 400/401 without unhandled 500 server crash.
3. **HTTP Range Request Video Streaming (`GET /api/preset/video`)**:
   - Full request (without Range): `200 OK` or `206 Partial Content`, `Accept-Ranges: bytes`.
   - Range request `bytes=0-1023`: Returns `206 Partial Content`, `Content-Range: bytes 0-1023/<total>`, payload length exactly 1024 bytes.
   - Intermediate Range `bytes=1024-2047`: Returns `206 Partial Content`, payload length exactly 1024 bytes.
   - Unsatisfiable Range `bytes=9999999999-`: Returns `416 Range Not Satisfiable`.

### Tier 3: Cross-Feature Interactions
Tests multi-step state transitions and isolation across features.
1. **Catalog to Analysis Pipeline**:
   - Step 1: Query `GET /api/preset`.
   - Step 2: Extract first preset (`io-2026-ucp`) `video_url` and `default_prompt`.
   - Step 3: Construct `POST /api/analyze` payload using the extracted preset data.
   - Step 4: Verify schema compatibility between preset catalog output and analyze endpoint input.
2. **Dynamic Credential Override Isolation**:
   - Request A passes custom credentials in payload.
   - Request B immediately follows without credentials.
   - Assert Request B falls back to server default environment configuration rather than retaining Request A's custom credentials.

### Tier 4: Real-World Scenarios & Telemetry Math
Verifies mathematical correctness of token savings, latency reporting, and telemetry invariants.
1. **Token Invariant Checks**:
   - Baseline total: `total == prompt + candidates + thoughts`
   - Agentic total: `total == prompt + candidates + thoughts`
   - Input reduction formula:
     $$\text{input\_reduction\_percent} = \frac{\text{baseline.prompt} - \text{agentic.prompt}}{\text{baseline.prompt}} \times 100$$
   - Total reduction formula:
     $$\text{total\_reduction\_percent} = \frac{\text{baseline.total} - \text{agentic.total}}{\text{baseline.total}} \times 100$$
   - Prompt tokens saved:
     $$\text{prompt\_tokens\_saved} = \text{baseline.prompt} - \text{agentic.prompt}$$
2. **Latency Verification**:
   - `execution_time_seconds > 0.0`
   - Type is `float` or numeric representation.

---

## 3. Test Directory Structure

```
tests/
└── e2e/
    ├── __init__.py
    ├── conftest.py                  # Shared fixtures, base URL detection, HTTP client
    ├── test_health_and_settings.py  # Tier 1 & 2: Health check & Settings
    ├── test_presets.py              # Tier 1, 2, 3: Presets & Range streaming
    ├── test_analyze_contract.py     # Tier 1, 2, 3, 4: Analyze schema, validation & math
    ├── test_frontend_assets.py      # Tier 1: Frontend compiled dist bundle
    └── run_e2e.sh                   # Master execution shell script
```

---

## 4. Execution Protocol & Exit Codes

The test suite is driven by `tests/e2e/run_e2e.sh`:
- Runs via standard Python `pytest` runner.
- Supports execution against a live running server (`TEST_BASE_URL=http://localhost:8000`) or via FastAPI `TestClient` in headless mode.
- Exit code `0`: All tests passed.
- Exit code non-zero: Failures encountered with detailed diagnostic output.
