"""Private object storage adapter for resume exports."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import boto3
from botocore.config import Config

from careeros.modules.resume_builder.application.ports import ResumeObjectStorage


@dataclass(frozen=True, slots=True)
class ResumeExportS3Options:
    internal_endpoint_url: str
    public_endpoint_url: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    use_ssl: bool
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 30.0


class ResumeExportS3Storage(ResumeObjectStorage):
    """S3-compatible private storage for verified resume exports."""

    def __init__(self, options: ResumeExportS3Options) -> None:
        self._options = options
        self._client = boto3.client(
            "s3",
            endpoint_url=options.internal_endpoint_url,
            region_name=options.region,
            aws_access_key_id=options.access_key_id,
            aws_secret_access_key=options.secret_access_key,
            use_ssl=options.use_ssl,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=options.connect_timeout_seconds,
                read_timeout=options.read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        self._public_client = boto3.client(
            "s3",
            endpoint_url=options.public_endpoint_url,
            region_name=options.region,
            aws_access_key_id=options.access_key_id,
            aws_secret_access_key=options.secret_access_key,
            use_ssl=options.use_ssl,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=options.connect_timeout_seconds,
                read_timeout=options.read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._options.bucket,
            Key=object_key,
            Body=value,
            ContentType=media_type,
            Metadata={"private": "true"},
        )

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._options.bucket,
            Key=object_key,
        )
        stream = response["Body"]
        try:
            body = await asyncio.to_thread(stream.read, max_bytes + 1)
        finally:
            await asyncio.to_thread(stream.close)
        if len(body) > max_bytes:
            raise ValueError("object exceeds maximum read size")
        return bytes(body)

    async def delete(self, object_key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._options.bucket,
            Key=object_key,
        )

    async def presign_get(self, object_key: str, *, expires_in_seconds: int) -> str:
        filename = object_key.rsplit("/", 1)[-1]
        return str(
            await asyncio.to_thread(
                self._public_client.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self._options.bucket,
                    "Key": object_key,
                    "ResponseCacheControl": "private, no-store",
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=expires_in_seconds,
            )
        )

    async def dispose(self) -> None:
        await asyncio.gather(
            asyncio.to_thread(self._client.close),
            asyncio.to_thread(self._public_client.close),
        )
