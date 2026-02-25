#!/usr/bin/env sh
set -eu

MINIO_HOST="${MINIO_HOST:-http://minio:9000}"

wait_for_minio() {
  echo "Waiting for MinIO at ${MINIO_HOST}..."
  for _ in $(seq 1 60); do
    if mc alias set local "${MINIO_HOST}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/tmp/minio-alias.log 2>&1; then
      echo "MinIO is reachable."
      return 0
    fi
    sleep 2
  done
  echo "MinIO health check failed."
  cat /tmp/minio-alias.log || true
  exit 1
}

ensure_bucket() {
  if mc ls local/${MINIO_BUCKET} >/dev/null 2>&1; then
    echo "Bucket ${MINIO_BUCKET} already exists."
  else
    echo "Creating bucket ${MINIO_BUCKET}."
    mc mb local/${MINIO_BUCKET}
  fi
}

ensure_policy() {
  POLICY_NAME="s3-${MINIO_BUCKET}-rw"
  POLICY_FILE="/tmp/${POLICY_NAME}.json"
  cat >"${POLICY_FILE}" <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": ["arn:aws:s3:::${MINIO_BUCKET}"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": ["arn:aws:s3:::${MINIO_BUCKET}/*"]
    }
  ]
}
POLICY

  if mc admin policy info local "${POLICY_NAME}" >/dev/null 2>&1; then
    echo "Policy ${POLICY_NAME} already exists."
  else
    echo "Creating policy ${POLICY_NAME}."
    mc admin policy create local "${POLICY_NAME}" "${POLICY_FILE}"
  fi
}

ensure_user() {
  if mc admin user info local "${MINIO_S3_USER}" >/dev/null 2>&1; then
    echo "User ${MINIO_S3_USER} already exists."
  else
    echo "Creating user ${MINIO_S3_USER}."
    mc admin user add local "${MINIO_S3_USER}" "${MINIO_S3_PASSWORD}"
  fi

  POLICY_NAME="s3-${MINIO_BUCKET}-rw"
  echo "Attaching policy ${POLICY_NAME} to ${MINIO_S3_USER}."
  mc admin policy attach local "${POLICY_NAME}" --user "${MINIO_S3_USER}"
}

seed_images() {
  SEED_IMAGES_DIR="/images"
  if [ ! -d "${SEED_IMAGES_DIR}" ]; then
    echo "Seed image directory ${SEED_IMAGES_DIR} not found. Skipping seed upload."
    return 0
  fi

  if ! ls "${SEED_IMAGES_DIR}" >/dev/null 2>&1; then
    echo "Seed image directory ${SEED_IMAGES_DIR} is empty. Skipping seed upload."
    return 0
  fi

  echo "Uploading seed images to ${MINIO_BUCKET}/images/"
  mc cp --recursive "${SEED_IMAGES_DIR}/" "local/${MINIO_BUCKET}/images/"
}

wait_for_minio
ensure_bucket
ensure_policy
ensure_user
seed_images

echo "MinIO init completed."
