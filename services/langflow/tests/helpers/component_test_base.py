from __future__ import annotations

from typing import Any, Dict

import pytest


try:
    from lfx.backend.tests.base.component_test import (
        ComponentTestBaseWithClient,
        ComponentTestBaseWithoutClient,
    )
except Exception:  # pragma: no cover
    class ComponentTestBaseWithoutClient:
        @pytest.fixture
        def component_class(self):  # pragma: no cover
            raise NotImplementedError

        @pytest.fixture
        def default_kwargs(self) -> Dict[str, Any]:
            return {}

        @pytest.fixture
        def file_names_mapping(self):  # pragma: no cover
            return []

        @pytest.fixture
        def component_instance(self, component_class, default_kwargs):
            instance = component_class()
            for key, value in default_kwargs.items():
                setattr(instance, key, value)
            return instance

    class ComponentTestBaseWithClient(ComponentTestBaseWithoutClient):
        pass


def normalize_component_run_result(result: Any, output_name: str = "result") -> Any:
    if hasattr(result, "data"):
        result = result.data

    if hasattr(result, "dict"):
        try:
            result = result.dict()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover
            pass

    if isinstance(result, dict):
        outputs = result
        if "outputs" in result and isinstance(result["outputs"], dict):
            outputs = result["outputs"]
        if output_name in outputs:
            return outputs[output_name]
        raise AssertionError(f"Output '{output_name}' was not found in run result")
    return result
