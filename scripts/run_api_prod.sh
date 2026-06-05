#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if [[ -f "${PROJECT_ROOT}/.env.api.ec2" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env.api.ec2"
  set +a
fi

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

API_HOST="${ERP_FRAUD_API_HOST:-127.0.0.1}"
API_PORT="${ERP_FRAUD_API_PORT:-8000}"
PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_EXEC}" ]]; then
  PYTHON_EXEC="python"
fi

exec "${PYTHON_EXEC}" -m uvicorn app.api.main:app \
  --host "${API_HOST}" \
  --port "${API_PORT}"
