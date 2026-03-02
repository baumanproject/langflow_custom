from __future__ import annotations

import base64

import pytest

from lfx.schema import Data

from components.s3.s3_upload import S3Upload, S3UploadInput, S3UploadOutput
from tests.helpers.component_test_base import (
    ComponentTestBaseWithoutClient,
    normalize_component_run_result,
)
from tests.helpers.s3_fakes import FakeS3Backend, install_fake_s3_session


@pytest.mark.asyncio
class TestS3Upload(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return S3Upload

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

    async def test_upload_runs_and_returns_contract(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload", backend)

        payload = b"upload payload"
        component_instance.data = Data(
            data=S3UploadInput(
                name="hello.txt",
                folder="nested",
                base64=base64.b64encode(payload).decode("utf-8"),
                mime="text/plain",
            )
        )

        result = normalize_component_run_result(await component_instance.run())
        uploaded = (
            S3UploadOutput.model_validate(result)
            if hasattr(S3UploadOutput, "model_validate")
            else S3UploadOutput.parse_obj(result)
        )

        assert uploaded.bucket == "unit-tests-bucket"
        assert uploaded.key == "nested/hello.txt"
        assert uploaded.size_bytes == len(payload)
        assert backend.store["unit-tests-bucket"]["nested/hello.txt"][0] == payload

    async def test_upload_validates_payload(self, component_instance):
        component_instance.data = Data(data={})
        with pytest.raises(ValueError, match="or data_url"):
            await component_instance.run()

    async def test_upload_no_credentials(self, component_instance, monkeypatch):
        backend = FakeS3Backend(behavior="bad_credentials")
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload", backend)
        component_instance.data = Data(
            data=S3UploadInput(name="a.txt", base64=base64.b64encode(b"x").decode("utf-8"))
        )
        with pytest.raises(PermissionError):
            await component_instance.run()

    async def test_upload_timeout_raises(self, component_instance, monkeypatch):
        backend = FakeS3Backend(behavior="timeout")
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload", backend)
        component_instance.data = Data(
            data=S3UploadInput(name="a.txt", base64=base64.b64encode(b"x").decode("utf-8"))
        )
        with pytest.raises(TimeoutError):
            await component_instance.run()
