"""Owner-facing read path over the shared job catalog.

Deliberately separate from `JobMatchService.list_jobs` (owner-scoped saved
jobs) — see `job_catalog_ports.py` for why. Cross-module role/experience data
is read only through the injected `TargetRoleProvider` port, never by
importing role_readiness/career_record internals directly here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from rezumi.modules.job_match.application.job_catalog_ports import (
    CatalogJobListing,
    JobCatalogStore,
)

_DEFAULT_LIMIT = 25
_MAX_TARGET_ROLES = 5


class TargetRoleProvider(Protocol):
    async def target_role_titles(self, owner_user_id: UUID) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class JobCatalogSearchResult:
    target_role_titles: tuple[str, ...]
    listings: tuple[CatalogJobListing, ...]
    matched_target_role: bool


class JobCatalogQueryService:
    def __init__(
        self,
        *,
        store: JobCatalogStore,
        target_roles: TargetRoleProvider,
    ) -> None:
        self._store = store
        self._target_roles = target_roles

    async def search_for_owner(
        self, owner_user_id: UUID, *, limit: int = _DEFAULT_LIMIT
    ) -> JobCatalogSearchResult:
        titles = (await self._target_roles.target_role_titles(owner_user_id))[
            :_MAX_TARGET_ROLES
        ]
        keywords = tuple({word for title in titles for word in title.split() if word})
        listings = await self._store.search(keywords=keywords, limit=limit)
        matched = bool(keywords) and bool(listings)
        if keywords and not listings:
            # A role title that happens not to text-match any current listing
            # (e.g. a niche or oddly-worded title) must not leave the owner
            # looking at an empty section — fall back to recent listings and
            # say so, rather than silently showing nothing.
            listings = await self._store.search(keywords=(), limit=limit)
        return JobCatalogSearchResult(
            target_role_titles=titles, listings=listings, matched_target_role=matched
        )

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None:
        return await self._store.get_listing(platform, external_id)
