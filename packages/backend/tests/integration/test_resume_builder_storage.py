"""Real private-object storage contract for verified resume exports."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from httpx import AsyncClient

from careeros.modules.resume_builder.infrastructure import (
    ResumeExportS3Options,
    ResumeExportS3Storage,
)


def _storage() -> ResumeExportS3Storage:
    endpoint = os.environ.get("CAREEROS_TEST_S3_ENDPOINT_URL")
    if endpoint is None:
        pytest.skip("CAREEROS_TEST_S3_ENDPOINT_URL is required for S3 integration tests")
    return ResumeExportS3Storage(
        ResumeExportS3Options(
            internal_endpoint_url=endpoint,
            public_endpoint_url=endpoint,
            region=os.environ["CAREEROS_TEST_S3_REGION"],
            bucket=os.environ["CAREEROS_TEST_S3_BUCKET"],
            access_key_id=os.environ["CAREEROS_TEST_S3_ACCESS_KEY_ID"],
            secret_access_key=os.environ["CAREEROS_TEST_S3_SECRET_ACCESS_KEY"],
            use_ssl=False,
        )
    )


@pytest.mark.asyncio
async def test_verified_resume_round_trips_through_private_s3() -> None:
    storage = _storage()
    key = f"resume-exports/integration/{uuid4().hex}/resume.txt"
    payload = "Fictional verified résumé.\n".encode()
    try:
        await storage.put_bytes(key, payload, "text/plain; charset=utf-8")
        assert await storage.get_bytes(key, max_bytes=1024) == payload

        grant = await storage.presign_get(key, expires_in_seconds=60)
        async with AsyncClient(trust_env=False, timeout=30) as client:
            response = await client.get(grant)
        assert response.status_code == 200
        assert response.content == payload
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-disposition"] == 'attachment; filename="resume.txt"'
    finally:
        await storage.delete(key)
        await storage.dispose()
