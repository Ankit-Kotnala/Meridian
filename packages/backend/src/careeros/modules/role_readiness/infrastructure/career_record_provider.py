"""Application-boundary adapter from Career Record to Role Readiness scoring."""

from __future__ import annotations

from uuid import UUID

from careeros.modules.career_record.application import CareerRecordService
from careeros.modules.role_readiness.domain.scoring import (
    CareerReadinessSnapshot,
    SnapshotEntity,
    SnapshotEvidence,
    SnapshotSkill,
)


class CareerRecordSnapshotProvider:
    """Consume only the Career Record application snapshot, never its tables."""

    def __init__(self, service: CareerRecordService, *, evidence_limit: int = 100) -> None:
        self._service = service
        self._evidence_limit = evidence_limit

    async def snapshot(self, owner_user_id: UUID) -> CareerReadinessSnapshot:
        source = await self._service.readiness_snapshot(
            owner_user_id, evidence_limit=self._evidence_limit
        )
        return CareerReadinessSnapshot(
            skills=tuple(
                SnapshotSkill(
                    id=skill.id,
                    name=skill.name,
                    category=skill.category,
                    proficiency=skill.proficiency,
                )
                for skill in source.skills
            ),
            entities=tuple(
                SnapshotEntity(
                    id=entity.id,
                    kind=entity.kind,
                    title=entity.title,
                    organization=entity.organization,
                    description=entity.description,
                )
                for entity in source.entities
            ),
            evidence=tuple(
                SnapshotEvidence(
                    id=evidence.id,
                    title=evidence.title,
                    statement=evidence.statement,
                    context=evidence.context,
                    strength=evidence.strength,
                    skill_ids=evidence.skill_ids,
                    entity_ids=evidence.entity_ids,
                    has_numeric_claim=evidence.has_numeric_claim,
                )
                for evidence in source.evidence
            ),
        )
