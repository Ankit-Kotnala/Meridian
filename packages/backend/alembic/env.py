"""Alembic environment using shared metadata and environment configuration."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from careeros.foundation.config import database_url_from_environment
from careeros.foundation.database import Base
from careeros.modules.application_workspace.infrastructure import (
    models as application_workspace_models,  # noqa: F401
)
from careeros.modules.career_record.infrastructure import (
    models as career_record_models,  # noqa: F401
)
from careeros.modules.change_studio.infrastructure import (
    models as change_studio_models,  # noqa: F401
)
from careeros.modules.identity.infrastructure import models as identity_models  # noqa: F401
from careeros.modules.job_match.infrastructure import models as job_match_models  # noqa: F401
from careeros.modules.resume_builder.infrastructure import (
    models as resume_builder_models,  # noqa: F401
)
from careeros.modules.resume_health.infrastructure import (
    models as resume_health_models,  # noqa: F401
)
from careeros.modules.role_readiness.infrastructure import (
    models as role_readiness_models,  # noqa: F401
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    """Retrieve the DSN without storing it in the Alembic Config object."""
    return database_url_from_environment()


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(run_sync_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
