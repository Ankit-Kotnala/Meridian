"""Adapter that reads a user's confirmed skill names from Career Record.

Only the application-layer `CareerRecordService` is imported here, never
`career_record.domain` internals — the same boundary job_match's
`CompositeTargetRoleProvider` already follows for cross-module reads.
"""

from __future__ import annotations

from uuid import UUID

from rezumi.modules.career_record.application.service import CareerRecordService


class CareerRecordSkillsProvider:
    def __init__(self, service: CareerRecordService) -> None:
        self._service = service

    async def list_skill_names(self, owner_user_id: UUID) -> tuple[str, ...]:
        skills = await self._service.list_skills(owner_user_id)
        return tuple(skill.name for skill in skills if skill.name)
