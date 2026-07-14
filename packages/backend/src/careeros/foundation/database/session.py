"""Async SQLAlchemy engine and session lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from careeros.foundation.config import DatabaseOptions


class ReadinessProbe(Protocol):
    """Minimal lifecycle contract used by deployable readiness checks."""

    async def ping(self) -> None: ...

    async def dispose(self) -> None: ...


class Database:
    """Own the async engine and session factory for one process."""

    def __init__(self, options: DatabaseOptions) -> None:
        self._engine: AsyncEngine = create_async_engine(
            options.url,
            pool_pre_ping=True,
            pool_size=options.pool_size,
            max_overflow=options.max_overflow,
            connect_args={
                "timeout": options.connect_timeout_seconds,
                "command_timeout": options.command_timeout_seconds,
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
