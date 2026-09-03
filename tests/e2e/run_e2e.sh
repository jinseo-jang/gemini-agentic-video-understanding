#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

echo "========================================================================"
echo "    Gemini 3.7 Flash Video Benchmark: 4-Tier E2E Test Suite Runner     "
echo "========================================================================"

# Detect Python/pytest environment
PYTEST_CMD=""
if [ -f "${REPO_ROOT}/.venv/bin/pytest" ]; then
    PYTEST_CMD="${REPO_ROOT}/.venv/bin/pytest"
    echo "[INFO] Using virtualenv pytest: ${PYTEST_CMD}"
elif command -v pytest &>/dev/null; then
    PYTEST_CMD="pytest"
    echo "[INFO] Using system pytest: $(which pytest)"
elif [ -f "${REPO_ROOT}/.venv/bin/python3" ]; then
    PYTEST_CMD="${REPO_ROOT}/.venv/bin/python3 -m pytest"
    echo "[INFO] Using virtualenv python3 -m pytest"
elif command -v python3 &>/dev/null; then
    PYTEST_CMD="python3 -m pytest"
    echo "[INFO] Using system python3 -m pytest"
else
    echo "[ERROR] Neither pytest nor python3 found in PATH or .venv."
    exit 1
fi

export TEST_BASE_URL="${TEST_BASE_URL:-http://127.0.0.1:8000}"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

echo "[INFO] Working Directory: ${REPO_ROOT}"
echo "[INFO] Target Base URL:   ${TEST_BASE_URL}"
echo "------------------------------------------------------------------------"

# Run pytest on the E2E suite
set +e
${PYTEST_CMD} -v "${SCRIPT_DIR}" "$@"
TEST_EXIT_CODE=$?
set -e

echo "------------------------------------------------------------------------"
if [ ${TEST_EXIT_CODE} -eq 0 ]; then
    echo "[SUCCESS] All E2E test suites passed successfully (exit code 0)."
else
    echo "[FAILURE] E2E test suite failed with exit code ${TEST_EXIT_CODE}."
fi
echo "========================================================================"

exit ${TEST_EXIT_CODE}
