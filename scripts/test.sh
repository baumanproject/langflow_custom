#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/scripts/up.sh"

cd "${ROOT_DIR}/tests"
cp -n .env.example .env || true
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
pytest -q

cd "${ROOT_DIR}"
docker compose exec -T langflow python -m pytest -q /app/tests
