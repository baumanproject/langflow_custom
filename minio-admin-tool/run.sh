#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${MC_MODE:-local}"
if [ "${1-}" != "" ]; then
  MODE="$1"
fi
BOOTSTRAP_SCRIPT="${2:-${SCRIPT_DIR}/shared/bootstrap-minio-user-bucket.sh}"

case "${MODE}" in
  local|remote)
    ;;
  *)
    echo "Usage: bash run.sh [local|remote] [bootstrap_script]" >&2
    echo "  local  - start local minio container from compose and configure it" >&2
    echo "  remote - configure existing external minio from MINIO_HOST, do not touch local minio container" >&2
    exit 1
    ;;
esac

if [ ! -f "${BOOTSTRAP_SCRIPT}" ]; then
  echo "Bootstrap script not found: ${BOOTSTRAP_SCRIPT}" >&2
  exit 1
fi

if [ ! -f "${SCRIPT_DIR}/.env" ]; then
  echo "Missing .env in ${SCRIPT_DIR}. Copy .env.example and fill values." >&2
  exit 1
fi

cd "${SCRIPT_DIR}"

if [ "${MODE}" = "local" ]; then
  docker compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d minio
else
  echo "Remote mode: skipping local minio start; configuring ${MINIO_HOST}"
fi

DOCKER_COMPOSE_RUN_OPTS=""
if [ "${MODE}" = "remote" ]; then
  DOCKER_COMPOSE_RUN_OPTS="--no-deps"
fi

docker compose -f "${SCRIPT_DIR}/docker-compose.yml" \
  run --rm ${DOCKER_COMPOSE_RUN_OPTS} \
  -v "${BOOTSTRAP_SCRIPT}:/tmp/bootstrap.sh:ro" \
  --entrypoint /bin/sh \
  mc -c "sh /tmp/bootstrap.sh"
