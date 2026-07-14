"""Async SQLAlchemy foundation for PostgreSQL."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from careeros_api.config import Settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for future domain models and Alembic metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ReadinessProbe(Protocol):
    """Minimal lifecycle contract used by the readiness endpoint."""

    async def ping(self) -> None: ...

    async def dispose(self) -> None: ...


class Database:
    """Own the async engine and session factory for one API process."""

    def __init__(self, settings: Settings) -> None:
        self._engine: AsyncEngine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            connect_args={
                "timeout": settings.database_connect_timeout_seconds,
                "command_timeout": settings.database_command_timeout_seconds,
            },
        )
        self._sessions = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session whose transaction boundary is owned by the caller."""
        async with self._sessions() as session:
            yield session

    async def ping(self) -> None:
        """Verify that PostgreSQL can execute a trivial query."""
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        """Release pooled connections during process shutdown."""
        await self._engine.dispose()
