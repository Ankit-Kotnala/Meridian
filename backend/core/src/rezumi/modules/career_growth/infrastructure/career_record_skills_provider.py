"""Adapter that reads evidence-demonstrated skills from Career Record.

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

    async def list_demonstrated_skill_names(self, owner_user_id: UUID) -> tuple[str, ...]:
        snapshot = await self._service.readiness_snapshot(
            owner_user_id,
            evidence_limit=2_000,
        )
        demonstrated_skill_ids = {
            skill_id for evidence in snapshot.evidence for skill_id in evidence.skill_ids
        }
        return tuple(
            skill.name
            for skill in snapshot.skills
            if skill.name and skill.id in demonstrated_skill_ids
        )
