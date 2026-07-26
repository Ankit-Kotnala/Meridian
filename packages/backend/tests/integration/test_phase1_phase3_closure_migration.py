"""Fresh PostgreSQL migration and constraint coverage for the Phase 1/3 closure."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_NEW_TABLES = {
    "career_entity_confirmations",
    "career_entity_relationships",
    "career_field_provenance",
    "career_personal_facts",
    "career_semantic_import_proposals",
    "career_skill_confirmations",
}


def _alembic_config() -> Config:
    config = Config(str(_PACKAGE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PACKAGE_ROOT / "alembic"))
    return config


async def _create_database(admin_url: str, database_name: str) -> None:
    assert re.fullmatch(r"careeros_phase13_closure_[0-9a-f]{32}", database_name)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql(
                f'CREATE DATABASE "{database_name}" TEMPLATE template0'
            )
    finally:
        await engine.dispose()


async def _drop_database(admin_url: str, database_name: str) -> None:
    assert re.fullmatch(r"careeros_phase13_closure_[0-9a-f]{32}", database_name)
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


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
            )
            return {str(row[0]) for row in rows}
    finally:
        await engine.dispose()


async def _insert_historical_entity(
    database_url: str,
) -> tuple[UUID, UUID, UUID]:
    engine = create_async_engine(database_url)
    owner_id = uuid4()
    other_id = uuid4()
    profile_id = uuid4()
    entity_id = uuid4()
    try:
        async with engine.begin() as connection:
            for user_id, email in (
                (owner_id, f"owner-{owner_id.hex}@example.test"),
                (other_id, f"other-{other_id.hex}@example.test"),
            ):
                await connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email_normalized, password_hash, status, "
                        "email_verified_at, auth_version, created_at, updated_at) "
                        "VALUES (:id, :email, NULL, 'active', now(), 1, now(), now())"
                    ),
                    {"id": user_id, "email": email},
                )
            await connection.execute(
                text(
                    "INSERT INTO career_profiles "
                    "(id, owner_user_id, professional_headline, summary, "
                    "work_authorization, version, created_at, updated_at) "
                    "VALUES (:id, :owner, NULL, NULL, NULL, 1, now(), now())"
                ),
                {"id": profile_id, "owner": owner_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO career_entities "
                    "(id, owner_user_id, profile_id, kind, title, organization, "
                    "description, official_title, display_title, employment_type, "
                    "location, external_url, start_year, start_month, end_year, "
                    "end_month, is_current, sort_order, group_id, version, "
                    "created_at, updated_at) "
                    "VALUES (:id, :owner, :profile, 'experience', 'Engineer', "
                    "'Example Corp', NULL, 'Engineer', 'Engineer', 'full_time', "
                    "NULL, NULL, 2024, 1, NULL, NULL, true, 0, NULL, 1, now(), now())"
                ),
                {"id": entity_id, "owner": owner_id, "profile": profile_id},
            )
        return owner_id, other_id, entity_id
    finally:
        await engine.dispose()


async def _degrade_phase9_schema(database_url: str) -> None:
    """Simulate a database stamped by an earlier pre-release Phase 9 migration."""

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            statements = (
                "ALTER TABLE career_analytics_audit_events "
                "DROP CONSTRAINT fk_career_analytics_audits_actor_user",
                "ALTER TABLE career_analytics_audit_events ALTER COLUMN actor_user_id SET NOT NULL",
                "ALTER TABLE career_analytics_audit_events ALTER COLUMN request_id SET NOT NULL",
                "DROP INDEX ix_career_analytics_snapshots_owner_scope_window",
                "CREATE INDEX ix_career_analytics_snapshots_owner_scope_window "
                "ON career_analytics_snapshots "
                "(owner_user_id, scope, window_start, window_end, created_at, id)",
                "ALTER TABLE career_analytics_snapshots DROP COLUMN timezone",
                "ALTER TABLE career_growth_evidence_links "
                "DROP CONSTRAINT fk_career_growth_evidence_links_owner_revision",
                "ALTER TABLE evidence_revisions "
                "DROP CONSTRAINT uq_evidence_revisions_owner_evidence_id",
                "ALTER TABLE career_growth_reviews "
                "DROP CONSTRAINT fk_career_growth_reviews_owner_latest_version",
                "ALTER TABLE career_growth_review_versions "
                "DROP CONSTRAINT fk_career_growth_review_versions_owner_predecessor",
                "ALTER TABLE career_growth_review_versions "
                "DROP CONSTRAINT uq_career_growth_review_versions_latest_state",
                "ALTER TABLE career_growth_review_versions "
                "ADD CONSTRAINT fk_career_growth_review_versions_owner_predecessor "
                "FOREIGN KEY (owner_user_id, supersedes_version_id) "
                "REFERENCES career_growth_review_versions (owner_user_id, id) "
                "ON DELETE CASCADE",
                "ALTER TABLE career_growth_reviews "
                "ADD CONSTRAINT fk_career_growth_reviews_owner_latest_version "
                "FOREIGN KEY (owner_user_id, id, latest_version_id) "
                "REFERENCES career_growth_review_versions "
                "(owner_user_id, review_id, id) "
                "DEFERRABLE INITIALLY DEFERRED",
                "ALTER TABLE interview_questions "
                "DROP CONSTRAINT ck_interview_questions_ordinal_positive",
                "ALTER TABLE interview_questions "
                "DROP CONSTRAINT uq_interview_questions_owner_session_ordinal",
                "ALTER TABLE interview_questions DROP COLUMN ordinal",
                "ALTER TABLE interview_idempotency_records "
                "DROP CONSTRAINT "
                "ck_interview_idempotency_records_response_snapshot_scope_valid",
                "ALTER TABLE interview_idempotency_records DROP COLUMN response_snapshot",
                "ALTER TABLE networking_reminder_occurrences "
                "DROP CONSTRAINT fk_networking_occurrences_owner_reminder_contact",
                "ALTER TABLE networking_reminders "
                "DROP CONSTRAINT uq_networking_reminders_owner_id_contact",
                "ALTER TABLE networking_reminder_occurrences "
                "ADD CONSTRAINT fk_networking_occurrences_owner_reminder "
                "FOREIGN KEY (owner_user_id, reminder_id) "
                "REFERENCES networking_reminders (owner_user_id, id) "
                "ON DELETE CASCADE",
                "ALTER TABLE networking_reminder_occurrences "
                "DROP CONSTRAINT "
                "ck_networking_reminder_occurrences_networking_occurrenc_6c3f",
                "ALTER TABLE networking_reminder_occurrences DROP COLUMN trace_id",
                "ALTER TABLE networking_reminder_outbox "
                "DROP CONSTRAINT "
                "ck_networking_reminder_outbox_networking_outbox_trace_id_valid",
                "ALTER TABLE networking_reminder_outbox DROP COLUMN trace_id",
            )
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def _assert_phase9_schema_repairs(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            repaired_columns = await connection.execute(
                text(
                    "SELECT table_name, column_name "
                    "FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND (table_name, column_name) IN ("
                    "('career_analytics_snapshots', 'timezone'), "
                    "('interview_questions', 'ordinal'), "
                    "('interview_idempotency_records', 'response_snapshot'), "
                    "('networking_reminder_occurrences', 'trace_id'), "
                    "('networking_reminder_outbox', 'trace_id'))"
                )
            )
            assert set(repaired_columns) == {
                ("career_analytics_snapshots", "timezone"),
                ("interview_questions", "ordinal"),
                ("interview_idempotency_records", "response_snapshot"),
                ("networking_reminder_occurrences", "trace_id"),
                ("networking_reminder_outbox", "trace_id"),
            }
            repaired_checks = await connection.execute(
                text(
                    "SELECT conrelid::regclass::text "
                    "FROM pg_constraint "
                    "WHERE contype = 'c' AND ("
                    "(conrelid = 'interview_questions'::regclass "
                    "AND pg_get_constraintdef(oid) LIKE '%ordinal%') OR "
                    "(conrelid = 'interview_idempotency_records'::regclass "
                    "AND pg_get_constraintdef(oid) LIKE '%response_snapshot%') OR "
                    "(conrelid = 'networking_reminder_occurrences'::regclass "
                    "AND pg_get_constraintdef(oid) LIKE '%trace_id%') OR "
                    "(conrelid = 'networking_reminder_outbox'::regclass "
                    "AND pg_get_constraintdef(oid) LIKE '%trace_id%'))"
                )
            )
            assert {str(row[0]) for row in repaired_checks} == {
                "interview_questions",
                "interview_idempotency_records",
                "networking_reminder_occurrences",
                "networking_reminder_outbox",
            }
    finally:
        await engine.dispose()


async def _assert_new_constraints(
    database_url: str,
    owner_id: UUID,
    other_id: UUID,
    entity_id: UUID,
) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM career_entity_confirmations")
            )
            assert count == 0

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO career_entity_confirmations "
                        "(entity_id, owner_user_id, state, version, updated_at, "
                        "confirmed_at) VALUES (:entity, :owner, 'needs_review', "
                        "1, now(), NULL)"
                    ),
                    {"entity": entity_id, "owner": other_id},
                )

        async with engine.connect() as connection:
            profile_id = await connection.scalar(
                text(
                    "SELECT profile_id FROM career_entities "
                    "WHERE owner_user_id = :owner AND id = :entity"
                ),
                {"owner": owner_id, "entity": entity_id},
            )
        assert isinstance(profile_id, UUID)
        first_fact = uuid4()
        second_fact = uuid4()
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO career_personal_facts "
                    "(id, owner_user_id, profile_id, kind, value, value_sha256, "
                    "label, is_primary, confirmation, version, created_at, "
                    "updated_at, confirmed_at) "
                    "VALUES (:id, :owner, :profile, 'email', 'first@example.test', "
                    ":digest, NULL, true, 'needs_review', 1, now(), now(), NULL)"
                ),
                {
                    "id": first_fact,
                    "owner": owner_id,
                    "profile": profile_id,
                    "digest": bytes.fromhex("01" * 32),
                },
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO career_personal_facts "
                        "(id, owner_user_id, profile_id, kind, value, value_sha256, "
                        "label, is_primary, confirmation, version, created_at, "
                        "updated_at, confirmed_at) "
                        "VALUES (:id, :owner, :profile, 'email', "
                        "'second@example.test', :digest, NULL, true, "
                        "'needs_review', 1, now(), now(), NULL)"
                    ),
                    {
                        "id": second_fact,
                        "owner": owner_id,
                        "profile": profile_id,
                        "digest": bytes.fromhex("02" * 32),
                    },
                )
    finally:
        await engine.dispose()


def test_phase1_phase3_closure_upgrade_downgrade_and_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if configured_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(configured_url)
    database_name = f"careeros_phase13_closure_{uuid4().hex}"
    target_url = parsed_url.set(database=database_name).render_as_string(hide_password=False)
    admin_url = parsed_url.render_as_string(hide_password=False)
    asyncio.run(_create_database(admin_url, database_name))
    try:
        monkeypatch.setenv("CAREEROS_DATABASE_URL", target_url)
        monkeypatch.setenv("DATABASE_URL", target_url)
        monkeypatch.setenv("CAREEROS_ENVIRONMENT", "test")
        monkeypatch.setenv("ENVIRONMENT", "test")
        config = _alembic_config()

        command.upgrade(config, "20260724_0010")
        asyncio.run(_degrade_phase9_schema(target_url))
        owner_id, other_id, entity_id = asyncio.run(_insert_historical_entity(target_url))
        assert not (_NEW_TABLES & asyncio.run(_table_names(target_url)))

        command.upgrade(config, "20260726_0011")
        asyncio.run(_assert_phase9_schema_repairs(target_url))
        assert asyncio.run(_table_names(target_url)) >= _NEW_TABLES
        asyncio.run(
            _assert_new_constraints(
                target_url,
                owner_id,
                other_id,
                entity_id,
            )
        )
        command.upgrade(config, "head")
        command.check(config)

        command.downgrade(config, "20260724_0010")
        asyncio.run(_assert_phase9_schema_repairs(target_url))
        assert not (_NEW_TABLES & asyncio.run(_table_names(target_url)))
        command.upgrade(config, "head")
        command.check(config)
        assert asyncio.run(_table_names(target_url)) >= _NEW_TABLES
    finally:
        asyncio.run(_drop_database(admin_url, database_name))
