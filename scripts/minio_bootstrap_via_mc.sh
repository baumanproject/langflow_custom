#!/usr/bin/env sh
set -eu

MINIO_ENV_FILE="${1:-services/minio/.env}"
MC_IMAGE="${MC_IMAGE:-minio/mc:latest}"
MC_NETWORK="${MC_NETWORK:-platform}"
MC_ALIAS="${MC_ALIAS:-local}"

# shell defaults (can be overridden in env or by file)
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
MINIO_S3_USER="${MINIO_S3_USER:-minio_s3_user}"
MINIO_S3_PASSWORD="${MINIO_S3_PASSWORD:-minio_s3_password}"
MINIO_BUCKET="${MINIO_BUCKET:-langflow-s3-bucket}"
MINIO_BUCKET_TTL_DAYS="${MINIO_BUCKET_TTL_DAYS:-30}"
MINIO_BUCKET_QUOTA="${MINIO_BUCKET_QUOTA:-100GiB}"
MINIO_BUCKET_POLICY_NAME="${MINIO_BUCKET_POLICY_NAME:-s3-${MINIO_BUCKET}-rw}"

if [ -f "${MINIO_ENV_FILE}" ]; then
  # shellcheck disable=SC1090
  . "${MINIO_ENV_FILE}"
fi

: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required (set env or in ${MINIO_ENV_FILE})}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required (set env or in ${MINIO_ENV_FILE})}"

TMP_SCRIPT="$(mktemp)"
trap 'rm -f "${TMP_SCRIPT}"' EXIT

cat > "${TMP_SCRIPT}" <<'EOF'
set -eu

wait_for_minio() {
  for _ in $(seq 1 60); do
    if mc alias set "${MC_ALIAS}" "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/tmp/alias.log 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "MinIO is not reachable. Last response:"
  cat /tmp/alias.log
  exit 1
}
}

ensure_bucket() {
  mc mb --ignore-existing "${MC_ALIAS}/${MINIO_BUCKET}"
}

ensure_user() {
  if mc admin user info "${MC_ALIAS}" "${MINIO_S3_USER}" >/dev/null 2>&1; then
    echo "User ${MINIO_S3_USER} exists."
  else
    echo "Create user ${MINIO_S3_USER}."
    mc admin user add "${MC_ALIAS}" "${MINIO_S3_USER}" "${MINIO_S3_PASSWORD}"
  fi
}

ensure_policy() {
  POLICY_FILE="/tmp/${MINIO_BUCKET_POLICY_NAME}.json"
  cat > "${POLICY_FILE}" <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:ListBucketMultipartUploads"
      ],
      "Resource": "arn:aws:s3:::${MINIO_BUCKET}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:AbortMultipartUpload",
        "s3:CreateMultipartUpload",
        "s3:DeleteObject",
        "s3:GetObject",
        "s3:ListMultipartUploadParts",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::${MINIO_BUCKET}/*"
    }
  ]
}
POLICY

  if mc admin policy info "${MC_ALIAS}" "${MINIO_BUCKET_POLICY_NAME}" >/dev/null 2>&1; then
    echo "Policy ${MINIO_BUCKET_POLICY_NAME} exists."
  else
    echo "Create policy ${MINIO_BUCKET_POLICY_NAME}."
    mc admin policy create "${MC_ALIAS}" "${MINIO_BUCKET_POLICY_NAME}" "${POLICY_FILE}"
  fi

  mc admin policy attach "${MC_ALIAS}" "${MINIO_BUCKET_POLICY_NAME}" --user "${MINIO_S3_USER}"
}

set_quota() {
  mc quota set --size "${MINIO_BUCKET_QUOTA}" "${MC_ALIAS}/${MINIO_BUCKET}" \
    || mc admin bucket quota --hard "${MC_ALIAS}/${MINIO_BUCKET}" "${MINIO_BUCKET_QUOTA}" \
    || mc admin bucket quota "${MC_ALIAS}/${MINIO_BUCKET}" --hard "${MINIO_BUCKET_QUOTA}"
}

set_ttl() {
  mc ilm add "${MC_ALIAS}/${MINIO_BUCKET}" --expire-days "${MINIO_BUCKET_TTL_DAYS}" \
    || mc ilm add "${MC_ALIAS}/${MINIO_BUCKET}" --expiry-days "${MINIO_BUCKET_TTL_DAYS}" \
    || mc ilm rule add "${MC_ALIAS}/${MINIO_BUCKET}" --expire-days "${MINIO_BUCKET_TTL_DAYS}" \
    || {
      ILM_FILE="/tmp/ilm.json"
      printf '%s\n' \
"{" \
'  "Rules": [' \
"    {" \
"      \"ID\": \"expire-after-${MINIO_BUCKET_TTL_DAYS}-days\"," \
"      \"Status\": \"Enabled\"," \
"      \"Expiration\": { \"Days\": ${MINIO_BUCKET_TTL_DAYS} }" \
"    }" \
"  ]" \
"}" > "${ILM_FILE}"
      mc ilm import "${MC_ALIAS}/${MINIO_BUCKET}" "${ILM_FILE}"
    }
}

main() {
  wait_for_minio
  ensure_bucket
  ensure_user
  ensure_policy
  set_quota
  set_ttl
}

main
EOF

docker run --rm \
  --network "${MC_NETWORK}" \
  -v "${TMP_SCRIPT}:/bootstrap.sh:ro" \
  -e MINIO_ENDPOINT="${MINIO_ENDPOINT}" \
  -e MC_ALIAS="${MC_ALIAS}" \
  -e MINIO_ROOT_USER="${MINIO_ROOT_USER}" \
  -e MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD}" \
  -e MINIO_S3_USER="${MINIO_S3_USER}" \
  -e MINIO_S3_PASSWORD="${MINIO_S3_PASSWORD}" \
  -e MINIO_BUCKET="${MINIO_BUCKET}" \
  -e MINIO_BUCKET_TTL_DAYS="${MINIO_BUCKET_TTL_DAYS}" \
  -e MINIO_BUCKET_QUOTA="${MINIO_BUCKET_QUOTA}" \
  -e MINIO_BUCKET_POLICY_NAME="${MINIO_BUCKET_POLICY_NAME}" \
  "${MC_IMAGE}" sh /bootstrap.sh
