"""Forward-repair coverage for a pre-release Phase 8 development schema."""

from __future__ import annotations

import asyncio
import os
import re
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_PROVENANCE_COLUMNS = {
    "evidence_revision_id",
    "evidence_revision_number",
    "evidence_statement_sha256",
}


def _alembic_config() -> Config:
    config = Config(str(_PACKAGE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PACKAGE_ROOT / "alembic"))
    return config


async def _create_database(admin_url: str, database_name: str) -> None:
    assert re.fullmatch(r"careeros_phase9_repair_[0-9a-f]{32}", database_name)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql(
                f'CREATE DATABASE "{database_name}" TEMPLATE template0'
            )
    finally:
        await engine.dispose()


async def _drop_database(admin_url: str, database_name: str) -> None:
    assert re.fullmatch(r"careeros_phase9_repair_[0-9a-f]{32}", database_name)
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


async def _remove_phase8_provenance(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                """
                DO $$
                DECLARE
                    constraint_record record;
                BEGIN
                    FOR constraint_record IN
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'change_operation_claims'::regclass
                          AND contype = 'c'
                          AND pg_get_constraintdef(oid) LIKE '%evidence_revision_id%'
                          AND pg_get_constraintdef(oid) LIKE '%evidence_revision_number%'
                          AND pg_get_constraintdef(oid) LIKE '%evidence_statement_sha256%'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE change_operation_claims DROP CONSTRAINT %I',
                            constraint_record.conname
                        );
                    END LOOP;
                END
                $$;
                """
            )
            for column in sorted(_PROVENANCE_COLUMNS):
                await connection.exec_driver_sql(
                    f"ALTER TABLE change_operation_claims DROP COLUMN {column}"
                )
    finally:
        await engine.dispose()


async def _replace_phase8_enums_with_pre_release_values(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                """
                DO $$
                DECLARE
                    constraint_record record;
                BEGIN
                    FOR constraint_record IN
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'application_events'::regclass
                          AND contype = 'c'
                          AND pg_get_constraintdef(oid) LIKE '%event_kind%'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE application_events DROP CONSTRAINT %I',
                            constraint_record.conname
                        );
                    END LOOP;
                END
                $$;
                """
            )
            await connection.exec_driver_sql(
                """
                DO $$
                DECLARE
                    constraint_record record;
                BEGIN
                    FOR constraint_record IN
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid =
                            'application_workspace_audit_events'::regclass
                          AND contype = 'c'
                          AND pg_get_constraintdef(oid) LIKE '%action%'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE application_workspace_audit_events '
                            'DROP CONSTRAINT %I',
                            constraint_record.conname
                        );
                    END LOOP;
                END
                $$;
                """
            )
            await connection.exec_driver_sql(
                """
                ALTER TABLE application_events
                ADD CONSTRAINT ck_phase8_legacy_event_kind
                CHECK (
                    event_kind IN (
                        'created','stage_changed','deadline_changed',
                        'follow_up_changed','note_added','task_added',
                        'task_completed','pack_generated','outcome_recorded',
                        'interview','contact','custom'
                    )
                )
                """
            )
            await connection.exec_driver_sql(
                """
                ALTER TABLE application_workspace_audit_events
                ADD CONSTRAINT ck_phase8_legacy_audit_action
                CHECK (
                    action IN (
                        'application_created','application_updated',
                        'application_stage_changed','application_deleted',
                        'task_created','task_updated','note_created',
                        'event_recorded','pack_generated','document_deleted'
                    )
                )
                """
            )
    finally:
        await engine.dispose()


async def _assert_phase8_provenance_present(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = current_schema() "
                            "AND table_name = 'change_operation_claims'"
                        )
                    )
                )
                .scalars()
                .all()
            )
            constraints = list(
                (
                    await connection.execute(
                        text(
                            "SELECT pg_get_constraintdef(oid) "
                            "FROM pg_constraint "
                            "WHERE conrelid = 'change_operation_claims'::regclass "
                            "AND contype = 'c'"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert columns >= _PROVENANCE_COLUMNS
        assert any(
            all(column_name in definition for column_name in _PROVENANCE_COLUMNS)
            for definition in constraints
        )
    finally:
        await engine.dispose()


async def _assert_phase8_enums_current(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            for table_name, column_name in (
                ("application_events", "event_kind"),
                ("application_workspace_audit_events", "action"),
            ):
                definitions = (
                    (
                        await connection.execute(
                            text(
                                "SELECT pg_get_constraintdef(oid) "
                                "FROM pg_constraint "
                                "WHERE conrelid = CAST(:table_name AS regclass) "
                                "AND contype = 'c'"
                            ),
                            {"table_name": table_name},
                        )
                    )
                    .scalars()
                    .all()
                )
                assert any(
                    column_name in definition and "resume_version_changed" in definition
                    for definition in definitions
                )
    finally:
        await engine.dispose()


async def _expect_integrity_error(
    database_url: str,
    statement: str,
    parameters: dict[str, object],
) -> None:
    engine = create_async_engine(database_url)
    try:
        try:
            async with engine.begin() as connection:
                await connection.execute(text(statement), parameters)
        except IntegrityError as error:
            assert getattr(error.orig, "sqlstate", None) == "23503"
            return
        raise AssertionError("the invalid Phase 9 relationship was accepted")
    finally:
        await engine.dispose()


async def _assert_phase9_growth_relational_integrity(database_url: str) -> None:
    owner_id = uuid4()
    other_owner_id = uuid4()
    evidence_id = uuid4()
    evidence_revision_id = uuid4()
    other_evidence_id = uuid4()
    other_evidence_revision_id = uuid4()
    cross_owner_evidence_id = uuid4()
    cross_owner_evidence_revision_id = uuid4()
    goal_id = uuid4()
    review_id = uuid4()
    review_version_id = uuid4()
    other_review_id = uuid4()
    other_review_version_id = uuid4()
    valid_link_id = uuid4()

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email_normalized, password_hash, status,
                        email_verified_at, auth_version, created_at, updated_at
                    )
                    VALUES (
                        :owner_id, :owner_email, NULL, 'active',
                        NULL, 1, now(), now()
                    ), (
                        :other_owner_id, :other_owner_email, NULL, 'active',
                        NULL, 1, now(), now()
                    )
                    """
                ),
                {
                    "owner_id": owner_id,
                    "owner_email": f"{owner_id}@phase9-integrity.example.test",
                    "other_owner_id": other_owner_id,
                    "other_owner_email": (f"{other_owner_id}@phase9-integrity.example.test"),
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO evidence_items (
                        id, owner_user_id, lifecycle, current_revision, version,
                        created_at, updated_at, archived_at, deleted_at
                    )
                    VALUES
                        (
                            :evidence_id, :owner_id, 'active', 1, 1,
                            now(), now(), NULL, NULL
                        ),
                        (
                            :other_evidence_id, :owner_id, 'active', 1, 1,
                            now(), now(), NULL, NULL
                        ),
                        (
                            :cross_owner_evidence_id, :other_owner_id,
                            'active', 1, 1, now(), now(), NULL, NULL
                        )
                    """
                ),
                {
                    "owner_id": owner_id,
                    "other_owner_id": other_owner_id,
                    "evidence_id": evidence_id,
                    "other_evidence_id": other_evidence_id,
                    "cross_owner_evidence_id": cross_owner_evidence_id,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO evidence_revisions (
                        id, owner_user_id, evidence_id, revision,
                        evidence_type, title, statement, strength, input_kind,
                        created_at
                    )
                    VALUES
                        (
                            :evidence_revision_id, :owner_id, :evidence_id, 1,
                            'achievement', 'Evidence A', 'Evidence statement A',
                            'confirmed', 'manual',
                            TIMESTAMPTZ '2026-07-25 00:00:00+00'
                        ),
                        (
                            :other_evidence_revision_id, :owner_id,
                            :other_evidence_id, 1, 'achievement', 'Evidence B',
                            'Evidence statement B', 'confirmed', 'manual',
                            TIMESTAMPTZ '2026-07-25 00:00:00+00'
                        ),
                        (
                            :cross_owner_evidence_revision_id, :other_owner_id,
                            :cross_owner_evidence_id, 1, 'achievement',
                            'Evidence C', 'Evidence statement C',
                            'confirmed', 'manual',
                            TIMESTAMPTZ '2026-07-25 00:00:00+00'
                        )
                    """
                ),
                {
                    "owner_id": owner_id,
                    "other_owner_id": other_owner_id,
                    "evidence_id": evidence_id,
                    "evidence_revision_id": evidence_revision_id,
                    "other_evidence_id": other_evidence_id,
                    "other_evidence_revision_id": other_evidence_revision_id,
                    "cross_owner_evidence_id": cross_owner_evidence_id,
                    "cross_owner_evidence_revision_id": (cross_owner_evidence_revision_id),
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO career_growth_goals (
                        id, owner_user_id, title, description, status,
                        target_date, version, created_at, updated_at
                    )
                    VALUES (
                        :goal_id, :owner_id, 'Integrity goal', NULL, 'active',
                        NULL, 1, now(), now()
                    )
                    """
                ),
                {"goal_id": goal_id, "owner_id": owner_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO career_growth_reviews (
                        id, owner_user_id, cadence, period_start, period_end,
                        latest_version_id, latest_version_number, latest_status,
                        version, created_at, updated_at
                    )
                    VALUES
                        (
                            :review_id, :owner_id, 'quarterly',
                            DATE '2026-01-01', DATE '2026-03-31',
                            :review_version_id, 1, 'draft', 1, now(), now()
                        ),
                        (
                            :other_review_id, :owner_id, 'quarterly',
                            DATE '2026-04-01', DATE '2026-06-30',
                            :other_review_version_id, 1, 'draft', 1, now(), now()
                        )
                    """
                ),
                {
                    "owner_id": owner_id,
                    "review_id": review_id,
                    "review_version_id": review_version_id,
                    "other_review_id": other_review_id,
                    "other_review_version_id": other_review_version_id,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO career_growth_review_versions (
                        id, owner_user_id, review_id, version_number, status,
                        title, summary, achievements, growth_areas, next_focus,
                        change_reason, material_change, supersedes_version_id,
                        content_sha256, created_at
                    )
                    VALUES
                        (
                            :review_version_id, :owner_id, :review_id, 1,
                            'draft', 'Review A', 'Review A summary', NULL, NULL,
                            NULL, 'Initial version', TRUE, NULL,
                            decode(repeat('01', 32), 'hex'), now()
                        ),
                        (
                            :other_review_version_id, :owner_id,
                            :other_review_id, 1, 'draft', 'Review B',
                            'Review B summary', NULL, NULL, NULL,
                            'Initial version', TRUE, NULL,
                            decode(repeat('02', 32), 'hex'), now()
                        )
                    """
                ),
                {
                    "owner_id": owner_id,
                    "review_id": review_id,
                    "review_version_id": review_version_id,
                    "other_review_id": other_review_id,
                    "other_review_version_id": other_review_version_id,
                },
            )
    finally:
        await engine.dispose()

    link_statement = """
        INSERT INTO career_growth_evidence_links (
            id, owner_user_id, target_kind, target_id, evidence_id,
            evidence_revision_id, revision_number, statement_sha256,
            evidence_revised_at, created_at
        )
        VALUES (
            :id, :owner_id, 'goal', :target_id, :evidence_id,
            :evidence_revision_id, :revision_number,
            sha256(convert_to(:statement, 'UTF8')),
            TIMESTAMPTZ '2026-07-25 00:00:00+00', now()
        )
    """
    await _expect_integrity_error(
        database_url,
        link_statement,
        {
            "id": uuid4(),
            "owner_id": owner_id,
            "target_id": uuid4(),
            "evidence_id": evidence_id,
            "evidence_revision_id": evidence_revision_id,
            "revision_number": 1,
            "statement": "Evidence statement A",
        },
    )
    await _expect_integrity_error(
        database_url,
        link_statement,
        {
            "id": uuid4(),
            "owner_id": other_owner_id,
            "target_id": goal_id,
            "evidence_id": cross_owner_evidence_id,
            "evidence_revision_id": cross_owner_evidence_revision_id,
            "revision_number": 1,
            "statement": "Evidence statement C",
        },
    )
    await _expect_integrity_error(
        database_url,
        link_statement,
        {
            "id": uuid4(),
            "owner_id": owner_id,
            "target_id": goal_id,
            "evidence_id": evidence_id,
            "evidence_revision_id": other_evidence_revision_id,
            "revision_number": 1,
            "statement": "Evidence statement A",
        },
    )
    await _expect_integrity_error(
        database_url,
        link_statement,
        {
            "id": uuid4(),
            "owner_id": owner_id,
            "target_id": goal_id,
            "evidence_id": evidence_id,
            "evidence_revision_id": evidence_revision_id,
            "revision_number": 2,
            "statement": "Evidence statement A",
        },
    )
    await _expect_integrity_error(
        database_url,
        link_statement,
        {
            "id": uuid4(),
            "owner_id": owner_id,
            "target_id": goal_id,
            "evidence_id": evidence_id,
            "evidence_revision_id": evidence_revision_id,
            "revision_number": 1,
            "statement": "Tampered evidence statement",
        },
    )
    await _expect_integrity_error(
        database_url,
        """
        INSERT INTO career_growth_review_versions (
            id, owner_user_id, review_id, version_number, status,
            title, summary, achievements, growth_areas, next_focus,
            change_reason, material_change, supersedes_version_id,
            content_sha256, created_at
        )
        VALUES (
            :id, :owner_id, :review_id, 2, 'draft',
            'Invalid successor', 'Invalid cross-review predecessor',
            NULL, NULL, NULL, 'Invalid predecessor', TRUE,
            :other_review_version_id, decode(repeat('04', 32), 'hex'), now()
        )
        """,
        {
            "id": uuid4(),
            "owner_id": owner_id,
            "review_id": review_id,
            "other_review_version_id": other_review_version_id,
        },
    )
    await _expect_integrity_error(
        database_url,
        """
        INSERT INTO career_growth_review_versions (
            id, owner_user_id, review_id, version_number, status,
            title, summary, achievements, growth_areas, next_focus,
            change_reason, material_change, supersedes_version_id,
            content_sha256, created_at
        )
        VALUES (
            :id, :owner_id, :review_id, 3, 'draft',
            'Skipped successor', 'The immediate predecessor was skipped.',
            NULL, NULL, NULL, 'Invalid predecessor', TRUE,
            :review_version_id, decode(repeat('05', 32), 'hex'), now()
        )
        """,
        {
            "id": uuid4(),
            "owner_id": owner_id,
            "review_id": review_id,
            "review_version_id": review_version_id,
        },
    )
    await _expect_integrity_error(
        database_url,
        """
        UPDATE career_growth_reviews
        SET latest_version_id = :other_review_version_id
        WHERE owner_user_id = :owner_id AND id = :review_id
        """,
        {
            "other_review_version_id": other_review_version_id,
            "owner_id": owner_id,
            "review_id": review_id,
        },
    )
    await _expect_integrity_error(
        database_url,
        """
        UPDATE career_growth_reviews
        SET latest_version_number = 2
        WHERE owner_user_id = :owner_id AND id = :review_id
        """,
        {"owner_id": owner_id, "review_id": review_id},
    )
    await _expect_integrity_error(
        database_url,
        """
        UPDATE career_growth_reviews
        SET latest_status = 'finalized'
        WHERE owner_user_id = :owner_id AND id = :review_id
        """,
        {"owner_id": owner_id, "review_id": review_id},
    )

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(link_statement),
                {
                    "id": valid_link_id,
                    "owner_id": owner_id,
                    "target_id": goal_id,
                    "evidence_id": evidence_id,
                    "evidence_revision_id": evidence_revision_id,
                    "revision_number": 1,
                    "statement": "Evidence statement A",
                },
            )
    finally:
        await engine.dispose()

    await _expect_integrity_error(
        database_url,
        """
        UPDATE career_growth_evidence_links
        SET revision_number = 2
        WHERE id = :id
        """,
        {"id": valid_link_id},
    )
    await _expect_integrity_error(
        database_url,
        """
        UPDATE career_growth_evidence_links
        SET statement_sha256 = decode(repeat('00', 32), 'hex')
        WHERE id = :id
        """,
        {"id": valid_link_id},
    )
    await _expect_integrity_error(
        database_url,
        """
        UPDATE career_growth_evidence_links
        SET evidence_revised_at = TIMESTAMPTZ '2026-07-25 00:00:01+00'
        WHERE id = :id
        """,
        {"id": valid_link_id},
    )


async def _assert_growth_target_insert_delete_is_serialized(database_url: str) -> None:
    owner_id = uuid4()
    evidence_id = uuid4()
    evidence_revision_id = uuid4()
    goal_id = uuid4()
    link_id = uuid4()
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email_normalized, password_hash, status,
                        email_verified_at, auth_version, created_at, updated_at
                    )
                    VALUES (
                        :owner_id, :owner_email, NULL, 'active',
                        NULL, 1, now(), now()
                    )
                    """
                ),
                {
                    "owner_id": owner_id,
                    "owner_email": f"{owner_id}@phase9-race.example.test",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO evidence_items (
                        id, owner_user_id, lifecycle, current_revision, version,
                        created_at, updated_at, archived_at, deleted_at
                    )
                    VALUES (
                        :evidence_id, :owner_id, 'active', 1, 1,
                        now(), now(), NULL, NULL
                    )
                    """
                ),
                {"evidence_id": evidence_id, "owner_id": owner_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO evidence_revisions (
                        id, owner_user_id, evidence_id, revision,
                        evidence_type, title, statement, strength, input_kind,
                        created_at
                    )
                    VALUES (
                        :evidence_revision_id, :owner_id, :evidence_id, 1,
                        'achievement', 'Race evidence', 'Race evidence statement',
                        'confirmed', 'manual',
                        TIMESTAMPTZ '2026-07-25 00:00:00+00'
                    )
                    """
                ),
                {
                    "evidence_revision_id": evidence_revision_id,
                    "owner_id": owner_id,
                    "evidence_id": evidence_id,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO career_growth_goals (
                        id, owner_user_id, title, description, status,
                        target_date, version, created_at, updated_at
                    )
                    VALUES (
                        :goal_id, :owner_id, 'Race goal', NULL, 'active',
                        NULL, 1, now(), now()
                    )
                    """
                ),
                {"goal_id": goal_id, "owner_id": owner_id},
            )

        link_connection = await engine.connect()
        delete_connection = await engine.connect()
        observer_connection = await engine.connect()
        link_transaction = await link_connection.begin()
        delete_transaction = await delete_connection.begin()
        delete_task: asyncio.Task[object] | None = None
        try:
            await link_connection.execute(
                text(
                    """
                    INSERT INTO career_growth_evidence_links (
                        id, owner_user_id, target_kind, target_id, evidence_id,
                        evidence_revision_id, revision_number, statement_sha256,
                        evidence_revised_at, created_at
                    )
                    VALUES (
                        :link_id, :owner_id, 'goal', :goal_id, :evidence_id,
                        :evidence_revision_id, 1,
                        sha256(convert_to('Race evidence statement', 'UTF8')),
                        TIMESTAMPTZ '2026-07-25 00:00:00+00', now()
                    )
                    """
                ),
                {
                    "link_id": link_id,
                    "owner_id": owner_id,
                    "goal_id": goal_id,
                    "evidence_id": evidence_id,
                    "evidence_revision_id": evidence_revision_id,
                },
            )
            delete_backend_pid = await delete_connection.scalar(text("SELECT pg_backend_pid()"))
            assert delete_backend_pid is not None
            delete_task = asyncio.create_task(
                delete_connection.execute(
                    text(
                        """
                        DELETE FROM career_growth_goals
                        WHERE owner_user_id = :owner_id
                          AND id = :goal_id
                        """
                    ),
                    {"owner_id": owner_id, "goal_id": goal_id},
                )
            )

            for _ in range(500):
                wait_event_type = await observer_connection.scalar(
                    text(
                        """
                        SELECT wait_event_type
                        FROM pg_stat_activity
                        WHERE pid = :backend_pid
                        """
                    ),
                    {"backend_pid": delete_backend_pid},
                )
                if wait_event_type == "Lock":
                    break
                if delete_task.done():
                    await delete_task
                    pytest.fail("target deletion was not blocked by the uncommitted evidence link")
                await asyncio.sleep(0.01)
            else:
                pytest.fail("target deletion did not enter a row-lock wait")

            await link_transaction.commit()
            await asyncio.wait_for(delete_task, timeout=5)
            await delete_transaction.commit()
        finally:
            if delete_task is not None and not delete_task.done():
                delete_task.cancel()
                with suppress(asyncio.CancelledError):
                    await delete_task
            if delete_transaction.is_active:
                await delete_transaction.rollback()
            if link_transaction.is_active:
                await link_transaction.rollback()
            await observer_connection.close()
            await delete_connection.close()
            await link_connection.close()

        async with engine.connect() as connection:
            target_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM career_growth_goals
                    WHERE owner_user_id = :owner_id
                      AND id = :goal_id
                    """
                ),
                {"owner_id": owner_id, "goal_id": goal_id},
            )
            link_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM career_growth_evidence_links
                    WHERE owner_user_id = :owner_id
                      AND id = :link_id
                    """
                ),
                {"owner_id": owner_id, "link_id": link_id},
            )
            assert target_count == 0
            assert link_count == 0
    finally:
        await engine.dispose()


def test_phase9_repairs_pre_release_phase8_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if configured_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(configured_url)
    database_name = f"careeros_phase9_repair_{uuid4().hex}"
    target_url = parsed_url.set(database=database_name).render_as_string(hide_password=False)
    admin_url = parsed_url.render_as_string(hide_password=False)
    asyncio.run(_create_database(admin_url, database_name))
    try:
        monkeypatch.setenv("CAREEROS_DATABASE_URL", target_url)
        monkeypatch.setenv("DATABASE_URL", target_url)
        monkeypatch.setenv("CAREEROS_ENVIRONMENT", "test")
        monkeypatch.setenv("ENVIRONMENT", "test")
        config = _alembic_config()

        command.upgrade(config, "20260724_0009")
        command.upgrade(config, "20260724_0010")
        command.upgrade(config, "head")
        command.check(config)
        command.downgrade(config, "20260724_0009")

        asyncio.run(_remove_phase8_provenance(target_url))
        asyncio.run(_replace_phase8_enums_with_pre_release_values(target_url))
        command.upgrade(config, "20260724_0010")
        asyncio.run(_assert_phase8_provenance_present(target_url))
        asyncio.run(_assert_phase8_enums_current(target_url))
        command.upgrade(config, "head")
        command.check(config)

        command.downgrade(config, "20260724_0009")
        asyncio.run(_assert_phase8_provenance_present(target_url))
        asyncio.run(_assert_phase8_enums_current(target_url))
        command.upgrade(config, "20260724_0010")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        asyncio.run(_drop_database(admin_url, database_name))


def test_phase9_growth_relationships_are_database_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if configured_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(configured_url)
    database_name = f"careeros_phase9_repair_{uuid4().hex}"
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
        command.upgrade(config, "head")
        command.check(config)
        asyncio.run(_assert_phase9_growth_relational_integrity(target_url))
        command.downgrade(config, "20260724_0009")
        command.upgrade(config, "20260724_0010")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        asyncio.run(_drop_database(admin_url, database_name))


def test_phase9_growth_target_delete_waits_for_uncommitted_evidence_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if configured_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(configured_url)
    database_name = f"careeros_phase9_repair_{uuid4().hex}"
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
        command.upgrade(config, "head")
        command.check(config)
        asyncio.run(_assert_growth_target_insert_delete_is_serialized(target_url))
    finally:
        asyncio.run(_drop_database(admin_url, database_name))
