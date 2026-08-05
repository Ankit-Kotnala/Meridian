"""Private S3-compatible object storage adapter with separate browser signing origin."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from careeros.modules.resume_health.application.models import ObjectMetadata, StorageUploadTarget
from careeros.modules.resume_health.domain.errors import RetryableProcessingFailure, UploadRejected


@dataclass(frozen=True, slots=True)
class S3Options:
    internal_endpoint_url: str
    public_endpoint_url: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    use_ssl: bool = False
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 30.0


class S3ObjectStorage:
    """Keep all object operations private and expose only operation-scoped URLs."""

    def __init__(self, options: S3Options) -> None:
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

    async def ping(self) -> None:
        await self._call(self._client.head_bucket, Bucket=self._options.bucket)

    async def presign_upload(
        self,
        object_key: str,
        media_type: str,
        expected_size: int,
        expires_at: datetime,
    ) -> StorageUploadTarget:
        now = datetime.now(UTC)
        ttl = max(1, min(3_600, int((expires_at - now).total_seconds())))
        metadata_value = str(expected_size)
        try:
            url = await asyncio.to_thread(
                self._signer.generate_presigned_url,
                "put_object",
                Params={
                    "Bucket": self._options.bucket,
                    "Key": object_key,
                    "ContentType": media_type,
                    "ContentLength": expected_size,
                    "Metadata": {"expected-size": metadata_value},
                },
                ExpiresIn=ttl,
                HttpMethod="PUT",
            )
        except (BotoCoreError, ClientError) as exc:
            raise RetryableProcessingFailure("object_storage_unavailable") from exc

        # Replace internal endpoint with public endpoint in presigned URL
        url_str = str(url)
        internal_url = self._options.internal_endpoint_url.rstrip('/')
        public_url = self._options.public_endpoint_url.rstrip('/')
        if url_str.startswith(internal_url):
            url_str = url_str.replace(internal_url, public_url, 1)

        return StorageUploadTarget(
            method="PUT",
            url=url_str,
            headers={
                "Content-Type": media_type,
                "x-amz-meta-expected-size": metadata_value,
            },
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
                raise UploadRejected("upload_object_missing") from exc
            raise RetryableProcessingFailure("object_storage_unavailable") from exc
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
                return await asyncio.to_thread(body.read, length)
            finally:
                await asyncio.gather(asyncio.to_thread(body.close), return_exceptions=True)
        except ClientError as exc:
            if _error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                raise UploadRejected("upload_object_missing") from exc
            raise RetryableProcessingFailure("object_storage_unavailable") from exc
        except BotoCoreError as exc:
            raise RetryableProcessingFailure("object_storage_unavailable") from exc

    async def promote(self, staging_key: str, quarantine_key: str) -> None:
        """Copy into quarantine; durable cleanup owns eventual staging deletion."""
        await self.copy(staging_key, quarantine_key)

    async def download(self, object_key: str, destination: Path, max_bytes: int) -> bytes:
        try:
            result = await self._call(
                self._client.get_object,
                Bucket=self._options.bucket,
                Key=object_key,
            )
            body = result["Body"]
            try:
                digest = sha256()
                total = 0
                with destination.open("xb") as output:
                    while True:
                        chunk = await asyncio.to_thread(body.read, 64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise UploadRejected("upload_too_large")
                        digest.update(chunk)
                        output.write(chunk)
                return digest.digest()
            finally:
                await asyncio.gather(asyncio.to_thread(body.close), return_exceptions=True)
        except UploadRejected:
            destination.unlink(missing_ok=True)
            raise
        except (BotoCoreError, ClientError, OSError) as exc:
            destination.unlink(missing_ok=True)
            raise RetryableProcessingFailure("object_download_failed") from exc

    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
        try:
            await self._call(
                self._client.put_object,
                Bucket=self._options.bucket,
                Key=object_key,
                Body=value,
                ContentLength=len(value),
                ContentType=media_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RetryableProcessingFailure("object_storage_unavailable") from exc

    async def get_bytes(self, object_key: str, max_bytes: int) -> bytes:
        try:
            result = await self._call(
                self._client.get_object,
                Bucket=self._options.bucket,
                Key=object_key,
            )
            body = result["Body"]
            try:
                value = await asyncio.to_thread(body.read, max_bytes + 1)
                if len(value) > max_bytes:
                    raise UploadRejected("artifact_too_large")
                return bytes(value)
            finally:
                await asyncio.gather(asyncio.to_thread(body.close), return_exceptions=True)
        except UploadRejected:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise RetryableProcessingFailure("object_storage_unavailable") from exc

    async def copy(self, source_key: str, destination_key: str) -> None:
        try:
            await self._call(
                self._client.copy_object,
                Bucket=self._options.bucket,
                Key=destination_key,
                CopySource={"Bucket": self._options.bucket, "Key": source_key},
                MetadataDirective="COPY",
            )
        except (BotoCoreError, ClientError) as exc:
            raise RetryableProcessingFailure("object_copy_failed") from exc

    async def delete(self, object_key: str) -> None:
        try:
            await self._call(
                self._client.delete_object,
                Bucket=self._options.bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RetryableProcessingFailure("object_delete_failed") from exc

    async def dispose(self) -> None:
        await asyncio.to_thread(self._client.close)
        await asyncio.to_thread(self._signer.close)

    @staticmethod
    async def _call(function: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(function, **kwargs)
        except (BotoCoreError, ClientError):
            raise


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))
