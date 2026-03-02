from __future__ import annotations

import base64
from typing import Any, Dict

from lfx.custom.custom_component.component import Component
from lfx.schema import Data
from lfx.io import Output, SecretStrInput, StrInput

import aioboto3
from pydantic import BaseModel

try:
    from lfx.io import MessageTextInput
except Exception:  # pragma: no cover - fallback when MessageTextInput is not available
    MessageTextInput = StrInput


def _coerce_object_key_from_input(message_reference: Any) -> str:
    if message_reference is None:
        return ""

    payload = message_reference.data if isinstance(message_reference, Data) else message_reference
    if isinstance(payload, str):
        key = payload.strip()
        return key.lstrip("/")
    if isinstance(payload, dict):
        if "key" in payload and isinstance(payload["key"], str):
            return str(payload["key"]).strip().lstrip("/")
        if "s3_key" in payload and isinstance(payload["s3_key"], str):
            return str(payload["s3_key"]).strip().lstrip("/")
        if "path" in payload and isinstance(payload["path"], str):
            return str(payload["path"]).strip().lstrip("/")
        return ""

    if hasattr(payload, "text") and isinstance(payload.text, str):
        return payload.text.strip().lstrip("/")
    if hasattr(payload, "content") and isinstance(payload.content, str):
        return payload.content.strip().lstrip("/")
    if hasattr(payload, "message") and isinstance(payload.message, str):
        return payload.message.strip().lstrip("/")

    key = getattr(payload, "key", None)
    if key is None:
        return ""
    return str(key).strip().lstrip("/")


class S3DownloadOutput(BaseModel):
    bucket: str
    key: str
    base64: str
    mime: str | None = None
    size_bytes: int


def _serialize_model(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


class S3Download(Component):
    display_name = "S3 Download"
    description = "Download object from S3/MinIO as base64."
    icon = "download"
    name = "S3Download"

    inputs = [
        StrInput(name="endpoint_url", display_name="Endpoint URL", required=True),
        SecretStrInput(name="access_key", display_name="Access Key", required=True),
        SecretStrInput(name="secret_key", display_name="Secret Key", required=True),
        SecretStrInput(name="session_token", display_name="Session Token", required=False, advanced=True),
        StrInput(name="region", display_name="Region", value="us-east-1", advanced=True),
        StrInput(name="bucket", display_name="Bucket", required=True),
        MessageTextInput(
            name="message_file_reference",
            display_name="Message File Reference",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Downloaded Data",
            method="build",
        )
    ]

    async def build(self) -> Data:
        object_key = _coerce_object_key_from_input(self.message_file_reference)
        if not object_key:
            raise ValueError("message_file_reference is required")
        result = await self._download_async(object_key=object_key)

        payload = result["content"]
        content_type = result["content_type"]
        mime = content_type or None

        record = S3DownloadOutput(
            bucket=self.bucket,
            key=object_key,
            base64=base64.b64encode(payload).decode("utf-8"),
            mime=mime,
            size_bytes=len(payload),
        )
        self.status = f"Downloaded {len(payload)} bytes as base64"
        return Data(data=_serialize_model(record))

    async def _download_async(self, *, object_key: str) -> Dict[str, Any]:
        session_kwargs = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region or "us-east-1",
        }
        if self.session_token:
            session_kwargs["aws_session_token"] = self.session_token

        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=object_key)
            raw = await response["Body"].read()
            return {"content": raw, "content_type": response.get("ContentType")}
