"""Fail-closed CLI for the explicitly fictional local PostgreSQL/S3 seed."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import urlsplit

from sqlalchemy import Select, select, text, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.config import DatabaseOptions, parse_async_postgresql_url
from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.identity.infrastructure.security import Argon2PasswordHasher
from careeros.modules.resume_health.domain.errors import UploadRejected
from careeros.modules.resume_health.infrastructure.models import ResumeUploadModel
from careeros.modules.resume_health.infrastructure.storage import (
    S3ObjectStorage,
    S3Options,
)
from careeros.modules.role_readiness.infrastructure.models import (
    RoleDefinitionModel,
    RoleTaxonomyVersionModel,
)

from .fictional_seed import (
    EXPECTED_MIGRATION_HEAD,
    FIXTURE_EMAIL,
    FIXTURE_PASSWORD,
    PRODUCT_MANAGER_ROLE_ID,
    PRODUCT_MANAGER_ROLE_SLUG,
    PRODUCT_MANAGER_TAXONOMY_VERSION,
    FictionalSeedManifest,
    SeedBatch,
    SeedObject,
    build_fictional_seed_manifest,
    fixture_id,
)

LOCAL_SEED_CONFIRMATION = "fictional-careeros-local-seed-v1"
_LOCAL_DATABASE_HOSTS = frozenset({"postgres", "localhost", "127.0.0.1", "::1"})
_LOCAL_STORAGE_HOSTS = frozenset({"minio", "localhost", "127.0.0.1", "::1"})


class LocalSeedError(RuntimeError):
    """Safe, content-free local seed failure."""


class LocalSeedRefused(LocalSeedError):
    """The command was refused before dependency I/O."""


@dataclass(frozen=True, slots=True)
class LocalSeedSettings:
    environment: str
    confirmation: str = field(repr=False)
    database_url: str = field(repr=False)
    s3_endpoint_url: str
    s3_region: str
    s3_bucket: str
    s3_access_key_id: str = field(repr=False)
    s3_secret_access_key: str = field(repr=False)
    s3_use_ssl: bool


@dataclass(frozen=True, slots=True)
class LocalSeedResult:
    user_id: str
    email: str
    created_rows: int
    expected_rows: int
    verified_objects: int
    phases: tuple[int, ...]
    account_created: bool


def load_local_seed_settings(
    values: Mapping[str, str] | None = None,
) -> LocalSeedSettings:
    """Load settings only after the two explicit local-only guards pass."""

    source = os.environ if values is None else values
    environment = _value(source, "CAREEROS_ENVIRONMENT", "ENVIRONMENT")
    if environment != "development":
        raise LocalSeedRefused("local seed requires explicit CAREEROS_ENVIRONMENT=development")
    confirmation = _value(source, "CAREEROS_ALLOW_LOCAL_SEED")
    if confirmation != LOCAL_SEED_CONFIRMATION:
        raise LocalSeedRefused(
            "local seed requires the explicit CAREEROS_ALLOW_LOCAL_SEED confirmation"
        )

    database_url = _required(source, "CAREEROS_DATABASE_URL", "DATABASE_URL")
    parsed_database = parse_async_postgresql_url(database_url)
    if (
        parsed_database.host not in _LOCAL_DATABASE_HOSTS
        or parsed_database.database != "careeros"
        or parsed_database.username != "careeros"
    ):
        raise LocalSeedRefused(
            "local seed accepts only the local CareerOS database identity and host"
        )

    s3_endpoint_url = _required(source, "CAREEROS_S3_ENDPOINT_URL", "S3_ENDPOINT_URL")
    storage = urlsplit(s3_endpoint_url)
    if (
        storage.scheme not in {"http", "https"}
        or storage.hostname not in _LOCAL_STORAGE_HOSTS
        or storage.path not in {"", "/"}
        or storage.username is not None
        or storage.password is not None
        or storage.query
        or storage.fragment
    ):
        raise LocalSeedRefused("local seed accepts only a path-free local MinIO endpoint")
    s3_use_ssl = _strict_bool(_value(source, "CAREEROS_S3_USE_SSL", "S3_USE_SSL") or "false")
    if (storage.scheme == "https") != s3_use_ssl:
        raise LocalSeedRefused("local seed S3 URL scheme and SSL setting must agree")
    s3_bucket = _required(source, "CAREEROS_S3_BUCKET", "S3_BUCKET")
    if s3_bucket != "careeros-documents":
        raise LocalSeedRefused("local seed accepts only the isolated careeros-documents bucket")

    return LocalSeedSettings(
        environment=environment,
        confirmation=confirmation,
        database_url=database_url,
        s3_endpoint_url=s3_endpoint_url.rstrip("/"),
        s3_region=_required(source, "CAREEROS_S3_REGION", "S3_REGION"),
        s3_bucket=s3_bucket,
        s3_access_key_id=_required(
            source,
            "CAREEROS_S3_ACCESS_KEY_ID",
            "S3_ACCESS_KEY_ID",
        ),
        s3_secret_access_key=_required(
            source,
            "CAREEROS_S3_SECRET_ACCESS_KEY",
            "S3_SECRET_ACCESS_KEY",
        ),
        s3_use_ssl=s3_use_ssl,
    )


async def seed_fictional_local_data(settings: LocalSeedSettings) -> LocalSeedResult:
    """Seed, then independently verify, the fixed local graph and both objects."""

    # Settings are validated by the public loader, but callers constructing the
    # dataclass directly must not be able to bypass the guard.
    _validate_direct_settings(settings)
    database = Database(
        DatabaseOptions(
            url=settings.database_url,
            pool_size=1,
            max_overflow=0,
            connect_timeout_seconds=3,
            command_timeout_seconds=30,
        )
    )
    storage = S3ObjectStorage(
        S3Options(
            internal_endpoint_url=settings.s3_endpoint_url,
            public_endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            use_ssl=settings.s3_use_ssl,
            connect_timeout_seconds=3,
            read_timeout_seconds=30,
        )
    )
    try:
        await database.ping()
        await storage.ping()
        existing_password_hash = await _preflight(database)
        account_created = existing_password_hash is None
        password_hash = existing_password_hash or await Argon2PasswordHasher().hash(
            FIXTURE_PASSWORD
        )
        manifest = build_fictional_seed_manifest(password_hash)
        async with database.session() as session:
            await _verify_batches(session, manifest, allow_missing=True)
        for item in manifest.objects:
            await _ensure_object(storage, item)
        created_rows = await _insert_batches(database, manifest)
        async with database.session() as session:
            await _verify_batches(session, manifest, allow_missing=False)
        for item in manifest.objects:
            await _verify_object(storage, item)
        return LocalSeedResult(
            user_id=str(manifest.user_id),
            email=manifest.email,
            created_rows=created_rows,
            expected_rows=manifest.expected_row_count,
            verified_objects=len(manifest.objects),
            phases=manifest.phases,
            account_created=account_created,
        )
    except LocalSeedError:
        raise
    except Exception as exc:
        raise LocalSeedError(f"local seed failed safely ({type(exc).__name__})") from exc
    finally:
        await asyncio.gather(
            database.dispose(),
            storage.dispose(),
            return_exceptions=True,
        )


async def _preflight(database: Database) -> str | None:
    async with database.session() as session:
        migration = await session.scalar(text("SELECT version_num FROM alembic_version"))
        if migration != EXPECTED_MIGRATION_HEAD:
            raise LocalSeedError("database migration head does not match the reviewed local seed")
        role = await session.execute(
            select(
                RoleDefinitionModel.id,
                RoleDefinitionModel.slug,
                RoleDefinitionModel.taxonomy_version_id,
            ).where(RoleDefinitionModel.id == PRODUCT_MANAGER_ROLE_ID)
        )
        role_row = role.one_or_none()
        if role_row is None or role_row.slug != PRODUCT_MANAGER_ROLE_SLUG:
            raise LocalSeedError("required authored role taxonomy row is unavailable")
        taxonomy_version = await session.scalar(
            select(RoleTaxonomyVersionModel.version).where(
                RoleTaxonomyVersionModel.id == role_row.taxonomy_version_id
            )
        )
        if taxonomy_version != PRODUCT_MANAGER_TAXONOMY_VERSION:
            raise LocalSeedError("required authored role taxonomy version is unavailable")

        existing = await session.execute(
            select(UserModel.email_normalized, UserModel.password_hash).where(
                UserModel.id == fixture_id("user")
            )
        )
        user = existing.one_or_none()
        if user is None:
            return None
        if user.email_normalized != FIXTURE_EMAIL:
            raise LocalSeedError("reserved fictional seed identity is already in use")
        if user.password_hash is None:
            raise LocalSeedError(
                "fictional seed account password was removed; refusing to overwrite it"
            )
        return cast(str, user.password_hash)


async def _insert_batches(
    database: Database,
    manifest: FictionalSeedManifest,
) -> int:
    created_rows = 0
    async with database.session() as session, session.begin():
        for batch in manifest.batches:
            rows = [dict(row) for row in batch.rows]
            if batch.table is ResumeUploadModel.__table__:
                for row in rows:
                    # The upload and finalized source-document keys are circular.
                    # Insert the upload as unfinalized, create the source row, then
                    # establish the immutable final link in this same transaction.
                    row["finalized_document_id"] = None
            primary_key = tuple(batch.table.primary_key.columns)
            statement = (
                postgresql_insert(batch.table)
                .values(rows)
                .on_conflict_do_nothing(index_elements=list(primary_key))
                .returning(*primary_key)
            )
            result = await session.execute(statement)
            created_rows += len(result.all())
        for batch in manifest.batches:
            if batch.table is not ResumeUploadModel.__table__:
                continue
            for expected in batch.rows:
                finalized_document_id = expected["finalized_document_id"]
                if finalized_document_id is None:
                    continue
                await session.execute(
                    update(ResumeUploadModel)
                    .where(
                        ResumeUploadModel.id == expected["id"],
                        ResumeUploadModel.finalized_document_id.is_(None),
                    )
                    .values(finalized_document_id=finalized_document_id)
                )
    return created_rows


async def _verify_batches(
    session: AsyncSession,
    manifest: FictionalSeedManifest,
    *,
    allow_missing: bool,
) -> None:
    for batch in manifest.batches:
        for expected in batch.rows:
            statement = _primary_key_select(batch, expected)
            actual = (await session.execute(statement)).mappings().one_or_none()
            if actual is None:
                if allow_missing:
                    continue
                raise LocalSeedError(f"seed verification could not find {batch.table.name}")
            if batch.immutable:
                for column, value in expected.items():
                    if actual[column] != value:
                        raise LocalSeedError(
                            f"immutable fictional seed row changed in {batch.table.name}"
                        )
            elif batch.table is UserModel.__table__ and actual["email_normalized"] != FIXTURE_EMAIL:
                raise LocalSeedError("fictional seed identity verification failed")


def _primary_key_select(batch: SeedBatch, expected: dict[str, Any]) -> Select[Any]:
    statement = select(batch.table)
    for column in batch.table.primary_key.columns:
        statement = statement.where(column == expected[column.name])
    return statement


async def _write_and_verify_object(
    storage: S3ObjectStorage,
    item: SeedObject,
) -> None:
    await storage.put_bytes(item.key, item.content, item.media_type)
    await _verify_object(storage, item)


async def _ensure_object(
    storage: S3ObjectStorage,
    item: SeedObject,
) -> None:
    """Preserve an existing exact object and fail closed on any drift."""

    try:
        await _verify_object(storage, item)
    except UploadRejected as exc:
        if exc.code != "upload_object_missing":
            raise
        await _write_and_verify_object(storage, item)


async def _verify_object(
    storage: S3ObjectStorage,
    item: SeedObject,
) -> None:
    metadata = await storage.head(item.key)
    if metadata.size_bytes != len(item.content) or metadata.media_type != item.media_type:
        raise LocalSeedError("fictional seed object metadata verification failed")
    persisted = await storage.get_bytes(item.key, max_bytes=len(item.content))
    if persisted != item.content:
        raise LocalSeedError("fictional seed object content verification failed")


def _validate_direct_settings(settings: LocalSeedSettings) -> None:
    expected = {
        "CAREEROS_ENVIRONMENT": settings.environment,
        "CAREEROS_ALLOW_LOCAL_SEED": settings.confirmation,
        "CAREEROS_DATABASE_URL": settings.database_url,
        "CAREEROS_S3_ENDPOINT_URL": settings.s3_endpoint_url,
        "CAREEROS_S3_REGION": settings.s3_region,
        "CAREEROS_S3_BUCKET": settings.s3_bucket,
        "CAREEROS_S3_ACCESS_KEY_ID": settings.s3_access_key_id,
        "CAREEROS_S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
        "CAREEROS_S3_USE_SSL": str(settings.s3_use_ssl).lower(),
    }
    validated = load_local_seed_settings(expected)
    if validated != settings:
        raise LocalSeedRefused("local seed settings did not pass canonical validation")


def _required(source: Mapping[str, str], *names: str) -> str:
    value = _value(source, *names)
    if value is None or not value.strip():
        raise LocalSeedRefused(f"local seed requires {names[0]}")
    return value.strip()


def _value(source: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = source.get(name)
        if value is not None:
            return value.strip()
    return None


def _strict_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise LocalSeedRefused("local seed S3 SSL setting must be true or false")


def main() -> int:
    try:
        settings = load_local_seed_settings()
        result = asyncio.run(seed_fictional_local_data(settings))
    except LocalSeedRefused as exc:
        print(f"CareerOS local seed refused: {exc}", file=sys.stderr)
        return 2
    except LocalSeedError as exc:
        print(f"CareerOS local seed failed: {exc}", file=sys.stderr)
        return 1

    action = "created" if result.account_created else "preserved"
    print("CareerOS fictional local seed verified.")
    print(f"  Account: {result.email} ({action})")
    if result.account_created:
        print(f"  Fresh-seed password: {FIXTURE_PASSWORD}")
    print(f"  User ID: {result.user_id}")
    print(f"  Phases represented: {', '.join(str(item) for item in result.phases)}")
    print(f"  Rows: {result.expected_rows} verified, {result.created_rows} newly created")
    print(f"  Private objects: {result.verified_objects} verified")
    print("  All records are fictional and must never be used as career claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
