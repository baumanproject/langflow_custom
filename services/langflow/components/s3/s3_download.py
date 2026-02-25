from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import threading
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DataInput, DropdownInput, Output, SecretStrInput, StrInput
from lfx.schema import Data

import aioboto3


class S3Download(Component):
    display_name = "S3 Download"
    description = "Download object from S3/MinIO to base64 or temporary file."
    icon = "download"
    name = "S3Download"

    inputs = [
        StrInput(name="endpoint_url", display_name="Endpoint URL", required=True),
        SecretStrInput(name="access_key", display_name="Access Key", required=True),
        SecretStrInput(name="secret_key", display_name="Secret Key", required=True),
        SecretStrInput(name="session_token", display_name="Session Token", required=False, advanced=True),
        StrInput(name="region", display_name="Region", value="us-east-1", advanced=True),
        StrInput(name="bucket", display_name="Bucket", required=True),
        StrInput(name="object_key", display_name="Object Key", required=True),
        DropdownInput(
            name="return_mode",
            display_name="Return Mode",
            value="temp_file",
            options=["base64", "temp_file"],
        ),
        StrInput(name="temp_dir", display_name="Temp Dir", required=False, advanced=True),
        BoolInput(name="include_data_url", display_name="Include data_url", value=False, advanced=True),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Downloaded Data",
            method="build",
        )
    ]

    def build(self) -> Data:
        return self.download()

    async def _download_async(self) -> Dict[str, Any]:
        session_kwargs = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region or "us-east-1",
        }
        if self.session_token:
            session_kwargs["aws_session_token"] = self.session_token

        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=self.object_key)
            raw = await response["Body"].read()
            headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
            return {
                "content": raw,
                "content_type": headers.get("content-type"),
            }

    def _run_async(self, coro):
        try:
            return asyncio.run(coro)
        except RuntimeError as exc:
            if "already running" not in str(exc).lower():
                raise

            result: Dict[str, Any] = {}
            error: Optional[BaseException] = None
            done = threading.Event()

            def runner() -> None:
                nonlocal result, error
                try:
                    result["value"] = asyncio.run(coro)
                except BaseException as e:  # noqa: BLE001
                    error = e
                finally:
                    done.set()

            thread = threading.Thread(target=runner, daemon=True)
            thread.start()
            done.wait()
            if error:
                raise error
            return result.get("value")

    def _parse_data_url(self, data: bytes, mime: str) -> str:
        return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"

    def download(self) -> Data:
        result = self._run_async(self._download_async())
        payload = result["content"]
        mime = result.get("content_type") or mimetypes.guess_type(self.object_key)[0] or "application/octet-stream"
        filename = Path(self.object_key).name

        if self.return_mode == "base64":
            record: Dict[str, Any] = {
                "filename": filename,
                "mime": mime,
                "base64": base64.b64encode(payload).decode("utf-8"),
            }
            if self.include_data_url:
                record["data_url"] = self._parse_data_url(payload, mime)
            self.status = f"Downloaded {len(payload)} bytes as base64"
            return Data(data=record)

        if self.temp_dir:
            Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
            fd, path = tempfile.mkstemp(suffix=Path(self.object_key).suffix, prefix=filename + "-", dir=self.temp_dir)
        else:
            fd, path = tempfile.mkstemp(suffix=Path(self.object_key).suffix, prefix=filename + "-")

        with os.fdopen(fd, "wb") as f:
            f.write(payload)

        self.status = f"Downloaded {len(payload)} bytes to {path}"
        return Data(data={"file_path": path, "filename": filename, "size_bytes": len(payload), "mime": mime})
