"""Schema-classified PostgreSQL export and cross-store account erasure."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import inspect, text

from careeros.foundation.database import Database
from careeros.modules.identity.application.account_operations import (
    AccountDeletionOutcome,
    AccountExportArtifact,
    AccountPrivacyStore,
)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_INTERNAL_TABLE_MARKERS = (
    "idempotency",
    "_outbox",
    "_processing_jobs",
    "_refresh_jobs",
    "_object_cleanups",
    "_download_intents",
    "_provider_runs",
)
_INTERNAL_TABLES = {
    "account_operations",
    "auth_one_time_tokens",
    "auth_refresh_tokens",
    "auth_sessions",
    "resume_uploads",
}
_SECRET_COLUMNS = {
    "access_token_hash",
    "capability_hash",
    "csrf_token_hash",
    "execution_token_hash",
    "password_hash",
    "request_token_hash",
    "token_hash",
}
_INTERNAL_COLUMNS = {
    "artifact_object_key",
    "invited_email_digest",
    "invited_email_normalized",
    "lease_token",
    "lease_expires_at",
    "object_key",
    "quarantine_object_key",
    "request_fingerprint",
    "staging_object_key",
}
_SPECIAL_SCOPES: dict[str, tuple[str, ...]] = {
    "audit_events": ("actor_user_id", "subject_user_id"),
    "consent_events": ("user_id",),
    "guest_resume_sessions": ("claimed_by_user_id",),
    "oauth_accounts": ("user_id",),
    "onboarding_progress": ("user_id",),
    "organization_access_grants": (
        "subject_user_id",
        "grantee_user_id",
        "granted_by_user_id",
    ),
    "organization_audit_events": ("actor_user_id", "subject_user_id"),
    "organization_invitations": ("invited_by_user_id", "accepted_by_user_id"),
    "organization_memberships": ("user_id",),
    "organizations": ("created_by_user_id",),
    "user_profiles": ("user_id",),
    "users": ("id",),
}
_OBJECT_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("document_artifacts", "owner_user_id", "object_key"),
    ("evidence_attachments", "owner_user_id", "quarantine_object_key"),
    ("resume_exports", "owner_user_id", "object_key"),
    ("source_documents", "owner_user_id", "quarantine_object_key"),
)
_ERASURE_OBJECT_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("account_operations", "user_id", "artifact_object_key"),
    ("document_artifacts", "owner_user_id", "object_key"),
    ("evidence_attachment_object_cleanups", "owner_user_id", "object_key"),
    ("evidence_attachments", "owner_user_id", "quarantine_object_key"),
    ("evidence_attachments", "owner_user_id", "staging_object_key"),
    ("resume_export_download_intents", "owner_user_id", "object_key"),
    ("resume_export_object_cleanups", "owner_user_id", "object_key"),
    ("resume_exports", "owner_user_id", "object_key"),
    ("resume_object_cleanups", "owner_user_id", "object_key"),
    ("resume_uploads", "owner_user_id", "staging_object_key"),
    ("source_documents", "owner_user_id", "quarantine_object_key"),
)


class PrivateObjectStorage(Protocol):
    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None: ...

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes: ...

    async def delete(self, object_key: str) -> None: ...

    async def presign_get(self, object_key: str, *, expires_in_seconds: int) -> str: ...


class PostgresS3AccountPrivacyStore(AccountPrivacyStore):
    """Export classified owner data and erase primary SQL/object stores."""

    def __init__(
        self,
        *,
        database: Database,
        storage: PrivateObjectStorage,
        max_archive_bytes: int = 134_217_728,
        max_object_bytes: int = 26_214_400,
    ) -> None:
        if not 1_048_576 <= max_archive_bytes <= 536_870_912:
            raise ValueError("account export archive limit is invalid")
        if not 1_048_576 <= max_object_bytes <= 52_428_800:
            raise ValueError("account export object limit is invalid")
        self._database = database
        self._storage = storage
        self._max_archive_bytes = max_archive_bytes
        self._max_object_bytes = max_object_bytes

    async def build_export(
        self,
        user_id: UUID,
        operation_id: UUID,
        generated_at: datetime,
        expires_at: datetime,
    ) -> AccountExportArtifact:
        async with self._database.session() as session:
            table_columns, user_fk_tables = await _schema_inventory(session)
            scopes = _classify_tables(table_columns, user_fk_tables)
            archive = io.BytesIO()
            file_manifest: list[dict[str, object]] = []
            table_manifest: list[dict[str, object]] = []
            with zipfile.ZipFile(
                archive,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
                strict_timestamps=True,
            ) as package:
                for table_name, scope_columns in sorted(scopes.items()):
                    rows = await _scoped_rows(
                        session,
                        table_name,
                        scope_columns,
                        user_id,
                    )
                    exported_rows = [_export_row(row) for row in rows]
                    path = f"data/{table_name}.json"
                    payload = _json_bytes(exported_rows)
                    package.writestr(path, payload)
                    table_manifest.append(
                        {
                            "table": table_name,
                            "recordCount": len(exported_rows),
                            "path": path,
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        }
                    )
                    _require_archive_limit(archive, self._max_archive_bytes)

                for table_name, owner_column, object_column in _OBJECT_SOURCES:
                    if (
                        table_name not in table_columns
                        or object_column not in table_columns[table_name]
                    ):
                        continue
                    objects = await _object_rows(
                        session,
                        table_name,
                        owner_column,
                        object_column,
                        user_id,
                    )
                    for record_id, object_key in objects:
                        if object_key is None:
                            continue
                        value = await self._storage.get_bytes(
                            object_key,
                            max_bytes=self._max_object_bytes,
                        )
                        suffix = _safe_suffix(object_key)
                        archive_path = f"files/{table_name}/{record_id}/{object_column}{suffix}"
                        package.writestr(archive_path, value)
                        file_manifest.append(
                            {
                                "source": table_name,
                                "recordId": record_id,
                                "path": archive_path,
                                "sizeBytes": len(value),
                                "sha256": hashlib.sha256(value).hexdigest(),
                            }
                        )
                        _require_archive_limit(archive, self._max_archive_bytes)

                manifest = {
                    "format": "careeros-account-export",
                    "formatVersion": 1,
                    "operationId": str(operation_id),
                    "generatedAt": generated_at.isoformat(),
                    "expiresAt": expires_at.isoformat(),
                    "tables": table_manifest,
                    "files": file_manifest,
                    "excluded": {
                        "authenticationSecrets": True,
                        "internalQueuesAndIdempotency": True,
                        "otherTenants": True,
                    },
                }
                package.writestr("manifest.json", _json_bytes(manifest))
                _require_archive_limit(archive, self._max_archive_bytes)

        value = archive.getvalue()
        if len(value) > self._max_archive_bytes:
            raise RuntimeError("account export exceeds configured archive limit")
        digest = hashlib.sha256(value).hexdigest()
        object_key = f"account-exports/{operation_id}/{digest[:16]}.zip"
        await self._storage.put_bytes(object_key, value, "application/zip")
        return AccountExportArtifact(
            object_key=object_key,
            sha256=digest,
            size_bytes=len(value),
            expires_at=expires_at,
        )

    async def erase_account(self, user_id: UUID) -> AccountDeletionOutcome:
        async with self._database.session() as session:
            sole_owner = await session.scalar(
                text(
                    "SELECT EXISTS ("
                    " SELECT 1 FROM organization_memberships mine"
                    " WHERE mine.user_id = :user_id"
                    " AND mine.role = 'owner' AND mine.status = 'active'"
                    " AND NOT EXISTS ("
                    "   SELECT 1 FROM organization_memberships other"
                    "   WHERE other.organization_id = mine.organization_id"
                    "   AND other.user_id <> :user_id"
                    "   AND other.role = 'owner' AND other.status = 'active'"
                    " ))"
                ),
                {"user_id": user_id},
            )
            if sole_owner:
                return AccountDeletionOutcome(blocker="organization_ownership_transfer_required")
            active_export = await session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM account_operations "
                    "WHERE user_id = :user_id AND kind = 'export' "
                    "AND status IN ('queued','running','retry_wait'))"
                ),
                {"user_id": user_id},
            )
            if active_export:
                raise RuntimeError("account export is still active")
            billing_record = await session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM commercial_billing_customers "
                    "WHERE owner_user_id = :user_id)"
                ),
                {"user_id": user_id},
            )
            if billing_record:
                return AccountDeletionOutcome(blocker="billing_retention_review_required")
            keys: set[str] = set()
            table_columns, _user_fk_tables = await _schema_inventory(session)
            _validate_erasure_object_inventory(table_columns)
            for table_name, owner_column, object_column in _ERASURE_OBJECT_SOURCES:
                if (
                    table_name not in table_columns
                    or object_column not in table_columns[table_name]
                ):
                    continue
                rows = await _object_rows(
                    session,
                    table_name,
                    owner_column,
                    object_column,
                    user_id,
                )
                keys.update(key for _record_id, key in rows if key)

        for object_key in sorted(keys):
            await self._storage.delete(object_key)

        async with self._database.session() as session:
            await session.execute(
                text(
                    "UPDATE account_operations SET status = 'expired', "
                    "artifact_object_key = NULL, artifact_sha256 = NULL, "
                    "artifact_size_bytes = NULL, artifact_expires_at = NULL, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE user_id = :user_id AND kind = 'export' "
                    "AND artifact_object_key IS NOT NULL"
                ),
                {"user_id": user_id},
            )
            result = await session.execute(
                text("DELETE FROM users WHERE id = :user_id AND status = 'disabled'"),
                {"user_id": user_id},
            )
            if cast(Any, result).rowcount != 1:
                await session.rollback()
                raise RuntimeError("account deletion target is unavailable")
            await session.commit()
        return AccountDeletionOutcome()

    async def delete_artifact(self, object_key: str) -> None:
        await self._storage.delete(object_key)

    async def presign_export(
        self,
        object_key: str,
        *,
        expires_in_seconds: int,
    ) -> str:
        return await self._storage.presign_get(
            object_key,
            expires_in_seconds=expires_in_seconds,
        )


async def _schema_inventory(
    session: Any,
) -> tuple[dict[str, set[str]], set[str]]:
    connection = await session.connection()

    def inspect_schema(sync_connection: Any) -> tuple[dict[str, set[str]], set[str]]:
        inspector = inspect(sync_connection)
        table_columns = {
            table_name: {
                str(column["name"]) for column in inspector.get_columns(table_name, schema="public")
            }
            for table_name in inspector.get_table_names(schema="public")
        }
        user_fk_tables: set[str] = set()
        for table_name in table_columns:
            for foreign_key in inspector.get_foreign_keys(table_name, schema="public"):
                if foreign_key.get("referred_table") == "users":
                    user_fk_tables.add(table_name)
        return table_columns, user_fk_tables

    return cast(
        tuple[dict[str, set[str]], set[str]],
        await connection.run_sync(inspect_schema),
    )


def _classify_tables(
    table_columns: Mapping[str, set[str]],
    user_fk_tables: set[str],
) -> dict[str, tuple[str, ...]]:
    scopes: dict[str, tuple[str, ...]] = {}
    unclassified: list[str] = []
    for table_name, columns in table_columns.items():
        if _is_internal_table(table_name):
            continue
        if table_name in _SPECIAL_SCOPES:
            configured = tuple(
                column for column in _SPECIAL_SCOPES[table_name] if column in columns
            )
            if configured:
                scopes[table_name] = configured
                continue
        if "owner_user_id" in columns:
            scopes[table_name] = ("owner_user_id",)
            continue
        if table_name in user_fk_tables:
            unclassified.append(table_name)
    if unclassified:
        raise RuntimeError(
            "unclassified user-linked privacy tables: " + ",".join(sorted(unclassified))
        )
    return scopes


def _validate_erasure_object_inventory(
    table_columns: Mapping[str, set[str]],
) -> None:
    discovered = {
        (table_name, column)
        for table_name, columns in table_columns.items()
        for column in columns
        if column == "object_key" or column.endswith("_object_key")
    }
    classified = {
        (table_name, object_column)
        for table_name, _owner_column, object_column in _ERASURE_OBJECT_SOURCES
    }
    unclassified = sorted(discovered - classified)
    if unclassified:
        labels = ",".join(f"{table}.{column}" for table, column in unclassified)
        raise RuntimeError("unclassified privacy object references: " + labels)


def _is_internal_table(table_name: str) -> bool:
    return table_name in _INTERNAL_TABLES or any(
        marker in table_name for marker in _INTERNAL_TABLE_MARKERS
    )


async def _scoped_rows(
    session: Any,
    table_name: str,
    scope_columns: tuple[str, ...],
    user_id: UUID,
) -> list[Mapping[str, object]]:
    table = _quoted_identifier(table_name)
    clauses = [f"{_quoted_identifier(column)} = :user_id" for column in scope_columns]
    result = await session.execute(
        text(f"SELECT * FROM {table} WHERE {' OR '.join(clauses)}"),  # noqa: S608 -- identifiers are regex allowlisted
        {"user_id": user_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def _object_rows(
    session: Any,
    table_name: str,
    owner_column: str,
    object_column: str,
    user_id: UUID,
) -> list[tuple[str, str | None]]:
    result = await session.execute(
        text(
            f"SELECT id, {_quoted_identifier(object_column)} "  # noqa: S608 -- regex-allowlisted identifiers
            f"FROM {_quoted_identifier(table_name)} "
            f"WHERE {_quoted_identifier(owner_column)} = :user_id "
            f"AND {_quoted_identifier(object_column)} IS NOT NULL"
        ),
        {"user_id": user_id},
    )
    return [(str(row[0]), str(row[1]) if row[1] is not None else None) for row in result.all()]


def _export_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        key: _json_value(value)
        for key, value in sorted(row.items())
        if key not in _SECRET_COLUMNS
        and key not in _INTERNAL_COLUMNS
        and not key.endswith("_token_hash")
    }


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _quoted_identifier(value: str) -> str:
    if _IDENTIFIER.fullmatch(value) is None:
        raise RuntimeError("unsafe schema identifier")
    return f'"{value}"'


def _safe_suffix(object_key: str) -> str:
    suffix = PurePosixPath(object_key).suffix.casefold()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ".bin"


def _require_archive_limit(archive: io.BytesIO, maximum: int) -> None:
    if archive.tell() > maximum:
        raise RuntimeError("account export exceeds configured archive limit")
