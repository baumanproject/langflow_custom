from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Tuple

S3Behavior = str | Dict[str, str | Exception] | None


class FakeS3Body:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self) -> bytes:
        return self._data


class FakeS3Paginator:
    def __init__(self, storage: Dict[str, Dict[str, Tuple[bytes, str | None]]], bucket: str, prefix: str = ""):
        self._storage = storage
        self._bucket = bucket
        self._prefix = prefix

    async def paginate(self, **kwargs: Any) -> AsyncIterator[Dict[str, Any]]:
        bucket = kwargs.get("Bucket", self._bucket)
        if not bucket:
            bucket = self._bucket
        prefix = kwargs.get("Prefix", self._prefix)
        contents: List[Dict[str, str]] = []
        bucket_values = self._storage.get(bucket, {})
        for key in sorted(bucket_values):
            if key.startswith(prefix):
                if key == prefix:
                    continue
                contents.append({"Key": key})
        yield {"Contents": contents}


class FakeS3Client:
    def __init__(self, storage: Dict[str, Dict[str, Tuple[bytes, str | None]]], behavior: S3Behavior = "ok"):
        self.storage = storage
        self.behavior = behavior

    def _failure(self, operation: str) -> Exception | None:
        mode = self.behavior
        if isinstance(mode, dict):
            mode = mode.get(operation, mode.get("default", "ok"))
        if mode in (None, "ok"):
            return None
        if isinstance(mode, Exception):
            return mode
        if mode == "timeout":
            return TimeoutError(f"Timeout in S3 fake: {operation}")
        if mode == "bad_credentials":
            return PermissionError("Invalid S3 credentials")
        if mode in {"not_found", "no_such_key"}:
            return FileNotFoundError(f"Object '{operation}' was not found in fake S3")
        return RuntimeError(f"Configured fake S3 error for '{operation}': {mode}")

    def _raise_if(self, operation: str) -> None:
        failure = self._failure(operation)
        if failure is None:
            return
        raise failure

    async def put_object(self, *, Bucket: str, Key: str, Body: bytes, **kwargs: Any) -> Dict[str, str]:
        self._raise_if("put_object")
        bucket = self.storage.setdefault(Bucket, {})
        payload = await Body.read() if hasattr(Body, "read") else Body
        content_type = kwargs.get("ContentType")
        bucket[str(Key)] = (payload, content_type)
        return {"ETag": "fake-etag"}

    async def get_object(self, *, Bucket: str, Key: str) -> Dict[str, Any]:
        self._raise_if("get_object")
        bucket = self.storage.get(Bucket, {})
        if Key not in bucket:
            self._raise_if("missing_key")
            raise FileNotFoundError(f"Object '{Key}' was not found in bucket '{Bucket}'")
        payload, content_type = bucket[Key]
        return {"Body": FakeS3Body(payload), "ContentType": content_type}

    def get_paginator(self, operation_name: str) -> FakeS3Paginator:
        self._raise_if("get_paginator")
        if operation_name != "list_objects_v2":
            raise ValueError("Unsupported paginator operation")
        return FakeS3Paginator(self.storage, bucket="", prefix="")


class FakeS3SessionContext:
    def __init__(self, client: FakeS3Client):
        self._client = client

    async def __aenter__(self) -> FakeS3Client:
        return self._client

    async def __aexit__(self, *_: Any) -> None:
        return None


class FakeS3Session:
    def __init__(self, client: FakeS3Client):
        self._client = client

    def client(self, *_: Any, **__: Any) -> FakeS3SessionContext:
        return FakeS3SessionContext(self._client)


class FakeS3Backend:
    def __init__(self, behavior: S3Behavior = "ok"):
        self.store: Dict[str, Dict[str, Tuple[bytes, str | None]]] = {}
        self.behavior = behavior

    def session_factory(self, *_, **__) -> FakeS3Session:
        return FakeS3Session(FakeS3Client(self.store, behavior=self.behavior))


def install_fake_s3_session(
    monkeypatch: Any,
    component_module: str,
    backend: FakeS3Backend | None = None,
    behavior: S3Behavior = "ok",
) -> FakeS3Backend:
    resolved_backend = backend if backend is not None else FakeS3Backend(behavior=behavior)
    if backend is None:
        resolved_backend.behavior = behavior

    def _session_factory(*_: Any, **__: Any) -> FakeS3Session:
        return resolved_backend.session_factory()

    monkeypatch.setattr(f"{component_module}.aioboto3.Session", _session_factory)
    return resolved_backend
