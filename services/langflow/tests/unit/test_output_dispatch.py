from __future__ import annotations

import asyncio

import pytest

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema import Data

from tests.helpers.component_test_base import (
    ComponentTestBaseWithoutClient,
    normalize_component_run_result,
)


class AsyncProbe(Component):
    display_name = "Async Probe"
    name = "AsyncProbe"
    description = "probe"
    icon = "sparkles"

    outputs = [Output(name="result", method="echo")]

    async def echo(self) -> Data:
        return Data(data={"mode": "async"})


class SyncProbe(Component):
    display_name = "Sync Probe"
    name = "SyncProbe"
    description = "probe"
    icon = "sparkles"

    outputs = [Output(name="result", method="echo")]

    def echo(self) -> Data:
        return Data(data={"mode": "sync"})


@pytest.mark.asyncio
class TestOutputDispatch(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AsyncProbe

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_async_output_method_uses_await(self, component_instance, monkeypatch):
        async def fail_to_thread(*_args, **_kwargs):  # pragma: no cover
            raise AssertionError("sync output method should not be run in to_thread for async path")

        monkeypatch.setattr(asyncio, "to_thread", fail_to_thread)
        result = normalize_component_run_result(await component_instance.run())
        assert result["mode"] == "async"

    async def test_sync_output_method_uses_to_thread(self, monkeypatch):
        calls = {"count": 0}

        original_to_thread = asyncio.to_thread

        async def fake_to_thread(func, *args, **kwargs):
            calls["count"] += 1
            return await original_to_thread(func, *args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

        comp = SyncProbe()
        result = normalize_component_run_result(await comp.run())
        assert calls["count"] >= 1
        assert result["mode"] == "sync"
