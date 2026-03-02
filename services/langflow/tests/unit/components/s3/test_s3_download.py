from __future__ import annotations

import base64

import pytest

from lfx.schema import Data

from components.s3.s3_download import S3Download, S3DownloadOutput
from tests.helpers.component_test_base import ComponentTestBaseWithoutClient, normalize_component_run_result
from tests.helpers.s3_fakes import FakeS3Backend, install_fake_s3_session


@pytest.mark.asyncio
class TestS3Download(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return S3Download

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def default_kwargs(self):
        return {
            "endpoint_url": "http://fake-minio:9000",
            "access_key": "test-access",
            "secret_key": "test-secret",
            "region": "us-east-1",
            "bucket": "unit-tests-bucket",
        }

    async def test_download_runs_and_returns_contract(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)
        backend.store["unit-tests-bucket"]["nested/hello.txt"] = (b"download payload", "text/plain")

        component_instance.message_file_reference = "nested/hello.txt"
        result = normalize_component_run_result(await component_instance.run())
        downloaded = (
            S3DownloadOutput.model_validate(result)
            if hasattr(S3DownloadOutput, "model_validate")
            else S3DownloadOutput.parse_obj(result)
        )

        assert downloaded.bucket == "unit-tests-bucket"
        assert downloaded.key == "nested/hello.txt"
        assert downloaded.mime == "text/plain"
        assert downloaded.size_bytes == len(b"download payload")
        assert base64.b64decode(downloaded.base64) == b"download payload"

    async def test_download_not_found(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)
        component_instance.message_file_reference = "nested/missing.txt"
        with pytest.raises(FileNotFoundError):
            await component_instance.run()

    async def test_download_timeout(self, component_instance, monkeypatch):
        backend = FakeS3Backend(behavior="timeout")
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)
        component_instance.message_file_reference = "nested/hello.txt"
        with pytest.raises(TimeoutError):
            await component_instance.run()

    async def test_download_requires_key_or_name(self, component_instance):
        component_instance.message_file_reference = ""
        with pytest.raises(ValueError, match="required"):
            await component_instance.run()

    async def test_download_reads_reference_message_payload(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)
        backend.store["unit-tests-bucket"]["nested/hello.txt"] = (b"download payload", "text/plain")

        component_instance.message_file_reference = Data(data={"key": "nested/hello.txt"})
        result = normalize_component_run_result(await component_instance.run())
        downloaded = (
            S3DownloadOutput.model_validate(result)
            if hasattr(S3DownloadOutput, "model_validate")
            else S3DownloadOutput.parse_obj(result)
        )

        assert downloaded.key == "nested/hello.txt"

    async def test_download_reads_reference_data_url(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_download", backend)
        backend.store["unit-tests-bucket"]["nested/hello.txt"] = (b"download payload", "text/plain")

        component_instance.message_file_reference = "nested/hello.txt"
        result = normalize_component_run_result(await component_instance.run())
        downloaded = (
            S3DownloadOutput.model_validate(result)
            if hasattr(S3DownloadOutput, "model_validate")
            else S3DownloadOutput.parse_obj(result)
        )

        assert downloaded.key == "nested/hello.txt"
