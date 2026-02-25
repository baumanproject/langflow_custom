from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Set

import pytest
import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name('.env'))


BASE_URL = os.getenv("TEST_LANGFLOW_BASE_URL", "http://localhost:7860")
API_KEY = os.getenv("TEST_LANGFLOW_API_KEY")


def _headers() -> Dict[str, str]:
    if API_KEY:
        return {"Authorization": f"Bearer {API_KEY}"}
    return {}


def _contains_any(name: str, haystack: Iterable[str]) -> bool:
    return any(name.lower() == item.lower() for item in haystack)


def _extract_component_names(payload: Any, out: Set[str]) -> None:
    if isinstance(payload, dict):
        if "display_name" in payload and isinstance(payload["display_name"], str):
            out.add(payload["display_name"])
        if "name" in payload and isinstance(payload["name"], str):
            out.add(payload["name"])
        for value in payload.values():
            _extract_component_names(value, out)
    elif isinstance(payload, list):
        for value in payload:
            _extract_component_names(value, out)


def wait_for_health() -> None:
    for _ in range(30):
        try:
            response = requests.get(f"{BASE_URL}/health", headers=_headers(), timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise AssertionError("Langflow health endpoint did not become ready")


def test_langflow_health():
    wait_for_health()


def test_langflow_components_visibility():
    wait_for_health()
    for path in ("/api/v1/all", "/api/v1/components", "/api/v1/component/all"):
        response = requests.get(f"{BASE_URL}{path}", headers=_headers(), timeout=10)
        if response.status_code in (200, 301, 302):
            payload = response.json()
            break
    else:
        raise AssertionError("Could not fetch components list from Langflow API")

    names: Set[str] = set()
    _extract_component_names(payload, names)
    assert _contains_any("S3 Upload", names)
    assert _contains_any("S3 Download", names)
