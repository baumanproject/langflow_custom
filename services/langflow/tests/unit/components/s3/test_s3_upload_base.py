from __future__ import annotations

import pytest

from components.s3.s3_upload_base import S3UploadBase
from tests.helpers.component_test_base import ComponentTestBaseWithoutClient
from tests.helpers.component_test_base import normalize_component_run_result
from tests.helpers.s3_fakes import FakeS3Backend, install_fake_s3_session


@pytest.mark.asyncio
class TestS3UploadBase(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return S3UploadBase

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
            "s3_folder": "uploaded",
        }

    async def test_upload_base_uploads_multiple_files(self, component_instance, monkeypatch, tmp_path):
        first = tmp_path / "one.txt"
        second = tmp_path / "two.txt"
        first.write_text("one")
        second.write_text("two")

        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload_base", backend)
        component_instance.files = [str(first), str(second)]

        result = normalize_component_run_result(await component_instance.run())
        assert result["folder"] == "uploaded"
        assert [item["name"] for item in result["files"]] == ["one.txt", "two.txt"]
        assert "uploaded/one.txt" in backend.store["unit-tests-bucket"]
        assert "uploaded/two.txt" in backend.store["unit-tests-bucket"]

    async def test_upload_base_fails_on_empty_files(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload_base", backend)
        component_instance.files = []
        with pytest.raises(ValueError):
            await component_instance.run()

    async def test_upload_base_fails_on_bad_credentials(self, component_instance, monkeypatch, tmp_path):
        first = tmp_path / "one.txt"
        first.write_text("one")

        backend = FakeS3Backend(behavior="bad_credentials")
        install_fake_s3_session(monkeypatch, "components.s3.s3_upload_base", backend)
        component_instance.files = [str(first)]
        with pytest.raises(PermissionError):
            await component_instance.run()
