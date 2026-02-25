from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, FileInput, Output, SecretStrInput, StrInput
from lfx.schema import Data

import aioboto3


class S3Upload(Component):
    display_name = "S3 Upload"
    description = "Upload file or base64 payload to S3/MinIO."
    icon = "upload"
    name = "S3Upload"

    inputs = [
        StrInput(name="endpoint_url", display_name="Endpoint URL", required=True),
        SecretStrInput(name="access_key", display_name="Access Key", required=True),
        SecretStrInput(name="secret_key", display_name="Secret Key", required=True),
        SecretStrInput(name="session_token", display_name="Session Token", required=False, advanced=True),
        StrInput(name="region", display_name="Region", value="us-east-1", advanced=True),
        StrInput(name="bucket", display_name="Bucket", required=True),
        StrInput(name="object_key", display_name="Object Key", required=True),
        DropdownInput(
            name="input_mode",
            display_name="Input Mode",
            value="auto",
            options=["auto", "file", "base64"],
        ),
        FileInput(name="file", display_name="File", required=False),
        DataInput(name="data", display_name="Data (base64/data_url)", required=False),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Upload Result",
            method="build",
        )
    ]

    def build(self) -> Data:
        return self.upload()

    async def _upload_async(self, *, payload: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
        session_kwargs: Dict[str, Any] = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region or "us-east-1",
        }
        if self.session_token:
            session_kwargs["aws_session_token"] = self.session_token

        content_type = mimetypes.guess_type(filename or "")[0] if filename else "application/octet-stream"

        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
            response = await s3.put_object(
                Bucket=self.bucket,
                Key=self.object_key,
                Body=payload,
                ContentType=content_type,
            )
        return {
            "bucket": self.bucket,
            "key": self.object_key,
            "size_bytes": len(payload),
            "etag": response.get("ETag"),
            "s3_uri": f"s3://{self.bucket}/{self.object_key}",
            "filename": filename,
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

    def _extract_payload(self) -> tuple[bytes, Optional[str]]:
        if self.input_mode in ("auto", "file"):
            file_path = (self.file or "").strip() if getattr(self, "file", None) is not None else ""
            if file_path:
                file_path_obj = Path(file_path)
                data = file_path_obj.read_bytes()
                return data, file_path_obj.name

            if self.input_mode == "file":
                raise ValueError("File input mode selected but no file provided")

        data_obj = getattr(self, "data", None)
        if data_obj is None:
            raise ValueError("No input file or data payload provided")

        payload_dict = data_obj.data if isinstance(data_obj, Data) else data_obj
        if not isinstance(payload_dict, dict):
            raise ValueError("Data input must contain a dict with 'base64' or 'data_url'")

        filename = payload_dict.get("filename")
        raw_base64 = payload_dict.get("base64")

        if raw_base64:
            try:
                return base64.b64decode(raw_base64), filename
            except Exception as exc:
                raise ValueError("Invalid base64 payload") from exc

        data_url = payload_dict.get("data_url")
        if not data_url:
            raise ValueError("Data input must provide 'base64' or 'data_url'")

        match = re.match(r"^data:.*;base64,(.*)$", data_url)
        if not match:
            raise ValueError("Invalid data_url format")
        return base64.b64decode(match.group(1)), filename

    def upload(self) -> Data:
        payload, filename = self._extract_payload()
        metadata = self._run_async(self._upload_async(payload=payload, filename=filename))
        self.status = f"Uploaded {metadata['size_bytes']} bytes to {metadata['bucket']}/{metadata['key']}"
        return Data(data=metadata)
