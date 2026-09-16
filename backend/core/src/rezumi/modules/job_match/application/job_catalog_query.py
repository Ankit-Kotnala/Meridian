"""Owner-facing read path over the shared job catalog.

Deliberately separate from `JobMatchService.list_jobs` (owner-scoped saved
jobs) — see `job_catalog_ports.py` for why. Cross-module role/experience data
is read only through the injected `TargetRoleProvider` port, never by
importing role_readiness/career_record internals directly here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from rezumi.modules.job_match.application.job_catalog_ports import (
    CatalogJobListing,
    JobCatalogStore,
)

_DEFAULT_LIMIT = 50
_MAX_TARGET_ROLES = 5
_MAX_BROWSE_LIMIT = 100
_MAX_BROWSE_OFFSET = 100_000
_MAX_TRACKED_EXTERNAL_ID = 200
# Keep in lockstep with JobMatchService idempotency keys: `/` is not allowed.
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def catalog_save_keys(platform: str, external_id: str) -> tuple[str, str]:
    """Return (idempotency_key, tracked_external_id) for copying a catalog listing.

    Himalayas listings use HTTPS URLs as external ids. Those values are valid
    catalog keys but are not valid Job Match idempotency keys and can exceed
    the 200-character job ``external_id`` column.
    """
    raw_idempotency = f"catalog:{platform}:{external_id}"
    if _IDEMPOTENCY_KEY.fullmatch(raw_idempotency) is None:
        digest = hashlib.sha256(raw_idempotency.encode("utf-8")).hexdigest()
        idempotency_key = f"catalog:{digest}"
    else:
        idempotency_key = raw_idempotency
    tracked = f"{platform}:{external_id}"
    if len(tracked) > _MAX_TRACKED_EXTERNAL_ID:
        digest = hashlib.sha256(tracked.encode("utf-8")).hexdigest()
        tracked = f"{platform}:{digest}"
    return idempotency_key, tracked


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


@dataclass(frozen=True, slots=True)
class JobCatalogBrowseResult:
    listings: tuple[CatalogJobListing, ...]
    has_more: bool
    next_offset: int
    total_count: int


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
        suggested = (await self._target_roles.target_role_titles(owner_user_id))[:_MAX_TARGET_ROLES]
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
        self,
        *,
        query: str,
        limit: int,
        offset: int,
        platform: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        work_model: str | None = None,
    ) -> JobCatalogBrowseResult:
        """Free-text search across the whole catalog, independent of role filtering."""

        bounded_limit = max(1, min(limit, _MAX_BROWSE_LIMIT))
        bounded_offset = max(0, min(offset, _MAX_BROWSE_OFFSET))
        keywords = tuple(word for word in query.split() if word)
        normalized_platform = platform.strip() if platform and platform.strip() else None
        normalized_location = location.strip() if location and location.strip() else None
        normalized_seniority = seniority.strip() if seniority and seniority.strip() else None
        normalized_work_model = work_model.strip() if work_model and work_model.strip() else None
        listings = await self._store.search(
            keywords=keywords,
            limit=bounded_limit + 1,
            offset=bounded_offset,
            platform=normalized_platform,
            location=normalized_location,
            seniority=normalized_seniority,
            work_model=normalized_work_model,
        )
        total_count = await self._store.count(
            keywords=keywords,
            platform=normalized_platform,
            location=normalized_location,
            seniority=normalized_seniority,
            work_model=normalized_work_model,
        )
        has_more = len(listings) > bounded_limit
        page = listings[:bounded_limit]
        return JobCatalogBrowseResult(
            listings=page,
            has_more=has_more,
            next_offset=bounded_offset + len(page),
            total_count=total_count,
        )

    async def get_listing(self, platform: str, external_id: str) -> CatalogJobListing | None:
        return await self._store.get_listing(platform, external_id)
