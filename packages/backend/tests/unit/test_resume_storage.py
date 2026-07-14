"""Resource-lifecycle tests for the S3-compatible storage adapter."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from careeros.modules.resume_health.infrastructure.storage import S3ObjectStorage, S3Options


class _ClosingBody:
    def __init__(self, value: bytes) -> None:
        self._stream = BytesIO(value)
        self.closed = False

    def read(self, length: int = -1) -> bytes:
        return self._stream.read(length)

    def close(self) -> None:
        self.closed = True
        self._stream.close()


class _GetObjectClient:
    def __init__(self, bodies: list[_ClosingBody]) -> None:
        self._bodies = iter(bodies)

    def get_object(self, **kwargs: Any) -> dict[str, _ClosingBody]:
        del kwargs
        return {"Body": next(self._bodies)}


class _Signer:
    def __init__(self) -> None:
        self.operation = ""
        self.arguments: dict[str, Any] = {}

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.operation = operation
        self.arguments = kwargs
        return "https://uploads.invalid/signed"


@pytest.mark.asyncio
async def test_streaming_bodies_are_closed_for_every_bounded_read(tmp_path: Path) -> None:
    bodies = [_ClosingBody(b"prefix"), _ClosingBody(b"artifact"), _ClosingBody(b"download")]
    storage = object.__new__(S3ObjectStorage)
    storage._options = S3Options(
        internal_endpoint_url="http://s3.invalid",
        public_endpoint_url="http://s3.invalid",
        region="test-1",
        bucket="test",
        access_key_id="test",
        secret_access_key="test",  # noqa: S106 - isolated fictional adapter credential
    )
    storage._client = _GetObjectClient(bodies)

    assert await storage.read_prefix("object", 3) == b"pre"
    assert await storage.get_bytes("object", 8) == b"artifact"
    destination = tmp_path / "download.bin"
    await storage.download("object", destination, 64)

    assert destination.read_bytes() == b"download"
    assert all(body.closed for body in bodies)


@pytest.mark.asyncio
async def test_presigned_put_binds_content_length_type_and_expected_size_metadata() -> None:
    signer = _Signer()
    storage = object.__new__(S3ObjectStorage)
    storage._options = S3Options(
        internal_endpoint_url="http://s3.invalid",
        public_endpoint_url="http://uploads.invalid",
        region="test-1",
        bucket="test",
        access_key_id="test",
        secret_access_key="test",  # noqa: S106 - isolated fictional adapter credential
    )
    storage._signer = signer
    expires_at = datetime.now(UTC) + timedelta(minutes=10)

    target = await storage.presign_upload(
        "staging/user/owner/object", "application/pdf", 12_345, expires_at
    )

    assert signer.operation == "put_object"
    assert signer.arguments["HttpMethod"] == "PUT"
    assert 1 <= signer.arguments["ExpiresIn"] <= 600
    assert signer.arguments["Params"] == {
        "Bucket": "test",
        "Key": "staging/user/owner/object",
        "ContentType": "application/pdf",
        "ContentLength": 12_345,
        "Metadata": {"expected-size": "12345"},
    }
    assert target.headers == {
        "Content-Type": "application/pdf",
        "x-amz-meta-expected-size": "12345",
    }
