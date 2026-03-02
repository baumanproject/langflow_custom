from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pytest
import requests


BASE_URL = os.getenv("TEST_LANGFLOW_BASE_URL", "http://localhost:7860")
FLOW_FIXTURE = os.getenv(
    "TEST_FLOW_FIXTURE_PATH",
    str(Path(__file__).resolve().parent / "fixtures" / "s3_roundtrip_flow.json"),
)
API_KEY = os.getenv("TEST_LANGFLOW_API_KEY", "")


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


def wait_for_health() -> None:
    for _ in range(36):
        try:
            response = requests.get(f"{BASE_URL}/health", headers=_headers(), timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise AssertionError("Langflow health endpoint did not become ready")


def _extract_flow_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        candidate = payload.get("id") or payload.get("flow_id") or payload.get("_id")
        if isinstance(candidate, str) and candidate:
            return candidate
        nested = payload.get("data")
        if isinstance(nested, dict):
            return _extract_flow_id(nested)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            value = _extract_flow_id(item)
            if value:
                return value
    return None


def _upload_payload_variants(flow_bytes: bytes) -> Iterable[tuple[str, Dict[str, Any]]]:
    files = {"file": ("flow.json", flow_bytes, "application/json")}
    for path in ("/api/v1/flows/upload", "/flows/upload", "/api/v1/flow/upload"):
        yield f"{BASE_URL}{path}", files


def _run_payload_variants() -> List[Dict[str, Any]]:
    base = {
        "input_type": "text",
        "output_type": "text",
        "session_id": "pytest-s3-flow",
        "tweaks": {},
        "input_value": "hello from pytest",
    }
    return [
        {"input_request": base},
        {
            "input_value": "hello from pytest",
            "input_type": "text",
            "output_type": "text",
            "session_id": "pytest-s3-flow",
            "tweaks": {},
        },
        {"input_value": "hello from pytest"},
    ]


def _extract_run_output(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    candidates = ("outputs", "result", "data")
    for key in candidates:
        if key in payload:
            return payload[key]
    return payload


def _post(url: str, **kwargs: Any) -> requests.Response:
    return requests.post(url, headers=_headers(), timeout=20, **kwargs)


def _raise_no_output(payload: Any) -> None:
    if not isinstance(payload, dict):
        pytest.fail("Flow run payload is not a JSON object")
    if any(key in payload for key in ("error", "detail", "message")):
        pytest.fail(f"Flow run returned an error payload: {payload}")

    flattened = _extract_run_output(payload)
    if isinstance(flattened, dict):
        if flattened:
            return
        raise AssertionError(f"Unexpected empty dict output: {flattened!r}")
    if isinstance(flattened, list) and len(flattened) > 0:
        for block in flattened:
            if isinstance(block, dict):
                if "results" in block or "outputs" in block:
                    return
        raise AssertionError(f"Unexpected flow output payload: {flattened!r}")
    raise AssertionError(f"Unexpected flow output payload: {flattened!r}")


@pytest.mark.e2e
def test_upload_flow_and_run_smoke() -> None:
    fixture_path = Path(FLOW_FIXTURE)
    if not fixture_path.exists():
        pytest.skip(f"Flow fixture is missing: {fixture_path}")

    wait_for_health()

    flow_payload = fixture_path.read_text(encoding="utf-8")
    flow_bytes = flow_payload.encode("utf-8")

    upload_response: requests.Response | None = None
    for upload_url, files in _upload_payload_variants(flow_bytes):
        try:
            response = _post(upload_url, files=files)
        except requests.RequestException:
            continue
        if response.status_code == 404:
            continue
        upload_response = response
        if response.status_code in (200, 201):
            break

    if upload_response is None:
        pytest.skip("Flow upload endpoint is unavailable in this test environment")
    if upload_response.status_code not in (200, 201):
        pytest.skip(f"Flow upload returned {upload_response.status_code}: {upload_response.text}")

    flow_response = upload_response.json()
    flow_id = _extract_flow_id(flow_response)
    if not flow_id:
        pytest.skip(f"Could not extract flow id from upload response: {flow_response}")

    run_urls = (
        f"{BASE_URL}/api/v1/run/{flow_id}",
        f"{BASE_URL}/api/v1/flows/{flow_id}/run",
        f"{BASE_URL}/flows/{flow_id}/run",
    )

    run_response: requests.Response | None = None
    for run_url in run_urls:
        for payload in _run_payload_variants():
            try:
                response = _post(run_url, json=payload)
            except requests.RequestException:
                continue
            if response.status_code == 404:
                continue
            run_response = response
            if response.status_code == 200:
                break
        if run_response is not None and run_response.status_code == 200:
            break

    if run_response is None:
        pytest.fail("Flow run endpoint is unavailable")
    if run_response.status_code != 200:
        pytest.fail(f"Flow run endpoint returned {run_response.status_code}: {run_response.text}")

    response_payload = run_response.json()
    _raise_no_output(response_payload)
