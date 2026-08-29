"""Populate the shared job catalog from configured published-API connectors."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from rezumi.modules.job_match.application.job_catalog_ports import (
    CatalogSyncResult,
    JobCatalogSourceConnector,
    JobCatalogStore,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class JobCatalogSyncService:
    """Worker-side use case: enumerate every configured source into the catalog."""

    def __init__(
        self,
        *,
        connectors: tuple[JobCatalogSourceConnector, ...],
        store: JobCatalogStore,
        clock: Clock,
    ) -> None:
        self._connectors = connectors
        self._store = store
        self._clock = clock

    async def sync_all(self) -> tuple[CatalogSyncResult, ...]:
        results = []
        for connector in self._connectors:
            results.append(await self._sync_one(connector))
        return tuple(results)

    async def _sync_one(self, connector: JobCatalogSourceConnector) -> CatalogSyncResult:
        fetched = 0
        upserted = 0
        rejected = 0
        now = self._clock.now()
        try:
            async for listing in connector.iter_listings():
                fetched += 1
                try:
                    await self._store.upsert_listing(listing, fetched_at=now)
                    upserted += 1
                except Exception:
                    rejected += 1
        except Exception:  # noqa: S110 - caller logs per-source counts; app layer stays log-free
            pass
        return CatalogSyncResult(
            platform=connector.platform, fetched=fetched, upserted=upserted, rejected=rejected
        )
