"""Real PostgreSQL and S3 coverage for durable account privacy operations."""

from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import timedelta
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from sqlalchemy import delete, select

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.integrations.privacy import PostgresS3AccountPrivacyStore
from careeros.modules.commercial.infrastructure.models import BillingCustomerModel
from careeros.modules.identity.application import (
    AccountOperationProcessor,
    AccountOperationsPolicy,
    AccountOperationsService,
)
from careeros.modules.identity.application.models import RequestContext
from careeros.modules.identity.domain import (
    AccountOperationStatus,
    AuthenticatedPrincipal,
    AuthMethod,
)
from careeros.modules.identity.domain.errors import ResourceNotFound
from careeros.modules.identity.infrastructure.account_operation_repository import (
    SqlAlchemyAccountOperationsUnitOfWorkFactory,
)
from careeros.modules.identity.infrastructure.account_operation_security import (
    HmacAccountOperationTokenManager,
    UuidAccountOperationIdentifierFactory,
)
from careeros.modules.identity.infrastructure.fakes import utc_test_clock
from careeros.modules.identity.infrastructure.models import (
    AccountOperationModel,
    UserModel,
)
from careeros.modules.organizations.infrastructure.models import (
    OrganizationMembershipModel,
    OrganizationModel,
)
from careeros.modules.resume_builder.infrastructure import (
    ResumeExportS3Options,
    ResumeExportS3Storage,
)
from careeros.modules.resume_health.infrastructure.models import (
    DocumentArtifactModel,
    ResumeUploadModel,
    SourceDocumentModel,
)


def _database() -> Database:
    value = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required")
    return Database(DatabaseOptions(url=value, pool_size=2, max_overflow=0))


def _storage() -> ResumeExportS3Storage:
    endpoint = os.environ.get("CAREEROS_TEST_S3_ENDPOINT_URL")
    if endpoint is None:
        pytest.skip("CAREEROS_TEST_S3_ENDPOINT_URL is required")
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


def _context(name: str) -> RequestContext:
    return RequestContext(
        request_id=f"privacy-integration-{name}",
        trace_id="7" * 32,
        device_label="Privacy integration",
        source_key="integration",
    )


@pytest.mark.asyncio
async def test_deletion_blocks_sole_owners_and_retained_billing_customers() -> None:
    database = _database()
    storage = _storage()
    privacy = PostgresS3AccountPrivacyStore(database=database, storage=storage)
    owner_user_id = uuid4()
    billing_user_id = uuid4()
    organization_id = uuid4()
    now = utc_test_clock().now()
    try:
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=owner_user_id,
                        email_normalized=f"owner-{owner_user_id.hex[:12]}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=now,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    ),
                    UserModel(
                        id=billing_user_id,
                        email_normalized=f"billing-{billing_user_id.hex[:12]}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=now,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.flush()
            session.add(
                OrganizationModel(
                    id=organization_id,
                    name="Fictional Privacy Organization",
                    created_by_user_id=owner_user_id,
                    status="active",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add_all(
                [
                    OrganizationMembershipModel(
                        id=uuid4(),
                        organization_id=organization_id,
                        user_id=owner_user_id,
                        role="owner",
                        status="active",
                        version=1,
                        accepted_at=now,
                        suspended_at=None,
                        left_at=None,
                        created_at=now,
                        updated_at=now,
                    ),
                    BillingCustomerModel(
                        id=uuid4(),
                        owner_user_id=billing_user_id,
                        provider="fictional-provider",
                        provider_customer_reference=f"fictional-{billing_user_id}",
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.commit()

        owner_outcome = await privacy.erase_account(owner_user_id)
        billing_outcome = await privacy.erase_account(billing_user_id)
        assert owner_outcome.blocker == "organization_ownership_transfer_required"
        assert billing_outcome.blocker == "billing_retention_review_required"
        async with database.session() as session:
            retained_owner = await session.get(UserModel, owner_user_id)
            retained_billing_user = await session.get(UserModel, billing_user_id)
            assert retained_owner is not None and retained_owner.status == "active"
            assert retained_billing_user is not None
            assert retained_billing_user.status == "active"
    finally:
        async with database.session() as session:
            await session.execute(
                delete(BillingCustomerModel).where(
                    BillingCustomerModel.owner_user_id == billing_user_id
                )
            )
            await session.execute(
                delete(OrganizationModel).where(OrganizationModel.id == organization_id)
            )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([owner_user_id, billing_user_id]))
            )
            await session.commit()
        await storage.dispose()
        await database.dispose()


@pytest.mark.asyncio
async def test_export_then_deletion_is_capability_scoped_and_cross_store_complete() -> None:
    database = _database()
    storage = _storage()
    clock = utc_test_clock()
    tokens = HmacAccountOperationTokenManager(
        "privacy-integration-secret-that-is-longer-than-thirty-two-bytes"
    )
    operations = SqlAlchemyAccountOperationsUnitOfWorkFactory(database)
    privacy = PostgresS3AccountPrivacyStore(database=database, storage=storage)
    policy = AccountOperationsPolicy(export_retention_seconds=86_400)
    service = AccountOperationsService(
        unit_of_work=operations,
        clock=clock,
        identifiers=UuidAccountOperationIdentifierFactory(),
        tokens=tokens,
        privacy_store=privacy,
        policy=policy,
    )
    processor = AccountOperationProcessor(
        unit_of_work=operations,
        clock=clock,
        identifiers=UuidAccountOperationIdentifierFactory(),
        privacy_store=privacy,
        policy=policy,
    )
    user_id = uuid4()
    other_user_id = uuid4()
    upload_id = uuid4()
    document_id = uuid4()
    artifact_id = uuid4()
    prefix = f"privacy-integration/{user_id}"
    staging_key = f"{prefix}/staging.bin"
    source_key = f"{prefix}/source.pdf"
    artifact_key = f"{prefix}/plain-text.txt"
    staging_payload = b"fictional staging bytes"
    source_payload = b"%PDF-fictional-private-source"
    artifact_payload = b"Fictional extracted career evidence."
    now = clock.now()
    export_operation_id = deletion_operation_id = None
    export_object_key = None

    try:
        await storage.put_bytes(staging_key, staging_payload, "application/octet-stream")
        await storage.put_bytes(source_key, source_payload, "application/pdf")
        await storage.put_bytes(artifact_key, artifact_payload, "text/plain")
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=user_id,
                        email_normalized=f"privacy-{user_id.hex[:12]}@example.test",
                        password_hash="never-export-this-password-hash",  # noqa: S106
                        status="active",
                        email_verified_at=now,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    ),
                    UserModel(
                        id=other_user_id,
                        email_normalized=f"other-{other_user_id.hex[:12]}@example.test",
                        password_hash="other-private-password-hash",  # noqa: S106
                        status="active",
                        email_verified_at=now,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.flush()
            session.add(
                ResumeUploadModel(
                    id=upload_id,
                    owner_user_id=user_id,
                    guest_session_id=None,
                    display_filename="fictional-resume.pdf",
                    expected_media_type="application/pdf",
                    expected_size=len(source_payload),
                    staging_object_key=staging_key,
                    status="finalized",
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                    staging_cleaned_at=None,
                    finalized_document_id=None,
                    safe_error_code=None,
                )
            )
            await session.flush()
            session.add(
                SourceDocumentModel(
                    id=document_id,
                    upload_id=upload_id,
                    owner_user_id=user_id,
                    guest_session_id=None,
                    display_filename="fictional-resume.pdf",
                    media_type="application/pdf",
                    size_bytes=len(source_payload),
                    quarantine_object_key=source_key,
                    status="ready",
                    malware_status="clean",
                    content_sha256=b"1" * 32,
                    page_count=1,
                    safe_error_code=None,
                    retention_expires_at=None,
                    deleted_at=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add(
                DocumentArtifactModel(
                    id=artifact_id,
                    document_id=document_id,
                    owner_user_id=user_id,
                    guest_session_id=None,
                    kind="plain_text",
                    object_key=artifact_key,
                    size_bytes=len(artifact_payload),
                    sha256=b"2" * 32,
                    created_at=now,
                )
            )
            await session.commit()

        principal = AuthenticatedPrincipal(
            user_id=user_id,
            session_id=uuid4(),
            authenticated_at=now,
            auth_method=AuthMethod.PASSWORD,
        )
        requested_export = await service.request_export(
            principal,
            idempotency_key=f"export-{uuid4()}",
            context=_context("export"),
        )
        export_operation_id = requested_export.operation.id
        assert requested_export.operation_token is not None
        export_result = await processor.process_due(1)
        assert export_result.succeeded == 1

        completed_export = await service.get_status(
            export_operation_id,
            requested_export.operation_token,
        )
        export_object_key = completed_export.operation.artifact_object_key
        assert completed_export.operation.status is AccountOperationStatus.SUCCEEDED
        assert export_object_key is not None
        archive_bytes = await storage.get_bytes(
            export_object_key,
            max_bytes=134_217_728,
        )
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read("manifest.json"))
            users = archive.read("data/users.json").decode()
            assert manifest["format"] == "careeros-account-export"
            assert manifest["operationId"] == str(export_operation_id)
            assert f"privacy-{user_id.hex[:12]}@example.test" in users
            assert f"other-{other_user_id.hex[:12]}@example.test" not in users
            assert "password_hash" not in users
            assert "never-export-this-password-hash" not in users
            source_file = next(name for name in names if name.startswith("files/source_documents/"))
            artifact_file = next(
                name for name in names if name.startswith("files/document_artifacts/")
            )
            assert archive.read(source_file) == source_payload
            assert archive.read(artifact_file) == artifact_payload
            assert not any("staging.bin" in name for name in names)

        requested_deletion = await service.request_deletion(
            principal,
            idempotency_key=f"deletion-{uuid4()}",
            context=_context("deletion"),
        )
        deletion_operation_id = requested_deletion.operation.id
        assert requested_deletion.operation_token is not None
        deletion_result = await processor.process_due(1)
        assert deletion_result.succeeded == 1

        completed_deletion = await service.get_status(
            deletion_operation_id,
            requested_deletion.operation_token,
        )
        assert completed_deletion.operation.status is AccountOperationStatus.SUCCEEDED
        assert completed_deletion.operation.user_id is None
        expired_export = await service.get_status(
            export_operation_id,
            requested_export.operation_token,
        )
        assert expired_export.operation.status is AccountOperationStatus.EXPIRED
        assert expired_export.operation.artifact_object_key is None
        with pytest.raises(ResourceNotFound):
            await service.create_download_url(
                export_operation_id,
                requested_export.operation_token,
            )

        async with database.session() as session:
            assert await session.get(UserModel, user_id) is None
            retained = (
                await session.scalars(
                    select(AccountOperationModel).where(
                        AccountOperationModel.id.in_([export_operation_id, deletion_operation_id])
                    )
                )
            ).all()
            assert len(retained) == 2
            assert all(item.user_id is None for item in retained)
        for key in (staging_key, source_key, artifact_key, export_object_key):
            with pytest.raises(ClientError):
                await storage.get_bytes(key, max_bytes=134_217_728)
    finally:
        for cleanup_key in (staging_key, source_key, artifact_key, export_object_key):
            if cleanup_key is not None:
                await storage.delete(cleanup_key)
        async with database.session() as session:
            if export_operation_id is not None or deletion_operation_id is not None:
                operation_ids = [
                    value
                    for value in (export_operation_id, deletion_operation_id)
                    if value is not None
                ]
                await session.execute(
                    delete(AccountOperationModel).where(AccountOperationModel.id.in_(operation_ids))
                )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([user_id, other_user_id]))
            )
            await session.commit()
        await storage.dispose()
        await database.dispose()
