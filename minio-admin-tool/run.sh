#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOTSTRAP_SCRIPT="${1:-${SCRIPT_DIR}/shared/bootstrap-minio-user-bucket.sh}"

if [ ! -f "${BOOTSTRAP_SCRIPT}" ]; then
  echo "Bootstrap script not found: ${BOOTSTRAP_SCRIPT}" >&2
  exit 1
fi

if [ ! -f "${SCRIPT_DIR}/.env" ]; then
  echo "Missing .env in ${SCRIPT_DIR}. Copy .env.example and fill values." >&2
  exit 1
fi

cd "${SCRIPT_DIR}"
docker compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d minio
docker compose -f "${SCRIPT_DIR}/docker-compose.yml" \
  run --rm \
  -v "${BOOTSTRAP_SCRIPT}:/tmp/bootstrap.sh:ro" \
  --entrypoint /bin/sh \
  mc -c "sh /tmp/bootstrap.sh"
