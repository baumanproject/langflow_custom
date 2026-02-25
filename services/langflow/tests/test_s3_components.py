from __future__ import annotations

import asyncio
import base64
import os
import uuid
from pathlib import Path

import aioboto3
import boto3
from dotenv import load_dotenv
from lfx.schema import Data

from components.s3.s3_download import S3Download
from components.s3.s3_upload import S3Upload

load_dotenv()


S3_ENDPOINT = os.getenv("TEST_MINIO_ENDPOINT_URL")
S3_ACCESS_KEY = os.getenv("TEST_MINIO_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("TEST_MINIO_SECRET_KEY")
S3_BUCKET = os.getenv("TEST_MINIO_BUCKET", "langflow-s3-bucket")
S3_REGION = os.getenv("TEST_MINIO_REGION", "us-east-1")


async def ensure_bucket() -> None:
    session = aioboto3.Session(
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )
    async with session.client("s3", endpoint_url=S3_ENDPOINT) as client:
        buckets = await client.list_buckets()
        existing = {item["Name"] for item in buckets.get("Buckets", [])}
        if S3_BUCKET not in existing:
            await client.create_bucket(Bucket=S3_BUCKET)


def test_upload_download_roundtrip() -> None:
    assert all([S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET]), "Missing TEST_MINIO_* env vars"

    asyncio.run(ensure_bucket())

    key = f"codex-tests/{uuid.uuid4().hex}.txt"
    payload = b"hello from langflow custom component"

    upload = S3Upload()
    upload.endpoint_url = S3_ENDPOINT
    upload.access_key = S3_ACCESS_KEY
    upload.secret_key = S3_SECRET_KEY
    upload.region = S3_REGION
    upload.bucket = S3_BUCKET
    upload.object_key = key
    upload.input_mode = "base64"
    upload.data = Data(data={"base64": base64.b64encode(payload).decode("utf-8"), "filename": "payload.txt"})

    upload_result = upload.upload()
    assert isinstance(upload_result.data, dict)
    assert upload_result.data["size_bytes"] == len(payload)

    download = S3Download()
    download.endpoint_url = S3_ENDPOINT
    download.access_key = S3_ACCESS_KEY
    download.secret_key = S3_SECRET_KEY
    download.region = S3_REGION
    download.bucket = S3_BUCKET
    download.object_key = key
    download.return_mode = "base64"
    download.include_data_url = True

    download_result = download.download()
    raw = base64.b64decode(download_result.data["base64"])
    assert raw == payload
    assert download_result.data["mime"].startswith("text/")

    # cleanup
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )
    s3.delete_object(Bucket=S3_BUCKET, Key=key)
