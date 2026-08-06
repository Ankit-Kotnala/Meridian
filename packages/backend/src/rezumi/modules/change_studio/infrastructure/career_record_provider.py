"""Application-boundary adapter from Career Record to Change Studio grounding."""

from __future__ import annotations

import hashlib
from uuid import UUID

from rezumi.modules.career_record.application import CareerRecordNotFound, CareerRecordService
from rezumi.modules.change_studio.domain import (
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
        unique_ids = tuple(dict.fromkeys(evidence_ids))
        if not unique_ids:
            return ()
        try:
            records = await self._service.get_evidence_batch_with_eligibility(
                owner_user_id,
                unique_ids,
            )
        except CareerRecordNotFound:
            # Preserve the previous tolerant behavior for a stale or unauthorized
            # reference without penalizing the normal path with N database reads.
            fallback_records = []
            for evidence_id in unique_ids:
                try:
                    fallback_records.append(
                        await self._service.get_evidence_with_eligibility(
                            owner_user_id,
                            evidence_id,
                        )
                    )
                except CareerRecordNotFound:
                    continue
            records = tuple(fallback_records)

        contexts: list[EvidenceGroundingContext] = []
        for record, decision in records:
            if not decision.eligible:
                continue
            contexts.append(
                EvidenceGroundingContext(
                    id=record.item.id,
                    evidence_revision_id=record.revision.id,
                    revision_number=record.revision.revision,
                    statement_sha256=hashlib.sha256(
                        record.revision.statement.encode("utf-8")
                    ).hexdigest(),
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
