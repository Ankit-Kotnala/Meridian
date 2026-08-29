"""Resolve an owner's target role titles for job-catalog matching.

Prefers the roles a user has explicitly saved in Role Readiness; falls back
to the title of their current (or most recent) Career Record experience
entity when nothing is explicitly saved. No new "target role" concept is
introduced — this composes two existing, already-owned signals.
"""

from __future__ import annotations

from uuid import UUID

from rezumi.modules.career_record.application.service import CareerRecordService
from rezumi.modules.role_readiness.application.service import RoleReadinessService

_MAX_SAVED_ROLES = 5
# CareerEntity.kind is a StrEnum whose EXPERIENCE member equals this string —
# compared by value here instead of importing career_record's domain enum, to
# keep this cross-module read behind the application boundary only.
_EXPERIENCE_KIND = "experience"


class CompositeTargetRoleProvider:
    def __init__(
        self,
        *,
        role_readiness: RoleReadinessService,
        career_record: CareerRecordService,
    ) -> None:
        self._role_readiness = role_readiness
        self._career_record = career_record

    async def target_role_titles(self, owner_user_id: UUID) -> tuple[str, ...]:
        saved = await self._role_readiness.list_saved_roles(
            owner_user_id, limit=_MAX_SAVED_ROLES
        )
        titles = tuple(item.role.title for item in saved.data if item.role.title)
        if titles:
            return titles
        entities = await self._career_record.list_entities(owner_user_id)
        experiences = [entity for entity in entities if entity.kind == _EXPERIENCE_KIND]
        current = [entity for entity in experiences if entity.is_current]
        pool = current or experiences
        if not pool:
            return ()
        latest = max(pool, key=lambda entity: (entity.end_date is None, entity.sort_order))
        title = latest.display_title or latest.official_title or latest.title
        return (title,) if title else ()
