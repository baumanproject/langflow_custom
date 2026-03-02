from __future__ import annotations

import base64
import mimetypes
from typing import Any, Dict

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output, SecretStrInput, StrInput
from lfx.schema import Data

import aioboto3
from pydantic import BaseModel, validator


class S3UploadInput(BaseModel):
    name: str | None = None
    folder: str = "/"
    base64: str | None = None
    data_url: str | None = None
    mime: str | None = None
    key: str | None = None

    @validator("folder", pre=True, always=True)
    def _normalize_folder(cls, value: str | None) -> str:
        if value is None:
            return "/"
        folder = str(value).strip()
        if not folder or folder == "/":
            return "/"
        return folder.strip("/")

    def resolve_name(self) -> str:
        if self.name:
            return self.name
        if self.key:
            name = self.key.rsplit("/", 1)[-1]
            if name:
                return name
        raise ValueError("Field 'name' is required when key is not provided")

    def resolve_object_key(self) -> str:
        if self.key:
            return self.key.lstrip("/")
        name = self.resolve_name()
        if self.folder == "/":
            return name
        return f"{self.folder}/{name}"

    def resolve_mime(self) -> str | None:
        if self.mime:
            return self.mime
        if self.data_url and self.data_url.startswith("data:") and ";" in self.data_url:
            header = self.data_url.split(",", 1)[0]
            return header[5:].split(";", 1)[0] or None
        return None

    def resolve_binary(self) -> bytes:
        raw = self.base64
        if not raw:
            if self.data_url:
                if "," not in self.data_url:
                    raise ValueError("data_url must be in format data:<mime>;base64,<payload>")
                raw = self.data_url.split(",", 1)[1]
        if not raw:
            raise ValueError("Field 'base64' or 'data_url' is required")
        try:
            return base64.b64decode(raw)
        except Exception as exc:
            raise ValueError("Invalid base64 payload") from exc


class S3UploadOutput(BaseModel):
    bucket: str
    key: str
    size_bytes: int
    etag: str | None = None
    mime: str | None = None


def _coerce_upload_input(value: Any) -> S3UploadInput:
    if isinstance(value, S3UploadInput):
        return value
    payload = value.data if isinstance(value, Data) else value
    if isinstance(payload, S3UploadInput):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("S3Upload DataInput must be a dict or S3UploadInput")
    if hasattr(S3UploadInput, "model_validate"):
        return S3UploadInput.model_validate(payload)
    return S3UploadInput.parse_obj(payload)


def _serialize_model(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


class S3Upload(Component):
    display_name = "S3 Upload"
    description = "Upload base64 payload to S3/MinIO."
    icon = "upload"
    name = "S3Upload"

    inputs = [
        StrInput(name="endpoint_url", display_name="Endpoint URL", required=True),
        SecretStrInput(name="access_key", display_name="Access Key", required=True),
        SecretStrInput(name="secret_key", display_name="Secret Key", required=True),
        SecretStrInput(name="session_token", display_name="Session Token", required=False, advanced=True),
        StrInput(name="region", display_name="Region", value="us-east-1", advanced=True),
        StrInput(name="bucket", display_name="Bucket", required=True),
        DataInput(name="data", display_name="Data (name/base64/mime/folder)", required=True),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Upload Result",
            method="build",
        ),
    ]

    async def build(self) -> Data:
        payload = _coerce_upload_input(self.data)
        binary = payload.resolve_binary()
        object_key = payload.resolve_object_key()
        file_name = payload.resolve_name()
        guessed_mime = mimetypes.guess_type(file_name)[0]
        mime = payload.resolve_mime() or guessed_mime or "application/octet-stream"

        metadata = await self._upload_async(payload=binary, object_key=object_key, mime=mime)
        result_payload = S3UploadOutput(
            bucket=self.bucket,
            key=metadata["key"],
            size_bytes=metadata["size_bytes"],
            etag=metadata["etag"],
            mime=mime,
        )
        self.status = f"Uploaded {metadata['size_bytes']} bytes to {metadata['bucket']}/{metadata['key']}"
        return Data(data=_serialize_model(result_payload))

    async def _upload_async(self, *, payload: bytes, object_key: str, mime: str) -> Dict[str, Any]:
        session_kwargs: Dict[str, Any] = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region or "us-east-1",
        }
        if self.session_token:
            session_kwargs["aws_session_token"] = self.session_token

        session = aioboto3.Session(**session_kwargs)
        async with session.client("s3", endpoint_url=self.endpoint_url) as s3:
            response = await s3.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=payload,
                ContentType=mime,
            )
        return {
            "bucket": self.bucket,
            "key": object_key,
            "size_bytes": len(payload),
            "etag": response.get("ETag"),
        }
