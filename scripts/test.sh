#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/scripts/up.sh"

cd "${ROOT_DIR}/tests"
cp -n .env.example .env || true
if [ ! -d ".venv" ]; then
  uv venv .venv
fi
source .venv/bin/activate
uv pip install -r requirements.txt
uv run pytest -q

cd "${ROOT_DIR}"
