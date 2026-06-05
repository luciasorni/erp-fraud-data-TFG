#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_DIR="${PROJECT_DIR:-${PROJECT_ROOT}}"
RUN_USER="${RUN_USER:-ubuntu}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_NAME="${SERVICE_NAME:-erp-fraud-api.service}"

echo "INFO: para systemd se usara PROJECT_DIR=${PROJECT_DIR}."

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "ERROR: no existe ${PYTHON_BIN}. Instala python3 y python3-venv." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

chmod +x scripts/run_api_prod.sh

if [[ ! -d ".venv" ]]; then
  "${PYTHON_BIN}" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ ! -f ".env.api.ec2" ]]; then
  cp ".env.api.ec2.example" ".env.api.ec2"
  echo "INFO: creado .env.api.ec2 desde el ejemplo. Revisa la configuracion AWS antes de arrancar."
fi

TMP_SERVICE="$(mktemp)"
sed \
  -e "s#__PROJECT_DIR__#${PROJECT_DIR}#g" \
  -e "s#__RUN_USER__#${RUN_USER}#g" \
  "deploy/erp-fraud-api.service" > "${TMP_SERVICE}"

sudo cp "${TMP_SERVICE}" "/etc/systemd/system/${SERVICE_NAME}"
rm -f "${TMP_SERVICE}"

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

echo "OK: servicio instalado como ${SERVICE_NAME}."
echo "Arranque: sudo systemctl start ${SERVICE_NAME}"
echo "Logs: sudo journalctl -u ${SERVICE_NAME} -f"
