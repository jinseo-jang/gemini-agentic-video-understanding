#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

echo "========================================================================"
echo "    Gemini 3.7 Flash Video Benchmark: Headless Browser E2E Test Runner  "
echo "========================================================================"

# Check Python/venv
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python3"
PIP_BIN="${REPO_ROOT}/.venv/bin/pip"
PYTEST_BIN="${REPO_ROOT}/.venv/bin/pytest"

if [ ! -f "${PYTHON_BIN}" ]; then
    echo "[ERROR] Virtual environment not found at ${REPO_ROOT}/.venv."
    exit 1
fi

# Ensure playwright is installed in .venv
if ! "${PYTHON_BIN}" -c "import playwright" 2>/dev/null; then
    echo "[INFO] Installing playwright into .venv..."
    "${PIP_BIN}" install playwright
fi

# Ensure Google Chrome is available
if ! command -v google-chrome &>/dev/null && [ ! -f "/usr/bin/google-chrome" ]; then
    echo "[ERROR] Google Chrome binary not found at /usr/bin/google-chrome."
    exit 1
fi

export TEST_BASE_URL="${TEST_BASE_URL:-http://127.0.0.1:8000}"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

echo "[INFO] Target URL: ${TEST_BASE_URL}"
echo "[INFO] Executing headless browser test: ${SCRIPT_DIR}/test_headless_browser.py"
echo "------------------------------------------------------------------------"

set +e
"${PYTEST_BIN}" -v -s "${SCRIPT_DIR}/test_headless_browser.py" "$@"
TEST_EXIT_CODE=$?
set -e

echo "------------------------------------------------------------------------"
if [ ${TEST_EXIT_CODE} -eq 0 ]; then
    echo "[SUCCESS] Headless browser E2E test passed successfully!"
    if [ -f "${REPO_ROOT}/headless_e2e_result.png" ]; then
        echo "[ARTIFACT] Screenshot captured at: ${REPO_ROOT}/headless_e2e_result.png ($(stat -c%s "${REPO_ROOT}/headless_e2e_result.png") bytes)"
    fi
else
    echo "[FAILURE] Headless browser E2E test failed with exit code ${TEST_EXIT_CODE}."
fi
echo "========================================================================"

exit ${TEST_EXIT_CODE}
