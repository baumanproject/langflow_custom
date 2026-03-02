from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema import Data

from pydantic import BaseModel


class DeleteLocalFilesInput(BaseModel):
    file_path: str | None = None
    file_paths: list[str] | None = None
    paths: list[str] | None = None


class DeleteLocalFilesOutput(BaseModel):
    deleted: list[str]
    errors: list[dict]


def _coerce_input(value: Any) -> DeleteLocalFilesInput:
    if isinstance(value, DeleteLocalFilesInput):
        return value
    payload = value.data if isinstance(value, Data) else value
    if isinstance(payload, DeleteLocalFilesInput):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("files_data must be a dict or DeleteLocalFilesInput")
    if hasattr(DeleteLocalFilesInput, "model_validate"):
        return DeleteLocalFilesInput.model_validate(payload)
    return DeleteLocalFilesInput.parse_obj(payload)


def _serialize_model(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


class DeleteLocalFiles(Component):
    display_name = "Delete Local Files"
    description = "Delete local temp files passed as file_path(s)."
    icon = "trash-2"
    name = "DeleteLocalFiles"

    inputs = [
        DataInput(name="files_data", display_name="File Data", required=True),
    ]

    outputs = [
        Output(name="result", display_name="Delete Result", method="build"),
    ]

    def build(self) -> Data:
        return self.delete()

    def _coerce_paths(self) -> List[str]:
        payload = _coerce_input(self.files_data)
        paths: List[str] = []

        if payload.file_path:
            paths.append(payload.file_path)

        if payload.file_paths:
            paths.extend([str(item).strip() for item in payload.file_paths if str(item).strip()])

        if payload.paths:
            paths.extend([str(item).strip() for item in payload.paths if str(item).strip()])

        if not paths:
            raise ValueError("No file paths found")
        return paths

    def _safe_delete(self, path: str) -> Dict[str, Any]:
        try:
            os.remove(path)
            return {"path": path, "ok": True, "error": None}
        except FileNotFoundError:
            return {"path": path, "ok": False, "error": "not_found"}
        except Exception as exc:  # noqa: BLE001
            return {"path": path, "ok": False, "error": str(exc)}

    def delete(self) -> Data:
        paths = self._coerce_paths()
        result = [self._safe_delete(path) for path in paths]
        deleted = [entry["path"] for entry in result if entry["ok"]]
        errors = [entry for entry in result if not entry["ok"]]
        self.status = f"Deleted {len(deleted)} files, failed {len(errors)}"
        return Data(data=_serialize_model(DeleteLocalFilesOutput(deleted=deleted, errors=errors)))
