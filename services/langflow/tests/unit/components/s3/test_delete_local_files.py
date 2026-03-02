from __future__ import annotations

import pytest

from components.s3.delete_local_files import DeleteLocalFiles
from tests.helpers.component_test_base import (
    ComponentTestBaseWithoutClient,
    normalize_component_run_result,
)


@pytest.mark.asyncio
class TestDeleteLocalFiles(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return DeleteLocalFiles

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def default_kwargs(self):
        return {}

    async def test_delete_local_files_removes_existing(self, component_instance, tmp_path):
        first = tmp_path / "a.txt"
        second = tmp_path / "b.txt"
        first.write_text("a")
        second.write_text("b")

        component_instance.files_data = {"file_paths": [str(first), str(second)]}
        result = normalize_component_run_result(await component_instance.run())

        assert result["deleted"] == [str(first), str(second)]
        assert result["errors"] == []
        assert not first.exists()
        assert not second.exists()

    async def test_delete_local_files_collects_missing(self, component_instance):
        component_instance.files_data = {"file_paths": ["/tmp/not-exists-9999.txt"]}
        result = normalize_component_run_result(await component_instance.run())
        assert result["deleted"] == []
        assert result["errors"][0]["ok"] is False

    async def test_delete_local_files_single_file_path_alias(self, component_instance, tmp_path):
        file_path = tmp_path / "single.txt"
        file_path.write_text("value")

        component_instance.files_data = {"file_path": str(file_path)}
        result = normalize_component_run_result(await component_instance.run())

        assert result["deleted"] == [str(file_path)]
        assert result["errors"] == []
