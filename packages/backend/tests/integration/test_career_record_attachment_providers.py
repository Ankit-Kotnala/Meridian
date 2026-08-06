"""Real provider contracts for the private Phase 3 attachment pipeline."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient

from rezumi.modules.career_record.application import (
    AttachmentDownloadPurpose,
    AttachmentLimits,
    AttachmentMediaType,
)
from rezumi.modules.career_record.application.attachment_workflow import ScanVerdict
from rezumi.modules.career_record.infrastructure import (
    AttachmentClamAvOptions,
    AttachmentClamAvScanner,
    AttachmentS3ObjectStorage,
    AttachmentS3Options,
    BoundedAttachmentExtractor,
)

FIXTURE = (
    Path(__file__).resolve().parents[3] / "test-fixtures" / "generated" / "fictional-resume.pdf"
)


def _storage() -> AttachmentS3ObjectStorage:
    endpoint = os.environ.get("REZUMI_TEST_S3_ENDPOINT_URL")
    if endpoint is None:
        pytest.skip("REZUMI_TEST_S3_ENDPOINT_URL is required for S3 integration tests")
    return AttachmentS3ObjectStorage(
        AttachmentS3Options(
            internal_endpoint_url=endpoint,
            public_endpoint_url=endpoint,
            region=os.environ["REZUMI_TEST_S3_REGION"],
            bucket=os.environ["REZUMI_TEST_S3_BUCKET"],
            access_key_id=os.environ["REZUMI_TEST_S3_ACCESS_KEY_ID"],
            secret_access_key=os.environ["REZUMI_TEST_S3_SECRET_ACCESS_KEY"],
        )
    )


@pytest.mark.asyncio
async def test_attachment_s3_signed_transfer_promotion_and_private_download(
    tmp_path: Path,
) -> None:
    storage = _storage()
    payload = FIXTURE.read_bytes()
    suffix = uuid4().hex
    staging_key = f"career-record/attachments/staging/integration/{suffix}"
    quarantine_key = f"career-record/attachments/quarantine/integration/{suffix}"
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    try:
        upload = await storage.presign_put(
            staging_key,
            AttachmentMediaType.PDF.value,
            len(payload),
            expires_at,
        )
        async with AsyncClient(trust_env=False, timeout=30) as client:
            response = await client.put(
                upload.url,
                content=payload,
                headers=dict(upload.required_headers),
            )
            assert response.status_code in {200, 204}

            assert (await storage.head(staging_key)).size_bytes == len(payload)
            assert await storage.read_prefix(staging_key, 5) == b"%PDF-"
            await storage.promote(staging_key, quarantine_key)

            grant = await storage.presign_get(
                quarantine_key,
                "fictional-evidence.pdf",
                AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
                expires_at,
            )
            downloaded_response = await client.get(grant.url)
            assert downloaded_response.status_code == 200
            assert downloaded_response.content == payload

        destination = tmp_path / "provider-download.pdf"
        downloaded = await storage.download(quarantine_key, destination, len(payload))
        assert downloaded.size_bytes == len(payload)
        assert destination.read_bytes() == payload
        assert len(downloaded.sha256_digest) == 32
    finally:
        await storage.delete(staging_key)
        await storage.delete(quarantine_key)
        await storage.dispose()


@pytest.mark.asyncio
async def test_attachment_clamav_and_bounded_extractor_accept_benign_pdf(
    tmp_path: Path,
) -> None:
    host = os.environ.get("REZUMI_TEST_CLAMAV_HOST")
    port = os.environ.get("REZUMI_TEST_CLAMAV_PORT")
    if host is None or port is None:
        pytest.skip("REZUMI_TEST_CLAMAV_HOST/PORT are required for scanner integration tests")

    scan = await AttachmentClamAvScanner(
        AttachmentClamAvOptions(host=host, port=int(port), timeout_seconds=30)
    ).scan(FIXTURE)
    assert scan.verdict is ScanVerdict.CLEAN

    summary = await BoundedAttachmentExtractor().extract(
        FIXTURE,
        AttachmentMediaType.PDF,
        AttachmentLimits(temp_root=tmp_path.resolve()),
    )
    assert summary.format_valid
    assert summary.page_count == 1
    assert summary.extracted_characters > 0
    assert summary.extracted_blocks > 0
