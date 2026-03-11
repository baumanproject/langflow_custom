from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output, StrInput
from lfx.schema import Data


def _coerce_source(value: Any) -> Dict[str, Any]:
    if isinstance(value, Data):
        value = value.data

    if isinstance(value, dict):
        return value

    if hasattr(value, "dict") and callable(value.dict):
        return value.dict()

    raise ValueError("Source payload must be a dict, Data, or a pydantic model with dict()")


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, bytes | bytearray):
        return bytes(value).decode("utf-8")
    return str(value).strip() or None


def _extract_field(payload: Dict[str, Any], field_path: str | None) -> Any:
    if not field_path:
        return None

    current: Any = payload
    for key in field_path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
            continue
        if isinstance(current, list):
            try:
                idx = int(key)
                current = current[idx]
                continue
            except (ValueError, IndexError):
                return None
        return None
    return current


def _normalize_folder(value: Any) -> str:
    folder = _coerce_text(value)
    if not folder or folder == "/":
        return "/"
    return folder.strip("/")


def _coerce_base64(value: Any) -> str:
    if isinstance(value, bytes | bytearray):
        return base64.b64encode(bytes(value)).decode("utf-8")
    if isinstance(value, str):
        return base64.b64encode(value.encode("utf-8")).decode("utf-8")
    if isinstance(value, (dict, list)):
        return base64.b64encode(json.dumps(value, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    return base64.b64encode(str(value).encode("utf-8")).decode("utf-8")


def _coerce_from_file(path: Any) -> str:
    file_path = _coerce_text(path)
    if not file_path:
        raise ValueError("file_path is required for payload from file")

    raw = Path(file_path).read_bytes()
    return base64.b64encode(raw).decode("utf-8")


def _build_output(payload: Dict[str, Any], *, fields: Dict[str, str | None]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    name = _extract_field(payload, fields["name_field"]) or _extract_field(payload, fields["filename_field"])
    key = _extract_field(payload, fields["key"])
    folder = _extract_field(payload, fields["folder_field"])
    mime = _extract_field(payload, fields["mime_field"])
    base64_value = _extract_field(payload, fields["base64_field"])
    data_url = _extract_field(payload, fields["data_url_field"])
    content = _extract_field(payload, fields["content_field"])
    file_path = _extract_field(payload, fields["file_path_field"])

    if name is not None:
        name = _coerce_text(name)
    if key is not None:
        key = _coerce_text(key)
    if key:
        result["key"] = key

    resolved_folder = _normalize_folder(folder if folder is not None else "/")
    if resolved_folder:
        result["folder"] = resolved_folder

    if name:
        result["name"] = name

    if mime is not None:
        mime_value = _coerce_text(mime)
        if mime_value:
            result["mime"] = mime_value

    if base64_value is not None:
        resolved_base64 = _coerce_text(base64_value)
        if not resolved_base64:
            raise ValueError("base64 field was found but empty")
        result["base64"] = resolved_base64
    elif data_url is not None:
        resolved_data_url = _coerce_text(data_url)
        if not resolved_data_url:
            raise ValueError("data_url field was found but empty")
        result["data_url"] = resolved_data_url
    elif content is not None:
        result["base64"] = _coerce_base64(content)
    elif file_path is not None:
        result["base64"] = _coerce_from_file(file_path)
    else:
        raise ValueError(
            "One of 'base64', 'data_url', content field, or file_path field is required in source payload"
        )

    if not result.get("name") and not result.get("key"):
        raise ValueError("Either 'name' (or 'filename') or 'key' is required")

    return result


class S3UploadInputBuilder(Component):
    display_name = "S3 Upload Input Builder"
    description = "Transform arbitrary JSON payload into S3Upload input contract."
    icon = "braces"
    name = "S3UploadInputBuilder"

    inputs = [
        DataInput(name="payload", display_name="Source payload (JSON)", required=True),
        StrInput(name="name_field", display_name="Name field", value="name", advanced=True),
        StrInput(name="filename_field", display_name="Filename field", value="filename", advanced=True),
        StrInput(name="key_field", display_name="Object key field", value="key", advanced=True),
        StrInput(name="folder_field", display_name="Folder field", value="folder", advanced=True),
        StrInput(name="base64_field", display_name="Base64 field", value="base64", advanced=True),
        StrInput(name="data_url_field", display_name="data URL field", value="data_url", advanced=True),
        StrInput(name="content_field", display_name="Content field (auto base64)", value="content", advanced=True),
        StrInput(name="file_path_field", display_name="File path field", value="file_path", advanced=True),
        StrInput(name="mime_field", display_name="MIME field", value="mime", advanced=True),
    ]

    outputs = [
        Output(name="result", display_name="Prepared Data", method="build"),
    ]

    def build(self) -> Data:
        source = _coerce_source(self.payload)
        output_payload = _build_output(
            source,
            fields={
                "name_field": _coerce_text(self.name_field),
                "filename_field": _coerce_text(self.filename_field),
                "key_field": _coerce_text(self.key_field),
                "folder_field": _coerce_text(self.folder_field),
                "base64_field": _coerce_text(self.base64_field),
                "data_url_field": _coerce_text(self.data_url_field),
                "content_field": _coerce_text(self.content_field),
                "file_path_field": _coerce_text(self.file_path_field),
                "mime_field": _coerce_text(self.mime_field),
            },
        )
        self.status = f"Prepared S3 payload fields: {sorted(output_payload.keys())}"
        return Data(data=output_payload)
