"""Private S3-compatible storage for Career Record evidence attachments."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3  # type: ignore[import-untyped,unused-ignore]
from botocore.client import Config  # type: ignore[import-untyped,unused-ignore]
from botocore.exceptions import (  # type: ignore[import-untyped,unused-ignore]
    BotoCoreError,
    ClientError,
)

from rezumi.modules.career_record.application.attachment_workflow import (
    AttachmentDownloadPurpose,
    AttachmentObjectMissing,
    AttachmentStorageUnavailable,
    DownloadedObject,
    ObjectMetadata,
    PresignedOperation,
)


@dataclass(frozen=True, slots=True)
class AttachmentS3Options:
    internal_endpoint_url: str
    public_endpoint_url: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    use_ssl: bool = False
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 30.0


class AttachmentS3ObjectStorage:
    """Expose only operation-scoped URLs while retaining permanent credentials."""

    def __init__(self, options: AttachmentS3Options) -> None:
        self._options = options
        common: dict[str, Any] = {
            "service_name": "s3",
            "region_name": options.region,
            "aws_access_key_id": options.access_key_id,
            "aws_secret_access_key": options.secret_access_key,
            "use_ssl": options.use_ssl,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=options.connect_timeout_seconds,
                read_timeout=options.read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        }
        self._client = boto3.client(endpoint_url=options.internal_endpoint_url, **common)
        self._signer = boto3.client(endpoint_url=options.public_endpoint_url, **common)

    async def presign_put(
        self,
        object_key: str,
        media_type: str,
        expected_size: int,
        expires_at: datetime,
    ) -> PresignedOperation:
        ttl = _ttl(expires_at, maximum=900)
        try:
            url = await asyncio.to_thread(
                self._signer.generate_presigned_url,
                "put_object",
                Params={
                    "Bucket": self._options.bucket,
                    "Key": object_key,
                    "ContentType": media_type,
                    "ContentLength": expected_size,
                    "Metadata": {"expected-size": str(expected_size)},
                },
                ExpiresIn=ttl,
                HttpMethod="PUT",
            )
        except (BotoCoreError, ClientError) as exc:
            raise AttachmentStorageUnavailable from exc

        # Replace internal endpoint with public endpoint in presigned URL
        url_str = str(url)
        internal_url = self._options.internal_endpoint_url.rstrip("/")
        public_url = self._options.public_endpoint_url.rstrip("/")
        if url_str.startswith(internal_url):
            url_str = url_str.replace(internal_url, public_url, 1)

        return PresignedOperation(
            method="PUT",
            url=url_str,
            required_headers=(
                ("content-type", media_type),
                ("content-length", str(expected_size)),
                ("x-amz-meta-expected-size", str(expected_size)),
            ),
            expires_at=expires_at,
        )

    async def head(self, object_key: str) -> ObjectMetadata:
        try:
            result = await self._call(
                self._client.head_object,
                Bucket=self._options.bucket,
                Key=object_key,
            )
        except ClientError as exc:
            if _error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                raise AttachmentObjectMissing from exc
            raise AttachmentStorageUnavailable from exc
        except BotoCoreError as exc:
            raise AttachmentStorageUnavailable from exc
        return ObjectMetadata(
            size_bytes=int(result["ContentLength"]),
            media_type=str(result.get("ContentType")) if result.get("ContentType") else None,
        )

    async def read_prefix(self, object_key: str, length: int) -> bytes:
        try:
            result = await self._call(
                self._client.get_object,
                Bucket=self._options.bucket,
                Key=object_key,
                Range=f"bytes=0-{max(0, length - 1)}",
            )
            body = result["Body"]
            try:
                return bytes(await asyncio.to_thread(body.read, length))
            finally:
                await asyncio.gather(asyncio.to_thread(body.close), return_exceptions=True)
        except ClientError as exc:
            if _error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                raise AttachmentObjectMissing from exc
            raise AttachmentStorageUnavailable from exc
        except BotoCoreError as exc:
            raise AttachmentStorageUnavailable from exc

    async def promote(self, staging_key: str, quarantine_key: str) -> None:
        """Copy to quarantine; the durable cleanup record removes staging."""

        try:
            await self._call(
                self._client.copy_object,
                Bucket=self._options.bucket,
                Key=quarantine_key,
                CopySource={"Bucket": self._options.bucket, "Key": staging_key},
                MetadataDirective="COPY",
            )
        except ClientError as exc:
            if _error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                raise AttachmentObjectMissing from exc
            raise AttachmentStorageUnavailable from exc
        except BotoCoreError as exc:
            raise AttachmentStorageUnavailable from exc

    async def download(
        self, object_key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject:
        total = 0
        digest = sha256()
        try:
            result = await self._call(
                self._client.get_object,
                Bucket=self._options.bucket,
                Key=object_key,
            )
            body = result["Body"]
            try:
                with destination.open("xb") as output:
                    while True:
                        chunk = bytes(await asyncio.to_thread(body.read, 64 * 1024))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise AttachmentStorageUnavailable
                        digest.update(chunk)
                        output.write(chunk)
            finally:
                await asyncio.gather(asyncio.to_thread(body.close), return_exceptions=True)
        except ClientError as exc:
            destination.unlink(missing_ok=True)
            if _error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                raise AttachmentObjectMissing from exc
            raise AttachmentStorageUnavailable from exc
        except AttachmentStorageUnavailable:
            destination.unlink(missing_ok=True)
            raise
        except (BotoCoreError, OSError) as exc:
            destination.unlink(missing_ok=True)
            raise AttachmentStorageUnavailable from exc
        return DownloadedObject(destination.resolve(), total, digest.digest())

    async def presign_get(
        self,
        object_key: str,
        display_filename: str,
        purpose: AttachmentDownloadPurpose,
        expires_at: datetime,
    ) -> PresignedOperation:
        if purpose is not AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW:
            raise ValueError("unsupported evidence attachment download purpose")
        disposition = f"attachment; filename*=UTF-8''{quote(display_filename, safe='')}"
        try:
            url = await asyncio.to_thread(
                self._signer.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self._options.bucket,
                    "Key": object_key,
                    "ResponseContentDisposition": disposition,
                    "ResponseCacheControl": "private, no-store",
                },
                ExpiresIn=_ttl(expires_at, maximum=300),
                HttpMethod="GET",
            )
        except (BotoCoreError, ClientError) as exc:
            raise AttachmentStorageUnavailable from exc
        return PresignedOperation(
            method="GET",
            url=str(url),
            required_headers=(),
            expires_at=expires_at,
        )

    async def delete(self, object_key: str) -> None:
        try:
            await self._call(
                self._client.delete_object,
                Bucket=self._options.bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise AttachmentStorageUnavailable from exc

    async def dispose(self) -> None:
        await asyncio.to_thread(self._client.close)
        await asyncio.to_thread(self._signer.close)

    @staticmethod
    async def _call(function: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(function, **kwargs)


def _ttl(expires_at: datetime, *, maximum: int) -> int:
    return max(1, min(maximum, int((expires_at - datetime.now(UTC)).total_seconds())))


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))
