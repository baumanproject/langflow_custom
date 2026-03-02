from __future__ import annotations

from typing import List

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput, StrInput
from lfx.schema import Data

import aioboto3


class S3ListFiles(Component):
    display_name = "S3 List Files"
    description = "List object keys inside a S3/MinIO folder."
    icon = "folder"
    name = "S3ListFiles"

    inputs = [
        StrInput(name="endpoint_url", display_name="Endpoint URL", required=True),
        SecretStrInput(name="access_key", display_name="Access Key", required=True),
        SecretStrInput(name="secret_key", display_name="Secret Key", required=True),
        SecretStrInput(name="session_token", display_name="Session Token", required=False, advanced=True),
        StrInput(name="region", display_name="Region", value="us-east-1", advanced=True),
        StrInput(name="bucket", display_name="Bucket", required=True),
        StrInput(name="folder", display_name="Folder", value="/", required=True),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Files",
            method="build",
        )
    ]

    async def build(self) -> Data:
        folder = self.folder
        prefix = self._build_prefix(folder)
        files = await self._list_async(prefix=prefix)
        self.status = f"Found {len(files)} file(s) in {folder}"
        return Data(data={"folder": folder, "files": files})

    @staticmethod
    def _build_prefix(folder: str) -> str:
        folder_clean = folder.strip()
        if not folder_clean or folder_clean == "/":
            return ""
        return folder_clean.strip("/") + "/"

    async def _list_async(self, *, prefix: str) -> List[str]:
        session_kwargs = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region or "us-east-1",
        }
        if self.session_token:
            session_kwargs["aws_session_token"] = self.session_token

        files = []
        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj.get("Key")
                    if not key:
                        continue
                    if key.endswith("/"):
                        continue
                    if prefix and key == prefix:
                        continue
                    files.append(key)
        return files
