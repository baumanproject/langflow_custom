#!/usr/bin/env sh
set -eu

MINIO_HOST="${MINIO_HOST:-http://minio:9000}"
MINIO_ALIAS="${MINIO_ALIAS:-local}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:?MINIO_ROOT_USER required}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD required}"
MINIO_S3_USER="${MINIO_S3_USER:?MINIO_S3_USER required}"
MINIO_S3_PASSWORD="${MINIO_S3_PASSWORD:?MINIO_S3_PASSWORD required}"
MINIO_BUCKET="${MINIO_BUCKET:?MINIO_BUCKET required}"
POLICY_NAME="${MINIO_BUCKET_POLICY_NAME:-s3-${MINIO_BUCKET}-rw}"
MINIO_BUCKET_TTL_DAYS="${MINIO_BUCKET_TTL_DAYS:-30}"
MINIO_BUCKET_QUOTA="${MINIO_BUCKET_QUOTA:-100GiB}"

wait_for_minio() {
  echo "Waiting for MinIO at ${MINIO_HOST}..."
  for _ in $(seq 1 60); do
    if mc alias set "${MINIO_ALIAS}" "${MINIO_HOST}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/tmp/minio-alias.log 2>&1; then
      echo "MinIO is reachable."
      return 0
    fi
    sleep 2
  done
  cat /tmp/minio-alias.log || true
  echo "MinIO is not reachable."
  exit 1
}

ensure_bucket() {
  echo "Create bucket: ${MINIO_BUCKET}"
  mc mb --ignore-existing "${MINIO_ALIAS}/${MINIO_BUCKET}"
}

ensure_policy() {
  POLICY_FILE="/tmp/${POLICY_NAME}.json"
  cat >"${POLICY_FILE}" <<POLICY
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

  if mc admin policy info "${MINIO_ALIAS}" "${POLICY_NAME}" >/dev/null 2>&1; then
    echo "Policy ${POLICY_NAME} already exists."
  else
    echo "Create policy ${POLICY_NAME}."
    mc admin policy create "${MINIO_ALIAS}" "${POLICY_NAME}" "${POLICY_FILE}"
  fi

  echo "Attach policy ${POLICY_NAME} to user ${MINIO_S3_USER}."
  mc admin policy attach "${MINIO_ALIAS}" "${POLICY_NAME}" --user "${MINIO_S3_USER}"
}

ensure_user() {
  if mc admin user info "${MINIO_ALIAS}" "${MINIO_S3_USER}" >/dev/null 2>&1; then
    echo "User ${MINIO_S3_USER} already exists."
  else
    echo "Create user ${MINIO_S3_USER}."
    mc admin user add "${MINIO_ALIAS}" "${MINIO_S3_USER}" "${MINIO_S3_PASSWORD}"
  fi
}

set_bucket_quota() {
  echo "Set hard quota ${MINIO_BUCKET_QUOTA} for ${MINIO_BUCKET}."
  BUCKET_TARGET="${MINIO_ALIAS}/${MINIO_BUCKET}"

  if mc quota set --size "${MINIO_BUCKET_QUOTA}" "${BUCKET_TARGET}"; then
    return 0
  fi
  if mc quota set "${BUCKET_TARGET}" --size "${MINIO_BUCKET_QUOTA}"; then
    return 0
  fi
  echo "Falling back to legacy quota command (mc admin bucket quota)."
  if mc admin bucket quota --hard "${BUCKET_TARGET}" "${MINIO_BUCKET_QUOTA}"; then
    return 0
  fi
  mc admin bucket quota "${BUCKET_TARGET}" --hard "${MINIO_BUCKET_QUOTA}"
}
    return 0
  fi
  echo "Falling back to legacy quota command."
  mc admin bucket quota "${MINIO_ALIAS}/${MINIO_BUCKET}" --hard "${MINIO_BUCKET_QUOTA}"
}

set_bucket_ttl() {
  echo "Set object TTL ${MINIO_BUCKET_TTL_DAYS} days for ${MINIO_BUCKET}."
  if mc ilm add "${MINIO_ALIAS}/${MINIO_BUCKET}" --expire-days "${MINIO_BUCKET_TTL_DAYS}"; then
    return 0
  fi
  if mc ilm add "${MINIO_ALIAS}/${MINIO_BUCKET}" --expiry-days "${MINIO_BUCKET_TTL_DAYS}"; then
    return 0
  fi
  mc ilm rule add "${MINIO_ALIAS}/${MINIO_BUCKET}" --expire-days "${MINIO_BUCKET_TTL_DAYS}"
}

wait_for_minio
ensure_bucket
ensure_user
ensure_policy
set_bucket_quota
set_bucket_ttl

echo "Done."
