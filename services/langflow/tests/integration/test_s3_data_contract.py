from __future__ import annotations

import base64

import pytest

from lfx.schema import Data

from components.s3.s3_download import S3Download
from components.s3.s3_list import S3ListFiles
from components.s3.s3_upload import S3Upload
from tests.helpers.component_test_base import normalize_component_run_result
from tests.helpers.s3_fakes import FakeS3Backend, install_fake_s3_session


@pytest.mark.asyncio
class TestS3IntegrationDataContract:
    async def test_upload_download_contract_roundtrip(self, monkeypatch):
        backend = FakeS3Backend()

        upload = S3Upload()
        upload.endpoint_url = "http://fake-minio:9000"
        upload.access_key = "test-access"
        upload.secret_key = "test-secret"
        upload.region = "us-east-1"
        upload.bucket = "unit-tests-bucket"
        upload.data = Data(
            data={
                "name": "contract.txt",
                "folder": "contract",
                "base64": base64.b64encode(b"ok").decode("utf-8"),
            }
        )

        download = S3Download()
        download.endpoint_url = "http://fake-minio:9000"
        download.access_key = "test-access"
        download.secret_key = "test-secret"
        download.region = "us-east-1"
        download.bucket = "unit-tests-bucket"

        install_fake_s3_session(monkeypatch, "components.s3.s3_upload", backend)
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)

        upload_result = normalize_component_run_result(await upload.run())
        assert upload_result["bucket"] == "unit-tests-bucket"
        assert upload_result["key"] == "contract/contract.txt"
        assert upload_result["size_bytes"] == 2

        download.message_file_reference = upload_result["key"]
        download_result = normalize_component_run_result(await download.run())
        assert download_result["bucket"] == "unit-tests-bucket"
        assert download_result["key"] == "contract/contract.txt"
        assert download_result["mime"] in (None, "application/octet-stream", "text/plain")
        assert base64.b64decode(download_result["base64"]) == b"ok"

    async def test_upload_result_output_connects_via_reference_input(self, monkeypatch):
        backend = FakeS3Backend()

        upload = S3Upload()
        upload.endpoint_url = "http://fake-minio:9000"
        upload.access_key = "test-access"
        upload.secret_key = "test-secret"
        upload.region = "us-east-1"
        upload.bucket = "unit-tests-bucket"
        upload.data = Data(
            data={
                "name": "contract.txt",
                "folder": "contract",
                "base64": base64.b64encode(b"ok").decode("utf-8"),
            }
        )

        download = S3Download()
        download.endpoint_url = "http://fake-minio:9000"
        download.access_key = "test-access"
        download.secret_key = "test-secret"
        download.region = "us-east-1"
        download.bucket = "unit-tests-bucket"
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload", backend)
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)

        upload_result = normalize_component_run_result(await upload.run())
        download.message_file_reference = Data(data=upload_result)

        download_result = normalize_component_run_result(await download.run())
        assert download_result["key"] == upload_result["key"]

    async def test_upload_output_feeds_list_filter(self, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload", backend)
        install_fake_s3_session(monkeypatch, "components.s3.s3_list", backend)

        upload = S3Upload()
        upload.endpoint_url = "http://fake-minio:9000"
        upload.access_key = "test-access"
        upload.secret_key = "test-secret"
        upload.region = "us-east-1"
        upload.bucket = "unit-tests-bucket"
        upload.data = Data(
            data={
                "name": "contract.txt",
                "folder": "contract",
                "base64": base64.b64encode(b"ok").decode("utf-8"),
            }
        )
        upload_result = normalize_component_run_result(await upload.run())
        key = upload_result["key"]

        lister = S3ListFiles()
        lister.endpoint_url = "http://fake-minio:9000"
        lister.access_key = "test-access"
        lister.secret_key = "test-secret"
        lister.region = "us-east-1"
        lister.bucket = "unit-tests-bucket"
        lister.folder = "contract"

        list_result = normalize_component_run_result(await lister.run())
        assert key in list_result["files"]
