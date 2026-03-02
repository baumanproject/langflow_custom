from __future__ import annotations

import pytest

from components.s3.s3_list import S3ListFiles
from tests.helpers.component_test_base import ComponentTestBaseWithoutClient, normalize_component_run_result
from tests.helpers.s3_fakes import FakeS3Backend, install_fake_s3_session


@pytest.mark.asyncio
class TestS3ListFiles(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return S3ListFiles

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
            "folder": "nested",
        }

    async def test_list_files_for_folder(self, component_instance, monkeypatch):
        backend = FakeS3Backend()
        backend.store["unit-tests-bucket"] = {
            "nested/first.txt": (b"a", None),
            "nested/second.txt": (b"b", None),
            "other/file.txt": (b"c", None),
        }
        install_fake_s3_session(monkeypatch, "components.s3.s3_list", backend)

        files = normalize_component_run_result(await component_instance.run())
        assert files["folder"] == "nested"
        assert files["files"] == ["nested/first.txt", "nested/second.txt"]

    async def test_list_files_missing_credentials(self, component_instance, monkeypatch):
        backend = FakeS3Backend(behavior="bad_credentials")
        install_fake_s3_session(monkeypatch, "components.s3.s3_list", backend)
        with pytest.raises(PermissionError):
            await component_instance.run()

    async def test_list_files_timeout(self, component_instance, monkeypatch):
        backend = FakeS3Backend(behavior="timeout")
        install_fake_s3_session(monkeypatch, "components.s3.s3_list", backend)
        with pytest.raises(TimeoutError):
            await component_instance.run()
