#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cp -n "${ROOT_DIR}/services/minio/.env.example" "${ROOT_DIR}/services/minio/.env" || true
cp -n "${ROOT_DIR}/services/langflow/.env.example" "${ROOT_DIR}/services/langflow/.env" || true
cp -n "${ROOT_DIR}/tests/.env.example" "${ROOT_DIR}/tests/.env" || true

cd "${ROOT_DIR}"
docker compose up -d --build
