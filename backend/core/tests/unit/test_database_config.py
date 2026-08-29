"""Shared database configuration tests."""

import pytest

from rezumi.foundation.config import (
    DatabaseOptions,
    database_url_from_environment,
    parse_async_postgresql_url,
)
from rezumi.foundation.database import Database

ASYNC_DATABASE_URL = "postgresql+asyncpg://app:secret@database:5432/rezumi"


def test_database_options_redact_the_url_from_repr() -> None:
    options = DatabaseOptions(url=ASYNC_DATABASE_URL)

    assert "secret" not in repr(options)


def test_database_engine_hides_bound_parameters_from_errors_and_logs() -> None:
    database = Database(DatabaseOptions(url=ASYNC_DATABASE_URL))

    assert database._engine.sync_engine.hide_parameters is True


def test_database_url_environment_aliases_are_supported() -> None:
    assert database_url_from_environment({"DATABASE_URL": ASYNC_DATABASE_URL}) == ASYNC_DATABASE_URL


def test_database_url_is_required_for_migrations() -> None:
    with pytest.raises(RuntimeError, match="REZUMI_DATABASE_URL"):
        database_url_from_environment({})


def test_database_url_requires_asyncpg() -> None:
    with pytest.raises(ValueError, match="postgresql\\+asyncpg"):
        parse_async_postgresql_url("postgresql://app:secret@database/rezumi")


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://app:strong-secret@localhost:5432/rezumi",
        "postgresql+asyncpg://app:change-me-local-only@database:5432/rezumi",
    ],
)
def test_migration_database_url_rejects_unsafe_production_values(database_url: str) -> None:
    with pytest.raises(ValueError, match="Unsafe production database configuration"):
        database_url_from_environment(
            {
                "REZUMI_ENVIRONMENT": "production",
                "REZUMI_DATABASE_URL": database_url,
            }
        )


def test_migration_database_url_accepts_a_hardened_production_value() -> None:
    database_url = "postgresql+asyncpg://app:strong-secret@database:5432/rezumi"

    assert (
        database_url_from_environment(
            {
                "REZUMI_ENVIRONMENT": "production",
                "REZUMI_DATABASE_URL": database_url,
            }
        )
        == database_url
    )


def test_migration_environment_must_be_recognized() -> None:
    with pytest.raises(ValueError, match="environment must be one of"):
        database_url_from_environment(
            {
                "REZUMI_ENVIRONMENT": "prod",
                "REZUMI_DATABASE_URL": ASYNC_DATABASE_URL,
            }
        )
