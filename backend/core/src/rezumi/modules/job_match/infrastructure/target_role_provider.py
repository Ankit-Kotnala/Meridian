"""Resolve an owner's role from Career Profile, resume, and career signals.

The explicit Career Profile target role is preferred, followed by resume role
signals, saved Role Readiness roles, the professional headline, and finally the
current or most recent Career Record experience title.
"""

from __future__ import annotations

from uuid import UUID

from rezumi.modules.career_record.application.service import CareerRecordService
from rezumi.modules.identity.application.service import IdentityService
from rezumi.modules.resume_builder.application.service import ResumeBuilderService
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
        identity: IdentityService | None = None,
        resume_builder: ResumeBuilderService | None = None,
    ) -> None:
        self._role_readiness = role_readiness
        self._career_record = career_record
        self._identity = identity
        self._resume_builder = resume_builder

    async def target_role_titles(self, owner_user_id: UUID) -> tuple[str, ...]:
        if self._identity is not None:
            target_role = await self._identity.get_target_role_preference(owner_user_id)
            if target_role:
                return (target_role,)
        if self._resume_builder is not None:
            resumes = await self._resume_builder.list_resumes(owner_user_id)
            for record in resumes.items:
                role = record.current_version.target_role or record.resume.target_role
                if role:
                    return (role,)
                entities = record.current_version.entities
                experiences = [entity for entity in entities if entity.kind == _EXPERIENCE_KIND]
                current = [entity for entity in experiences if entity.is_current]
                for entity in current or experiences:
                    role = entity.display_title or entity.official_title or entity.title
                    if role:
                        return (role,)
        saved = await self._role_readiness.list_saved_roles(owner_user_id, limit=_MAX_SAVED_ROLES)
        titles = tuple(item.role.title for item in saved.data if item.role.title)
        if titles:
            return titles
        career_profile = await self._career_record.get_profile(owner_user_id)
        if career_profile.profile.professional_headline:
            return (career_profile.profile.professional_headline,)
        career_experiences = [
            entity for entity in career_profile.entities if entity.kind == _EXPERIENCE_KIND
        ]
        current_career = [entity for entity in career_experiences if entity.is_current]
        pool = current_career or career_experiences
        if not pool:
            return ()
        latest = max(pool, key=lambda entity: (entity.end_date is None, entity.sort_order))
        title = latest.display_title or latest.official_title or latest.title
        return (title,) if title else ()
