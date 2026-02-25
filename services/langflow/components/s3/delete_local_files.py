from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema import Data


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
        data = self.files_data
        if isinstance(data, Data):
            payload: Dict[str, Any] = data.data or {}
        elif isinstance(data, dict):
            payload = data
        else:
            raise ValueError("files_data must contain a Data or dict with file_path(s)")

        paths: List[str] = []
        explicit = payload.get("file_path") or payload.get("file_paths")

        if explicit:
            if isinstance(explicit, str):
                paths.append(explicit)
            elif isinstance(explicit, Iterable):
                paths.extend([str(item) for item in explicit if str(item).strip()])

        if payload.get("file_path") is None and payload.get("file_paths") is None and payload.get("paths"):
            paths.extend([str(item) for item in payload.get("paths", []) if str(item).strip()])

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
        return Data(data={"deleted": deleted, "errors": errors})
