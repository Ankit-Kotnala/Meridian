"""Application-boundary adapter from Career Record to Change Studio grounding."""

from __future__ import annotations

from uuid import UUID

from careeros.modules.career_record.application import CareerRecordNotFound, CareerRecordService
from careeros.modules.change_studio.domain import (
    EvidenceGroundingContext,
    MetricContext,
)


class CareerRecordChangeStudioEvidenceProvider:
    """Load only owner-scoped, generation-eligible evidence through Career Record."""

    def __init__(self, service: CareerRecordService) -> None:
        self._service = service

    async def evidence_contexts(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[EvidenceGroundingContext, ...]:
        contexts: list[EvidenceGroundingContext] = []
        seen: set[UUID] = set()
        for evidence_id in evidence_ids:
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            try:
                record, decision = await self._service.get_evidence_with_eligibility(
                    owner_user_id, evidence_id
                )
            except CareerRecordNotFound:
                continue
            if not decision.eligible:
                continue
            contexts.append(
                EvidenceGroundingContext(
                    id=record.item.id,
                    title=record.revision.title,
                    statement=record.revision.statement,
                    context=record.revision.context,
                    strength=record.revision.strength.value,
                    metrics=tuple(
                        MetricContext(
                            value=metric.value,
                            value_max=metric.value_max,
                            unit=metric.unit,
                            period=metric.period,
                            attribution=metric.attribution,
                        )
                        for metric in record.metrics
                        if metric.complete
                    ),
                )
            )
        return tuple(contexts)
