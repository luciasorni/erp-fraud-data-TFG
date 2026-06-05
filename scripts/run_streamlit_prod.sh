#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if [[ -f "${PROJECT_ROOT}/.env.streamlit.ec2" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env.streamlit.ec2"
  set +a
fi

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

STREAMLIT_HOST="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}"
STREAMLIT_PORT="${STREAMLIT_SERVER_PORT:-8501}"
PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_EXEC}" ]]; then
  PYTHON_EXEC="python"
fi

exec "${PYTHON_EXEC}" -m streamlit run app/ui/Home.py \
  --server.address="${STREAMLIT_HOST}" \
  --server.port="${STREAMLIT_PORT}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
