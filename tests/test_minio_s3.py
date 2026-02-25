from __future__ import annotations

import os
import uuid
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name('.env'))


@pytest.fixture(scope="session")
def s3_client():
    endpoint = os.getenv("TEST_MINIO_ENDPOINT_URL")
    access_key = os.getenv("TEST_MINIO_ACCESS_KEY")
    secret_key = os.getenv("TEST_MINIO_SECRET_KEY")
    region = os.getenv("TEST_MINIO_REGION", "us-east-1")

    if not all([endpoint, access_key, secret_key]):
        raise pytest.UsageError("Missing TEST_MINIO_* variables in tests/.env")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=boto3.session.Config(signature_version="s3v4"),
    )


@pytest.fixture(scope="session")
def test_bucket(s3_client):
    bucket = os.getenv("TEST_MINIO_BUCKET", "langflow-s3-bucket")
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)
    return bucket


def test_minio_connectivity(s3_client, test_bucket):
    response = s3_client.list_buckets()
    buckets = {bucket["Name"] for bucket in response.get("Buckets", [])}
    assert test_bucket in buckets


def test_minio_roundtrip(s3_client, test_bucket):
    prefix = os.getenv("TEST_MINIO_OBJECT_PREFIX", "codex")
    key = f"{prefix}/roundtrip-{uuid.uuid4().hex}.bin"
    payload = b"hello-langflow-minio"

    put = s3_client.put_object(Bucket=test_bucket, Key=key, Body=payload)
    assert "ETag" in put

    downloaded = s3_client.get_object(Bucket=test_bucket, Key=key)["Body"].read()
    assert downloaded == payload

    s3_client.delete_object(Bucket=test_bucket, Key=key)


def test_minio_seed_images(s3_client, test_bucket):
    response = s3_client.list_objects_v2(Bucket=test_bucket, Prefix="images/")
    contents = response.get("Contents", []) if response else []
    names = {
        obj.get("Key")
        for obj in contents
        if isinstance(obj.get("Key"), str)
    }

    expected = {"images/python.png", "images/docker.png", "images/aws.png"}
    assert expected.issubset(names), f"Missing seeded images in bucket: {expected - names}"
