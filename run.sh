#!/usr/bin/env bash
# ==============================================================================
# Gemini 3.7 Flash Video Benchmark: Unified Runner (run.sh)
#
# Single executable script to bootstrap runtime environment, install dependencies,
# compile frontend static distribution bundle, verify data cache, and serve
# the full-stack application (FastAPI + React SPA) on 0.0.0.0:8000.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
cd "${REPO_ROOT}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
REBUILD_FRONTEND=false
FORWARD_ARGS=()

print_usage() {
    cat << 'EOF'
Usage: ./run.sh [OPTIONS] [-- UVICORN_OPTIONS]

Unified startup script for Gemini 3.7 Flash Video Benchmark full-stack application.
Bootstraps Python virtual environment, validates Node.js runtime, builds frontend
distribution assets, ensures reference video cache, and starts the FastAPI Uvicorn
server bound to 0.0.0.0:8000.

Options:
  --rebuild       Force reinstallation of frontend npm packages and rebuild frontend/dist
  --help, -h      Display this help message and exit

Environment Variables:
  HOST            Bind host (default: 0.0.0.0)
  PORT            Bind port (default: 8000)
  GEMINI_API_KEY  Gemini Developer API Key (optional, can also be configured in UI)
  GOOGLE_CLOUD_PROJECT
                  Google Cloud Project for Vertex AI (optional, configurable in UI)

Uvicorn Pass-Through:
  Any extra arguments (e.g. --reload, --log-level debug) are forwarded directly
  to the uvicorn server.

Examples:
  ./run.sh                    # Standard production launch
  ./run.sh --rebuild          # Force clean rebuild of frontend assets then start
  ./run.sh --reload           # Launch with server auto-reload for development
  PORT=8080 ./run.sh          # Bind to custom port 8080
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            print_usage
            exit 0
            ;;
        --rebuild)
            REBUILD_FRONTEND=true
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                FORWARD_ARGS+=("$1")
                shift
            done
            break
            ;;
        *)
            FORWARD_ARGS+=("$1")
            shift
            ;;
    esac
done

echo "=========================================================================="
echo "    Gemini 3.7 Flash Video Benchmark: Unified Runner (run.sh)             "
echo "=========================================================================="

# Step 1: Check runtime dependencies
echo "[1/5] Checking runtime dependencies..."
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is required but not found in PATH." >&2
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo "      Python:  ${PYTHON_VER}"

if ! command -v node &>/dev/null; then
    echo "[ERROR] node is required but not found in PATH." >&2
    exit 1
fi
NODE_VER=$(node -v 2>&1)
echo "      Node.js: ${NODE_VER}"

if ! command -v npm &>/dev/null; then
    echo "[ERROR] npm is required but not found in PATH." >&2
    exit 1
fi
NPM_VER=$(npm -v 2>&1)
echo "      npm:     ${NPM_VER}"

# Step 2: Initialize Python virtual environment (.venv)
echo "[2/5] Preparing Python virtual environment..."
VENV_DIR="${REPO_ROOT}/.venv"
if [ ! -d "${VENV_DIR}" ] || [ ! -f "${VENV_DIR}/bin/python3" ]; then
    echo "      Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
fi

echo "      Ensuring backend dependencies from backend/requirements.txt..."
"${VENV_DIR}/bin/pip" install -q -r "${REPO_ROOT}/backend/requirements.txt"

# Step 3: Ensure frontend distribution bundle
echo "[3/5] Checking frontend production assets..."
FRONTEND_DIR="${REPO_ROOT}/frontend"
FRONTEND_DIST="${FRONTEND_DIR}/dist"

if [ ! -d "${FRONTEND_DIST}" ] || [ ! -f "${FRONTEND_DIST}/index.html" ] || [ "${REBUILD_FRONTEND}" = "true" ]; then
    echo "      Building frontend distribution bundle (npm install && npm run build)..."
    (
        cd "${FRONTEND_DIR}"
        if [ ! -d "node_modules" ] || [ "${REBUILD_FRONTEND}" = "true" ]; then
            echo "      Installing frontend npm dependencies..."
            npm install
        fi
        echo "      Compiling Vite production bundle..."
        npm run build
    )
    echo "      Frontend build complete: ${FRONTEND_DIST}"
else
    echo "      Frontend production build already exists at ${FRONTEND_DIST}."
fi

# Step 4: Ensure reference video cache directory
echo "[4/5] Ensuring reference video cache directory..."
CACHE_DIR="${REPO_ROOT}/data/cache"
mkdir -p "${CACHE_DIR}"
echo "      Cache directory ready: ${CACHE_DIR}"

# Step 5: Launch FastAPI server via Uvicorn
echo "[5/5] Launching Gemini 3.7 Flash Video Benchmark service..."
echo "      Host:       ${HOST}"
echo "      Port:       ${PORT}"
echo "      Web UI:     http://${HOST}:${PORT}"
echo "      Health API: http://${HOST}:${PORT}/api/health"
echo "=========================================================================="

set -- "${FORWARD_ARGS[@]}"
exec "${VENV_DIR}/bin/uvicorn" backend.app.main:app --host "${HOST}" --port "${PORT}" "$@"
