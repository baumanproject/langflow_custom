from __future__ import annotations

import base64
from pathlib import Path

import pytest

from lfx.schema import Data

from components.s3.s3_prepare_upload_payload import S3UploadInputBuilder
from tests.helpers.component_test_base import ComponentTestBaseWithoutClient, normalize_component_run_result


@pytest.mark.asyncio
class TestS3UploadInputBuilder(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return S3UploadInputBuilder

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def default_kwargs(self):
        return {
            "name_field": "name",
            "filename_field": "filename",
            "key_field": "key",
            "folder_field": "folder",
            "base64_field": "base64",
            "data_url_field": "data_url",
            "content_field": "content",
            "file_path_field": "file_path",
            "mime_field": "mime",
        }

    async def test_passes_through_s3_upload_contract(self, component_instance):
        payload = {
            "name": "contract.txt",
            "folder": "nested",
            "base64": base64.b64encode(b"hello").decode("utf-8"),
            "mime": "text/plain",
        }
        component_instance.payload = Data(data=payload)
        result = normalize_component_run_result(await component_instance.run())
        assert result["name"] == "contract.txt"
        assert result["folder"] == "nested"
        assert result["base64"] == base64.b64encode(b"hello").decode("utf-8")
        assert result["mime"] == "text/plain"

    async def test_builds_from_content_and_filename(self, component_instance):
        component_instance.payload = Data(
            data={"meta": {"filename": "meta.json", "content": {"foo": "bar"}}}
        )
        component_instance.name_field = "meta.filename"
        component_instance.content_field = "meta.content"
        component_instance.folder_field = "meta_folder"
        component_instance.payload.data["meta_folder"] = "reports"

        result = normalize_component_run_result(await component_instance.run())
        assert result["name"] == "meta.json"
        assert result["folder"] == "reports"
        assert base64.b64decode(result["base64"]) == b'{"foo":"bar"}'

    async def test_builds_from_key_when_name_is_absent(self, component_instance, tmp_path):
        file_path = tmp_path / "payload.txt"
        file_path.write_text("file-content")
        component_instance.payload = Data(data={"item_key": "incoming/file.txt", "file_path": str(file_path)})
        component_instance.name_field = ""  # force key-based resolution
        component_instance.key_field = "item_key"
        component_instance.content_field = ""  # disable content fallback in this path
        component_instance.file_path_field = "file_path"
        component_instance.folder_field = ""  # ignore folder if key is used

        result = normalize_component_run_result(await component_instance.run())
        assert result["key"] == "incoming/file.txt"
        assert "name" not in result
        assert result["base64"] == base64.b64encode(b"file-content").decode("utf-8")
