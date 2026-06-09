#!/usr/bin/env bash
set -euo pipefail

echo "[financial-pdf-parse-doubao-eval] Checking Linux/macOS environment"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: python is not available on PATH"
  return 1 2>/dev/null || exit 1
fi

"${PYTHON_BIN}" --version
"${PYTHON_BIN}" -m pip --version >/dev/null
"${PYTHON_BIN}" -m pip install --upgrade las-sdk

if command -v lasutil >/dev/null 2>&1; then
  lasutil --version || true
else
  echo "WARNING: lasutil is not on PATH after las-sdk installation."
fi

if command -v jq >/dev/null 2>&1; then
  jq --version
else
  echo "WARNING: jq is not installed. Python scripts do not require jq."
fi

if [ -z "${LAS_API_KEY:-}" ]; then
  echo 'LAS_API_KEY is not set. Use: export LAS_API_KEY="..."'
fi
if [ -z "${LAS_REGION:-}" ]; then
  echo 'LAS_REGION is not set. Recommended: export LAS_REGION="cn-beijing"'
fi

echo "[financial-pdf-parse-doubao-eval] Done. No permanent env vars were modified."
