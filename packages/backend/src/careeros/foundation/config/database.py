"""Database configuration primitives independent of any deployable settings model."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
_DEVELOPMENT_PASSWORDS = frozenset(
    {
        "",
        "careeros",
        "change-me",
        "change-me-local-only",
        "changeme",
        "password",
    }
)


def parse_async_postgresql_url(value: str) -> URL:
    """Parse and require the asyncpg SQLAlchemy driver without exposing credentials."""
    try:
        url = make_url(value)
    except ArgumentError as exc:
        raise ValueError("database_url must be a valid SQLAlchemy URL") from exc
    if url.drivername != "postgresql+asyncpg":
        raise ValueError("database_url must use the postgresql+asyncpg driver")
    return url


def validate_database_url_for_environment(value: str, environment: str) -> URL:
    """Reject known development database settings when running in production."""
    if environment not in _ENVIRONMENTS:
        choices = ", ".join(sorted(_ENVIRONMENTS))
        raise ValueError(f"environment must be one of: {choices}")

    url = parse_async_postgresql_url(value)
    if environment != "production":
        return url

    violations: list[str] = []
    if url.host in {"localhost", "127.0.0.1", "::1"}:
        violations.append("database URL must not target a loopback host")
    if (url.password or "").casefold() in _DEVELOPMENT_PASSWORDS:
        violations.append("the development database credential must be replaced")
    if violations:
        raise ValueError("Unsafe production database configuration: " + "; ".join(violations))
    return url


def database_url_from_environment(values: Mapping[str, str] | None = None) -> str:
    """Load the migration DSN without coupling Alembic to the API settings class."""
    source = environ if values is None else values
    value = source.get("CAREEROS_DATABASE_URL") or source.get("DATABASE_URL")
    if not value:
        raise RuntimeError(
            "CAREEROS_DATABASE_URL (or DATABASE_URL) is required for database migrations"
        )
    environment = source.get("CAREEROS_ENVIRONMENT") or source.get("ENVIRONMENT") or "development"
    validate_database_url_for_environment(value, environment)
    return value


@dataclass(frozen=True, slots=True)
class DatabaseOptions:
    """Validated engine options; the URL is deliberately excluded from repr output."""

    url: str = field(repr=False)
    pool_size: int = 5
    max_overflow: int = 10
    connect_timeout_seconds: float = 3.0
    command_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parse_async_postgresql_url(self.url)
        if not 1 <= self.pool_size <= 50:
            raise ValueError("pool_size must be between 1 and 50")
        if not 0 <= self.max_overflow <= 100:
            raise ValueError("max_overflow must be between 0 and 100")
        if not 0 < self.connect_timeout_seconds <= 30:
            raise ValueError("connect_timeout_seconds must be greater than 0 and at most 30")
        if not 0 < self.command_timeout_seconds <= 300:
            raise ValueError("command_timeout_seconds must be greater than 0 and at most 300")
