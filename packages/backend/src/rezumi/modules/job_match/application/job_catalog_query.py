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


_MAX_BROWSE_LIMIT = 100


class TargetRoleProvider(Protocol):
    async def target_role_titles(self, owner_user_id: UUID) -> tuple[str, ...]: ...


class RolePreferenceProvider(Protocol):
    async def get_role_preference(self, owner_user_id: UUID) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class JobCatalogSearchResult:
    target_role_titles: tuple[str, ...]
    listings: tuple[CatalogJobListing, ...]
    matched_target_role: bool
    suggested_role_titles: tuple[str, ...] = ()
    selected_role_titles: tuple[str, ...] = ()


class JobCatalogQueryService:
    def __init__(
        self,
        *,
        store: JobCatalogStore,
        target_roles: TargetRoleProvider,
        role_preferences: RolePreferenceProvider | None = None,
    ) -> None:
        self._store = store
        self._target_roles = target_roles
        self._role_preferences = role_preferences

    async def search_for_owner(
        self, owner_user_id: UUID, *, limit: int = _DEFAULT_LIMIT
    ) -> JobCatalogSearchResult:
        suggested = (await self._target_roles.target_role_titles(owner_user_id))[
            :_MAX_TARGET_ROLES
        ]
        selected: tuple[str, ...] = ()
        if self._role_preferences is not None:
            selected = (await self._role_preferences.get_role_preference(owner_user_id))[
                :_MAX_TARGET_ROLES
            ]
        # An explicit selection always wins over the auto-suggested role —
        # the owner opted in/out on purpose.
        titles = selected or suggested
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
            target_role_titles=titles,
            listings=listings,
            matched_target_role=matched,
            suggested_role_titles=suggested,
            selected_role_titles=selected,
        )

    async def browse(
        self, *, query: str, limit: int, offset: int
    ) -> tuple[tuple[CatalogJobListing, ...], bool]:
        """Free-text search across the whole catalog, independent of role filtering."""

        bounded_limit = max(1, min(limit, _MAX_BROWSE_LIMIT))
        keywords = tuple(word for word in query.split() if word)
        listings = await self._store.search(
            keywords=keywords, limit=bounded_limit + 1, offset=max(0, offset)
        )
        has_more = len(listings) > bounded_limit
        return listings[:bounded_limit], has_more

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None:
        return await self._store.get_listing(platform, external_id)
