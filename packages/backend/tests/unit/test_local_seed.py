"""Pure checks for the production-guarded fictional local seed."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pypdf import PdfReader

from rezumi.development.fictional_seed import (
    EXPECTED_MIGRATION_HEAD,
    FIXTURE_EMAIL,
    FictionalSeedManifest,
    build_fictional_seed_manifest,
)
from rezumi.development.local_seed import (
    LOCAL_SEED_CONFIRMATION,
    LocalSeedError,
    LocalSeedRefused,
    _ensure_object,
    load_local_seed_settings,
)
from rezumi.modules.application_workspace.infrastructure.models import (
    ApplicationRecordModel,
)
from rezumi.modules.application_workspace.infrastructure.repository import (
    _application as load_application,
)
from rezumi.modules.career_analytics.infrastructure.models import (
    AnalyticsSnapshotModel,
)
from rezumi.modules.career_analytics.infrastructure.repository import (
    _snapshot as load_analytics_snapshot,
)
from rezumi.modules.interview_prep.infrastructure.models import StarStoryModel
from rezumi.modules.interview_prep.infrastructure.repository import (
    _story as load_star_story,
)
from rezumi.modules.resume_builder.application import (
    validate_resume_version,
    version_provenance_failures,
)
from rezumi.modules.resume_builder.domain import (
    build_fidelity_manifest,
    manifest_grounding_failures,
)
from rezumi.modules.resume_builder.infrastructure.models import ResumeVersionModel
from rezumi.modules.resume_builder.infrastructure.repository import (
    _version as load_resume_version,
)
from rezumi.modules.resume_health.application.models import ObjectMetadata
from rezumi.modules.resume_health.domain.errors import UploadRejected
from rezumi.modules.resume_health.infrastructure.models import (
    CanonicalResumeSnapshotModel,
)
from rezumi.modules.resume_health.infrastructure.repository import (
    _snapshot as load_canonical_snapshot,
)
from rezumi.modules.resume_health.infrastructure.storage import S3ObjectStorage


def _safe_environment() -> dict[str, str]:
    return {
        "REZUMI_ENVIRONMENT": "development",
        "REZUMI_ALLOW_LOCAL_SEED": LOCAL_SEED_CONFIRMATION,
        "REZUMI_DATABASE_URL": (
            "postgresql+asyncpg://rezumi:local-only@postgres:5432/rezumi"
        ),
        "REZUMI_S3_ENDPOINT_URL": "http://minio:9000",
        "REZUMI_S3_REGION": "us-east-1",
        "REZUMI_S3_BUCKET": "rezumi-documents",
        "REZUMI_S3_ACCESS_KEY_ID": "rezumi-app",
        "REZUMI_S3_SECRET_ACCESS_KEY": "local-only-object-store-key",
        "REZUMI_S3_USE_SSL": "false",
    }


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"REZUMI_ENVIRONMENT": "production"}, "development"),
        ({"REZUMI_ENVIRONMENT": "staging"}, "development"),
        ({"REZUMI_ENVIRONMENT": "test"}, "development"),
        ({"REZUMI_ALLOW_LOCAL_SEED": ""}, "confirmation"),
        (
            {
                "REZUMI_DATABASE_URL": (
                    "postgresql+asyncpg://rezumi:local-only@db.example.com/rezumi"
                )
            },
            "database",
        ),
        (
            {
                "REZUMI_DATABASE_URL": (
                    "postgresql+asyncpg://other:local-only@postgres:5432/rezumi"
                )
            },
            "database",
        ),
        (
            {
                "REZUMI_DATABASE_URL": (
                    "postgresql+asyncpg://rezumi:local-only@postgres:5432/production"
                )
            },
            "database",
        ),
        ({"REZUMI_S3_ENDPOINT_URL": "https://objects.example.com"}, "MinIO"),
        ({"REZUMI_S3_BUCKET": "production-documents"}, "bucket"),
        ({"REZUMI_S3_USE_SSL": "yes"}, "true or false"),
        ({"REZUMI_S3_USE_SSL": "true"}, "must agree"),
    ),
)
def test_local_seed_guard_rejects_nonlocal_or_unconfirmed_settings(
    updates: Mapping[str, str],
    message: str,
) -> None:
    values = _safe_environment()
    values.update(updates)

    with pytest.raises(LocalSeedRefused, match=message):
        load_local_seed_settings(values)


def test_local_seed_guard_requires_explicit_environment_before_other_settings() -> None:
    with pytest.raises(LocalSeedRefused, match="development"):
        load_local_seed_settings(
            {
                "REZUMI_ENVIRONMENT": "production",
                "REZUMI_ALLOW_LOCAL_SEED": LOCAL_SEED_CONFIRMATION,
            }
        )


def test_local_seed_guard_accepts_only_reviewed_compose_local_settings() -> None:
    settings = load_local_seed_settings(_safe_environment())

    assert settings.environment == "development"
    assert settings.s3_endpoint_url == "http://minio:9000"
    assert settings.s3_bucket == "rezumi-documents"
    assert settings.s3_use_ssl is False
    assert "database_url" not in repr(settings)
    assert "secret_access_key" not in repr(settings)
    assert "confirmation" not in repr(settings)


def test_fictional_manifest_is_deterministic_and_spans_phases_one_through_nine() -> None:
    first = build_fictional_seed_manifest("public-fixture-password-hash")
    second = build_fictional_seed_manifest("public-fixture-password-hash")

    assert first.phases == tuple(range(1, 10))
    assert first.expected_row_count >= 40
    assert first == second
    assert first.email == FIXTURE_EMAIL
    assert first.email.endswith(".invalid")
    assert all(
        item.content == repeated.content
        for item, repeated in zip(first.objects, second.objects, strict=True)
    )
    assert all(
        item.sha256_digest == hashlib.sha256(item.content).hexdigest() for item in first.objects
    )
    assert all("fictional" in item.key for item in first.objects[:1])
    source_text = PdfReader(BytesIO(first.objects[0].content), strict=True).pages[0].extract_text()
    assert "FICTIONAL LOCAL FIXTURE" in source_text
    assert b"fictional local fixture" in first.objects[1].content


def test_fictional_manifest_has_unique_primary_keys_and_expected_object_links() -> None:
    manifest = build_fictional_seed_manifest("public-fixture-password-hash")

    for batch in manifest.batches:
        primary_key_names = tuple(column.name for column in batch.table.primary_key.columns)
        keys = [tuple(_hashable(row[name]) for name in primary_key_names) for row in batch.rows]
        assert len(keys) == len(set(keys)), batch.table.name

    source_document = _row(manifest, "source_documents")
    resume_export = _row(manifest, "resume_exports")
    source_object, export_object = manifest.objects
    assert source_document["quarantine_object_key"] == source_object.key
    assert source_document["content_sha256"] == bytes.fromhex(source_object.sha256_digest)
    assert source_document["size_bytes"] == len(source_object.content)
    assert resume_export["object_key"] == export_object.key
    assert resume_export["sha256_digest"] == export_object.sha256_digest
    assert resume_export["size_bytes"] == len(export_object.content)
    assert resume_export["status"] == "verified"
    assert resume_export["verification_status"] == "passed"


def test_fictional_resume_and_export_manifest_are_grounded_and_hash_consistent() -> None:
    manifest = build_fictional_seed_manifest("public-fixture-password-hash")
    version = manifest.resume_version
    fidelity = build_fidelity_manifest(version)
    resume_export = _row(manifest, "resume_exports")
    verification = _row(manifest, "resume_export_verification_reports")

    assert validate_resume_version(version) == version.sections
    assert version_provenance_failures(version) == ()
    assert manifest_grounding_failures(fidelity) == ()
    assert resume_export["version_content_sha256"] == fidelity.version_content_sha256
    assert verification["version_content_sha256"] == resume_export["version_content_sha256"]
    assert verification["manifest_sha256"] == resume_export["fidelity_manifest_sha256"]
    assert verification["file_sha256"] == resume_export["sha256_digest"]
    assert verification["critical_failures"] == []


def test_immutable_cross_phase_rows_are_accepted_by_product_repository_loaders() -> None:
    manifest = build_fictional_seed_manifest("public-fixture-password-hash")

    canonical = load_canonical_snapshot(
        CanonicalResumeSnapshotModel(**_row(manifest, "canonical_resume_snapshots"))
    )
    loaded_resume = load_resume_version(ResumeVersionModel(**_row(manifest, "resume_versions")))
    application = load_application(ApplicationRecordModel(**_row(manifest, "application_records")))
    story = load_star_story(
        StarStoryModel(**_row(manifest, "interview_star_stories")),
        (),
    )
    analytics = load_analytics_snapshot(
        AnalyticsSnapshotModel(**_row(manifest, "career_analytics_snapshots"))
    )

    assert canonical.resume.semantics is not None
    assert canonical.resume.semantics.review_state.value == "confirmed"
    assert loaded_resume == manifest.resume_version
    assert application.resume_version_id == manifest.resume_version.id
    assert application.resume_claims[0].evidence_links[0].evidence_id in (
        application.resume_evidence_ids
    )
    assert story.status.value == "draft"
    assert story.claim_pins == ()
    assert analytics.verify_payload_hash()


def test_seed_migration_pin_matches_the_executable_graph_gate() -> None:
    package_root = Path(__file__).resolve().parents[2]
    scripts = ScriptDirectory.from_config(Config(package_root / "alembic.ini"))

    assert scripts.get_heads() == [EXPECTED_MIGRATION_HEAD]


class _ObjectStorageDouble:
    def __init__(
        self,
        *,
        content: bytes | None = None,
        media_type: str | None = None,
    ) -> None:
        self.content = content
        self.media_type = media_type
        self.put_calls = 0

    async def head(self, object_key: str) -> ObjectMetadata:
        del object_key
        if self.content is None:
            raise UploadRejected("upload_object_missing")
        return ObjectMetadata(
            size_bytes=len(self.content),
            media_type=self.media_type,
        )

    async def get_bytes(self, object_key: str, max_bytes: int) -> bytes:
        del object_key
        if self.content is None:
            raise UploadRejected("upload_object_missing")
        return self.content[: max_bytes + 1]

    async def put_bytes(
        self,
        object_key: str,
        value: bytes,
        media_type: str,
    ) -> None:
        del object_key
        self.put_calls += 1
        self.content = value
        self.media_type = media_type


@pytest.mark.asyncio
async def test_seed_object_is_created_once_then_verified_without_rewrite() -> None:
    item = build_fictional_seed_manifest("public-fixture-password-hash").objects[0]
    double = _ObjectStorageDouble()
    storage = cast(S3ObjectStorage, double)

    await _ensure_object(storage, item)
    await _ensure_object(storage, item)

    assert double.put_calls == 1
    assert double.content == item.content
    assert double.media_type == item.media_type


@pytest.mark.asyncio
async def test_seed_object_drift_fails_without_overwrite() -> None:
    item = build_fictional_seed_manifest("public-fixture-password-hash").objects[0]
    drifted_content = b"X" * len(item.content)
    double = _ObjectStorageDouble(
        content=drifted_content,
        media_type=item.media_type,
    )
    storage = cast(S3ObjectStorage, double)

    with pytest.raises(LocalSeedError, match="content verification failed"):
        await _ensure_object(storage, item)

    assert double.put_calls == 0
    assert double.content == drifted_content


def _row(manifest: FictionalSeedManifest, table_name: str) -> dict[str, object]:
    matches = [
        row for batch in manifest.batches if batch.table.name == table_name for row in batch.rows
    ]
    assert len(matches) == 1
    return matches[0]


def _hashable(value: object) -> object:
    if isinstance(value, list):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _hashable(item)) for key, item in value.items()))
    if isinstance(value, UUID):
        return value.hex
    return value
