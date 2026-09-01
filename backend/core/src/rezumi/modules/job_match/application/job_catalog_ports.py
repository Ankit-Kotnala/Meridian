"""Ports for the shared, cross-owner job catalog.

This is deliberately separate from `job_source_ports.py`. That port
(`JobSourceConnector.fetch_listings(query)`) is shaped for the existing
synchronous, single-owner, single-board `sync_from_source` feature and must
not change. The catalog described here is a different read/write path: many
published sources, enumerated in bulk on a schedule, stored once and shared
across every owner, then filtered per owner at read time. It never writes
into the owner-scoped `job_postings` table directly — an owner explicitly
saves a catalog listing into their own tracked jobs through the existing
`JobMatchService` import path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CatalogJobListing:
    platform: str
    external_id: str
    title: str
    company: str | None
    location: str | None
    remote: bool | None
    application_url: str | None
    source_text: str
    posted_at: datetime | None


class JobCatalogSourceConnector(Protocol):
    """Enumerates every currently-open listing from one published source."""

    platform: str

    def iter_listings(self) -> AsyncIterator[CatalogJobListing]: ...


@dataclass(frozen=True, slots=True)
class CatalogSyncResult:
    platform: str
    fetched: int
    upserted: int
    rejected: int


class JobCatalogStore(Protocol):
    """Durable storage for the shared job catalog. One doc per (platform, external_id)."""

    async def ping(self) -> None: ...

    async def upsert_listing(self, listing: CatalogJobListing, *, fetched_at: datetime) -> None: ...

    async def search(
        self,
        *,
        keywords: tuple[str, ...],
        limit: int,
        offset: int = 0,
    ) -> tuple[CatalogJobListing, ...]: ...

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None: ...

    async def dispose(self) -> None: ...
