#!/usr/bin/env sh
set -eu

: "${MINIO_HOST:?MINIO_HOST is required}"
: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"
: "${MINIO_S3_USER:?MINIO_S3_USER is required}"
: "${MINIO_S3_PASSWORD:?MINIO_S3_PASSWORD is required}"
: "${MINIO_BUCKET:?MINIO_BUCKET is required}"

MC_ALIAS="${MC_ALIAS:-local}"
MINIO_BUCKET_TTL_DAYS="${MINIO_BUCKET_TTL_DAYS:-30}"
MINIO_BUCKET_QUOTA="${MINIO_BUCKET_QUOTA:-100GiB}"
MINIO_BUCKET_POLICY_NAME="${MINIO_BUCKET_POLICY_NAME:-s3-${MINIO_BUCKET}-rw}"

wait_for_minio() {
  for _ in $(seq 1 60); do
    if mc alias set "${MC_ALIAS}" "${MINIO_HOST}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/tmp/minio-alias.log 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "MinIO is not reachable. Last error:"
  cat /tmp/minio-alias.log
  exit 1
}

ensure_bucket() {
  mc mb --ignore-existing "${MC_ALIAS}/${MINIO_BUCKET}"
}

ensure_user() {
  if mc admin user info "${MC_ALIAS}" "${MINIO_S3_USER}" >/dev/null 2>&1; then
    echo "User exists: ${MINIO_S3_USER}"
  else
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
        "s3:DeleteObject",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::${MINIO_BUCKET}/*"
    }
  ]
}
POLICY

  if mc admin policy info "${MC_ALIAS}" "${MINIO_BUCKET_POLICY_NAME}" >/dev/null 2>&1; then
    echo "Policy exists: ${MINIO_BUCKET_POLICY_NAME}"
  else
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
