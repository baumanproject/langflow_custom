from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, Output, SecretStrInput, StrInput
from lfx.schema import Data

import aioboto3


class S3UploadBase(Component):
    display_name = "S3 Upload Base"
    description = "Upload one or more local files to S3/MinIO folder."
    icon = "upload"
    name = "S3UploadBase"

    inputs = [
        StrInput(name="endpoint_url", display_name="Endpoint URL", required=True),
        SecretStrInput(name="access_key", display_name="Access Key", required=True),
        SecretStrInput(name="secret_key", display_name="Secret Key", required=True),
        SecretStrInput(name="session_token", display_name="Session Token", required=False, advanced=True),
        StrInput(name="region", display_name="Region", value="us-east-1", advanced=True),
        StrInput(name="bucket", display_name="Bucket", required=True),
        StrInput(name="s3_folder", display_name="S3 Folder", value="/", advanced=True),
        FileInput(
            name="files",
            display_name="Upload files",
            required=True,
            file_types=["png", "jpg", "jpeg", "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt"],
            info="Основные бизнес-форматы: png, jpg, jpeg, pdf, doc, docx, xls, xlsx, csv, txt",
            list=True,
            list_add_label="Upload files",
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Upload Result",
            method="build",
        )
    ]

    async def build(self) -> Data:
        folder = self._normalize_folder(self.s3_folder)
        file_paths = self._extract_files()
        uploaded = await self._upload_files(folder=folder, file_paths=file_paths)
        self.status = f"Uploaded {len(uploaded)} file(s) to {folder}"
        return Data(data={"folder": folder, "files": uploaded})

    @staticmethod
    def _normalize_folder(folder: str) -> str:
        folder_clean = folder.strip()
        if not folder_clean or folder_clean == "/":
            return "/"
        return folder_clean.strip("/")

    def _extract_files(self) -> List[str]:
        raw_files = self.files
        if isinstance(raw_files, (list, tuple)):
            files = list(raw_files)
        elif isinstance(raw_files, str):
            files = [raw_files]
        else:
            raise ValueError("Files input is required and must be one or more file paths")

        file_paths = [str(item).strip() for item in files if str(item).strip()]
        if not file_paths:
            raise ValueError("No valid file paths provided")
        return file_paths

    @staticmethod
    def _compose_key(folder: str, name: str) -> str:
        if not folder or folder == "/":
            return name
        return f"{folder.strip('/')}/{name}"

    async def _upload_files(self, *, folder: str, file_paths: List[str]) -> List[Dict[str, Any]]:
        session_kwargs: Dict[str, Any] = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region or "us-east-1",
        }
        if self.session_token:
            session_kwargs["aws_session_token"] = self.session_token

        uploaded: List[Dict[str, Any]] = []
        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
            for file_path in file_paths:
                path = Path(file_path)
                payload = path.read_bytes()
                object_key = self._compose_key(folder=folder, name=path.name)
                await s3.put_object(Bucket=self.bucket, Key=object_key, Body=payload)
                uploaded.append({"name": path.name, "s3_key": object_key})
        return uploaded
