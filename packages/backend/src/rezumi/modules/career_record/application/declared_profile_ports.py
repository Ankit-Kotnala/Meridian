"""Ports for declared-link profile enrichment (Phase 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit

from rezumi.modules.career_record.domain.errors import (
    CareerRecordConflict,
    CareerRecordValidationError,
)


@dataclass(frozen=True, slots=True)
class DeclaredProfileAchievement:
    """One public achievement extracted from a user-declared profile URL."""

    title: str
    statement: str
    source_url: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class DeclaredProfileFetchResult:
    platform: str
    profile_url: str
    fetched_at: datetime
    achievements: tuple[DeclaredProfileAchievement, ...]


class DeclaredProfileConnector(Protocol):
    """Fetch public achievements from a single declared profile URL."""

    platform: str

    def supports(self, url: str) -> bool:
        """Return true when this connector owns the declared URL host/path."""

    async def fetch(self, url: str) -> DeclaredProfileFetchResult:
        """Fetch achievements from the declared public profile."""


class DeclaredProfileUnsupported(CareerRecordValidationError):
    """Raised when no connector may fetch the declared URL."""


class DeclaredProfileFetchFailed(CareerRecordConflict):
    """Raised when a permitted fetch fails safely."""


def normalize_declared_profile_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise CareerRecordValidationError("profile link must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise CareerRecordValidationError("profile link must not contain credentials")
    return url.strip()


def hostname(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold().removeprefix("www.")
