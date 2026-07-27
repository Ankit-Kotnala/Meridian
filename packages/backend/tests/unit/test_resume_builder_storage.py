"""Private object-storage contract tests for verified resume exports."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest

from careeros.modules.resume_builder.infrastructure.storage import (
    ResumeExportS3Options,
    ResumeExportS3Storage,
)


class _ClosingBody:
    def __init__(self, value: bytes) -> None:
        self._stream = BytesIO(value)
        self.closed = False

    def read(self, length: int = -1) -> bytes:
        return self._stream.read(length)

    def close(self) -> None:
        self.closed = True
        self._stream.close()


class _ObjectClient:
    def __init__(self, body: _ClosingBody) -> None:
        self.body = body
        self.put_calls: list[dict[str, Any]] = []
        self.deleted: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.put_calls.append(kwargs)

    def get_object(self, **kwargs: Any) -> dict[str, _ClosingBody]:
        _ = kwargs
        return {"Body": self.body}

    def delete_object(self, **kwargs: Any) -> None:
        self.deleted.append(kwargs)


class _Signer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.calls.append((operation, kwargs))
        return "https://objects.invalid/private-download"


def _options() -> ResumeExportS3Options:
    return ResumeExportS3Options(
        internal_endpoint_url="http://s3.invalid",
        public_endpoint_url="http://downloads.invalid",
        region="test-1",
        bucket="private-resumes",
        access_key_id="fictional-access",
        secret_access_key="fictional-secret",  # noqa: S106 - isolated test credential
        use_ssl=False,
    )


@pytest.mark.asyncio
async def test_storage_marks_objects_private_and_presigns_no_store_attachment() -> None:
    body = _ClosingBody(b"verified resume")
    client = _ObjectClient(body)
    signer = _Signer()
    storage = object.__new__(ResumeExportS3Storage)
    storage._options = _options()
    storage._client = client
    storage._public_client = signer
    key = "resume-exports/owner/version/export/resume.pdf"

    await storage.put_bytes(key, b"verified resume", "application/pdf")
    url = await storage.presign_get(key, expires_in_seconds=300)
    await storage.delete(key)

    assert client.put_calls == [
        {
            "Body": b"verified resume",
            "Bucket": "private-resumes",
            "ContentType": "application/pdf",
            "Key": key,
            "Metadata": {"private": "true"},
        }
    ]
    assert client.deleted == [{"Bucket": "private-resumes", "Key": key}]
    assert url == "https://objects.invalid/private-download"
    operation, kwargs = signer.calls[0]
    assert operation == "get_object"
    assert kwargs["ExpiresIn"] == 300
    assert kwargs["Params"]["ResponseCacheControl"] == "private, no-store"
    assert kwargs["Params"]["ResponseContentDisposition"] == ('attachment; filename="resume.pdf"')


@pytest.mark.asyncio
async def test_storage_bounded_read_closes_stream_on_success_and_overflow() -> None:
    success_body = _ClosingBody(b"resume")
    storage = object.__new__(ResumeExportS3Storage)
    storage._options = _options()
    storage._client = _ObjectClient(success_body)

    assert await storage.get_bytes("opaque", max_bytes=6) == b"resume"
    assert success_body.closed

    overflow_body = _ClosingBody(b"too-large")
    storage._client = _ObjectClient(overflow_body)
    with pytest.raises(ValueError, match="maximum read size"):
        await storage.get_bytes("opaque", max_bytes=3)
    assert overflow_body.closed
