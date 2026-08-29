"""Real PostgreSQL upgrade coverage for legacy Change Studio claim provenance."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from rezumi.foundation.config import DatabaseOptions
from rezumi.foundation.database import Database
from rezumi.modules.change_studio.infrastructure.repository import (
    SqlAlchemyChangeStudioUnitOfWorkFactory,
)
from rezumi.modules.resume_builder.domain import ResumeBuilderValidationError
from rezumi.modules.resume_builder.infrastructure.sources import (
    CareerRecordResumeSourceProvider,
)

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_OWNER_ID = UUID("00000000-0000-4000-8000-000000009001")
_CHANGE_SET_ID = UUID("00000000-0000-4000-8000-000000009002")
_OPERATION_ID = UUID("00000000-0000-4000-8000-000000009003")
_CLAIM_ID = UUID("00000000-0000-4000-8000-000000009004")
_EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000009005")
_VERSION_ID = UUID("00000000-0000-4000-8000-000000009006")
_TARGET_ID = UUID("00000000-0000-4000-8000-000000009007")
_LEGACY_CLAIM_TEXT = "Preserved legacy evidence-backed claim."


def _alembic_config() -> Config:
    config = Config(str(_PACKAGE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PACKAGE_ROOT / "alembic"))
    return config


async def _create_database(admin_url: str, database_name: str) -> None:
    assert re.fullmatch(r"rezumi_phase8_[0-9a-f]{32}", database_name)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql(
                f'CREATE DATABASE "{database_name}" TEMPLATE template0'
            )
    finally:
        await engine.dispose()


async def _drop_database(admin_url: str, database_name: str) -> None:
    assert re.fullmatch(r"rezumi_phase8_[0-9a-f]{32}", database_name)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            await connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await engine.dispose()


async def _insert_legacy_claim(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email_normalized, password_hash, status, email_verified_at, "
                    "auth_version, created_at, updated_at) "
                    "VALUES (:id, 'phase8-legacy@example.test', NULL, 'active', NULL, "
                    "1, '2026-07-19T00:00:00Z', '2026-07-19T00:00:00Z')"
                ),
                {"id": _OWNER_ID},
            )
            await connection.execute(
                text(
                    "INSERT INTO change_sets "
                    "(id, owner_user_id, purpose, target_kind, status, job_id, analysis_id, "
                    "current_version_id, provider_name, provider_model, prompt_version, "
                    "policy_version, schema_version, grounding_version, idempotency_key, "
                    "idempotency_fingerprint, version, created_at, updated_at) "
                    "VALUES (:id, :owner_id, 'job_tailoring', 'tailored_resume_bullet', "
                    "'draft', NULL, NULL, NULL, 'legacy-provider', 'legacy-model', "
                    "'legacy-prompt', 'legacy-policy', 'legacy-schema', 'legacy-grounding', "
                    "'phase8-legacy-change-set', 'phase8-legacy-fingerprint', 1, "
                    "'2026-07-19T00:00:00Z', '2026-07-19T00:00:00Z')"
                ),
                {"id": _CHANGE_SET_ID, "owner_id": _OWNER_ID},
            )
            await connection.execute(
                text(
                    "INSERT INTO change_operations "
                    "(id, owner_user_id, change_set_id, operation_type, target_kind, target_id, "
                    "before_text, after_text, reason, status, risk, confidence_basis_points, "
                    "requires_confirmation, grounding_status, grounding_codes, "
                    "expected_score_delta_basis_points, requirement_id, requirement_text, "
                    "locked, sort_order, version, created_at, updated_at) "
                    "VALUES (:id, :owner_id, :change_set_id, 'replace_bullet', "
                    "'tailored_resume_bullet', :target_id, 'Before', :claim_text, "
                    "'Legacy reason', 'accepted', 'low', 9000, TRUE, 'grounded', "
                    "CAST(:grounding_codes AS jsonb), NULL, NULL, NULL, TRUE, 10, 1, "
                    "'2026-07-19T00:00:00Z', '2026-07-19T00:00:00Z')"
                ),
                {
                    "id": _OPERATION_ID,
                    "owner_id": _OWNER_ID,
                    "change_set_id": _CHANGE_SET_ID,
                    "target_id": _TARGET_ID,
                    "claim_text": _LEGACY_CLAIM_TEXT,
                    "grounding_codes": json.dumps(["grounded"]),
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO change_operation_claims "
                    "(id, owner_user_id, change_set_id, operation_id, claim_kind, text, "
                    "evidence_id, evidence_title, evidence_strength, source_excerpt, "
                    "validation_status, validation_codes, sort_order, created_at) "
                    "VALUES (:id, :owner_id, :change_set_id, :operation_id, 'achievement', "
                    ":claim_text, :evidence_id, 'Legacy evidence', 'confirmed', "
                    "'Original legacy excerpt', 'passed', CAST(:validation_codes AS jsonb), "
                    "10, '2026-07-19T00:00:00Z')"
                ),
                {
                    "id": _CLAIM_ID,
                    "owner_id": _OWNER_ID,
                    "change_set_id": _CHANGE_SET_ID,
                    "operation_id": _OPERATION_ID,
                    "claim_text": _LEGACY_CLAIM_TEXT,
                    "evidence_id": _EVIDENCE_ID,
                    "validation_codes": json.dumps(["grounded"]),
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO change_set_versions "
                    "(id, owner_user_id, change_set_id, version_number, parent_version_id, "
                    "created_by_operation_id, title, content, operation_ids, created_at) "
                    "VALUES (:id, :owner_id, :change_set_id, 1, NULL, :operation_id, "
                    "'Legacy accepted version', :claim_text, CAST(:operation_ids AS jsonb), "
                    "'2026-07-19T00:00:00Z')"
                ),
                {
                    "id": _VERSION_ID,
                    "owner_id": _OWNER_ID,
                    "change_set_id": _CHANGE_SET_ID,
                    "operation_id": _OPERATION_ID,
                    "claim_text": _LEGACY_CLAIM_TEXT,
                    "operation_ids": json.dumps([str(_OPERATION_ID)]),
                },
            )
            await connection.execute(
                text(
                    "UPDATE change_sets SET current_version_id = :version_id "
                    "WHERE owner_user_id = :owner_id AND id = :change_set_id"
                ),
                {
                    "version_id": _VERSION_ID,
                    "owner_id": _OWNER_ID,
                    "change_set_id": _CHANGE_SET_ID,
                },
            )
    finally:
        await engine.dispose()


async def _assert_preserved_and_constrained(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT text, evidence_id, evidence_title, source_excerpt, "
                            "evidence_revision_id, evidence_revision_number, "
                            "evidence_statement_sha256 "
                            "FROM change_operation_claims WHERE id = :claim_id"
                        ),
                        {"claim_id": _CLAIM_ID},
                    )
                )
                .mappings()
                .one()
            )
            assert row["text"] == _LEGACY_CLAIM_TEXT
            assert row["evidence_id"] == _EVIDENCE_ID
            assert row["evidence_title"] == "Legacy evidence"
            assert row["source_excerpt"] == "Original legacy excerpt"
            assert row["evidence_revision_id"] is None
            assert row["evidence_revision_number"] is None
            assert row["evidence_statement_sha256"] is None

            await connection.commit()
            transaction = await connection.begin()
            with pytest.raises(IntegrityError):
                await connection.execute(
                    text(
                        "UPDATE change_operation_claims "
                        "SET evidence_revision_id = :revision_id "
                        "WHERE id = :claim_id"
                    ),
                    {"revision_id": uuid4(), "claim_id": _CLAIM_ID},
                )
            await transaction.rollback()
    finally:
        await engine.dispose()


async def _assert_runtime_refuses_legacy_claim(database_url: str) -> None:
    database = Database(DatabaseOptions(url=database_url, pool_size=1, max_overflow=0))
    try:
        factory = SqlAlchemyChangeStudioUnitOfWorkFactory(database)
        async with factory() as unit_of_work:
            record = await unit_of_work.get_record(_OWNER_ID, _CHANGE_SET_ID)
        assert record is not None
        assert record.claims[0].evidence_revision_id is None
        assert record.claims[0].evidence_revision_number is None
        assert record.claims[0].evidence_statement_sha256 is None
        assert not record.claims[0].evidence_is_pinned

        career_record = SimpleNamespace(
            get_profile=_async_result(
                SimpleNamespace(
                    profile=SimpleNamespace(
                        professional_headline="Legacy profile",
                        summary=None,
                    )
                )
            ),
            readiness_snapshot=_async_result(
                SimpleNamespace(
                    evidence=(),
                    skills=(),
                )
            ),
            get_evidence_batch_with_eligibility=_async_failure(
                AssertionError("legacy pins must be rejected before evidence lookup")
            ),
        )
        change_studio = SimpleNamespace(get_change_set=_async_result(record))
        provider = CareerRecordResumeSourceProvider(  # type: ignore[arg-type]
            career_record,
            change_studio=change_studio,
        )
        with pytest.raises(
            ResumeBuilderValidationError,
            match="legacy unpinned",
        ):
            await provider.snapshot(
                _OWNER_ID,
                change_set_id=_CHANGE_SET_ID,
                change_set_version_id=_VERSION_ID,
            )
    finally:
        await database.dispose()


def _async_result(value: object):  # type: ignore[no-untyped-def]
    async def result(*_args: object, **_kwargs: object) -> object:
        return value

    return result


def _async_failure(error: Exception):  # type: ignore[no-untyped-def]
    async def fail(*_args: object, **_kwargs: object) -> object:
        raise error

    return fail


async def _assert_provenance_columns_absent(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            columns = (
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = current_schema() "
                            "AND table_name = 'change_operation_claims' "
                            "AND column_name IN "
                            "('evidence_revision_id', 'evidence_revision_number', "
                            "'evidence_statement_sha256')"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert columns == []
            preserved = await connection.scalar(
                text(
                    "SELECT text FROM change_operation_claims "
                    "WHERE owner_user_id = :owner_id AND id = :claim_id"
                ),
                {"owner_id": _OWNER_ID, "claim_id": _CLAIM_ID},
            )
            assert preserved == _LEGACY_CLAIM_TEXT
    finally:
        await engine.dispose()


def test_upgrade_from_0008_preserves_legacy_claim_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_url = os.environ.get("REZUMI_TEST_DATABASE_URL")
    if configured_url is None:
        pytest.skip("REZUMI_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(configured_url)
    database_name = f"rezumi_phase8_{uuid4().hex}"
    target_url = parsed_url.set(database=database_name).render_as_string(hide_password=False)
    admin_url = parsed_url.render_as_string(hide_password=False)
    asyncio.run(_create_database(admin_url, database_name))
    try:
        monkeypatch.setenv("REZUMI_DATABASE_URL", target_url)
        monkeypatch.setenv("DATABASE_URL", target_url)
        monkeypatch.setenv("REZUMI_ENVIRONMENT", "test")
        monkeypatch.setenv("ENVIRONMENT", "test")

        command.upgrade(_alembic_config(), "20260719_0008")
        asyncio.run(_insert_legacy_claim(target_url))
        command.upgrade(_alembic_config(), "20260724_0009")
        asyncio.run(_assert_preserved_and_constrained(target_url))
        asyncio.run(_assert_runtime_refuses_legacy_claim(target_url))

        command.downgrade(_alembic_config(), "20260719_0008")
        asyncio.run(_assert_provenance_columns_absent(target_url))
    finally:
        asyncio.run(_drop_database(admin_url, database_name))
