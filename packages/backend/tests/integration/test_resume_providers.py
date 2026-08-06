"""Real MinIO/S3 and ClamAV adapter contracts for isolated Phase 2 stacks."""

import os
from io import BytesIO
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from rezumi.modules.resume_health.infrastructure.malware import ClamAvOptions, ClamAvScanner
from rezumi.modules.resume_health.infrastructure.storage import S3ObjectStorage, S3Options


@pytest.mark.asyncio
async def test_private_s3_object_lifecycle() -> None:
    endpoint = os.environ.get("REZUMI_TEST_S3_ENDPOINT_URL")
    if endpoint is None:
        pytest.skip("REZUMI_TEST_S3_ENDPOINT_URL is required for S3 integration tests")
    storage = S3ObjectStorage(
        S3Options(
            internal_endpoint_url=endpoint,
            public_endpoint_url=endpoint,
            region=os.environ["REZUMI_TEST_S3_REGION"],
            bucket=os.environ["REZUMI_TEST_S3_BUCKET"],
            access_key_id=os.environ["REZUMI_TEST_S3_ACCESS_KEY_ID"],
            secret_access_key=os.environ["REZUMI_TEST_S3_SECRET_ACCESS_KEY"],
        )
    )
    first = f"integration/{uuid4().hex}"
    second = f"integration/{uuid4().hex}"
    try:
        await storage.ping()
        await storage.put_bytes(first, b"fictional resume derivative", "text/plain")
        assert await storage.get_bytes(first, 1_024) == b"fictional resume derivative"
        await storage.copy(first, second)
        assert (await storage.head(second)).size_bytes == len(b"fictional resume derivative")
    finally:
        await storage.delete(first)
        await storage.delete(second)
        await storage.dispose()


@pytest.mark.asyncio
async def test_clamav_detects_isolated_standard_test_signature() -> None:
    host = os.environ.get("REZUMI_TEST_CLAMAV_HOST")
    port = os.environ.get("REZUMI_TEST_CLAMAV_PORT")
    if host is None or port is None:
        pytest.skip("REZUMI_TEST_CLAMAV_HOST/PORT are required for scanner integration tests")
    # Build the standard harmless antivirus test signature at runtime so repository
    # checkout and static scanners never handle an active signature as one literal.
    pieces = [
        "X5O!P%@AP[4\\PZX54(P^)7CC)7}$",
        "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!",
        "$H+H*",
    ]
    payload = "".join(pieces).encode("ascii")

    class MemoryBackedPath:
        def open(self, mode: str) -> BytesIO:
            assert mode == "rb"
            return BytesIO(payload)

    result = await ClamAvScanner(ClamAvOptions(host=host, port=int(port), timeout_seconds=30)).scan(
        cast(Path, MemoryBackedPath())
    )

    assert result.infected
    assert not result.clean
