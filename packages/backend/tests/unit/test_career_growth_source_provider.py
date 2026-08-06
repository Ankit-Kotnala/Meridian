"""Career Growth source minimization and achievement-cohort tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from rezumi.modules.career_growth.infrastructure.career_record_provider import (
    CareerRecordGrowthSourceProvider,
)
from rezumi.modules.career_record.domain import EvidenceStrength, EvidenceType

OWNER_ID = UUID("00000000-0000-4000-8000-000000009801")
SKILL_ID = UUID("00000000-0000-4000-8000-000000009802")
ACHIEVEMENT_ID = UUID("00000000-0000-4000-8000-000000009803")
NOTE_ID = UUID("00000000-0000-4000-8000-000000009804")


class _CareerRecordSource:
    def __init__(self) -> None:
        self._records = {
            ACHIEVEMENT_ID: self._record(
                ACHIEVEMENT_ID,
                EvidenceType.ACHIEVEMENT,
                "Evidence-backed achievement",
            ),
            NOTE_ID: self._record(
                NOTE_ID,
                EvidenceType.NOTE,
                "Private supporting note",
            ),
        }

    async def readiness_snapshot(
        self,
        owner_user_id: UUID,
        *,
        evidence_limit: int,
    ) -> SimpleNamespace:
        assert owner_user_id == OWNER_ID
        assert evidence_limit == 2_000
        evidence = tuple(
            SimpleNamespace(
                id=evidence_id,
                evidence_revision_id=record.revision.id,
                revision_number=record.revision.revision,
                statement_sha256=hashlib.sha256(
                    record.revision.statement.encode("utf-8")
                ).hexdigest(),
            )
            for evidence_id, record in self._records.items()
        )
        return SimpleNamespace(
            evidence=evidence,
            skills=(
                SimpleNamespace(
                    id=SKILL_ID,
                    name="Delivery",
                    category="leadership",
                    proficiency="advanced",
                ),
            ),
        )

    async def get_evidence_batch_with_eligibility(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[tuple[SimpleNamespace, SimpleNamespace], ...]:
        assert owner_user_id == OWNER_ID
        return tuple(
            (self._records[evidence_id], SimpleNamespace(eligible=True))
            for evidence_id in evidence_ids
        )

    @staticmethod
    def _record(
        evidence_id: UUID,
        evidence_type: EvidenceType,
        statement: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            item=SimpleNamespace(id=evidence_id),
            revision=SimpleNamespace(
                id=UUID(int=evidence_id.int + 100),
                revision=1,
                title=statement,
                statement=statement,
                evidence_type=evidence_type,
                strength=EvidenceStrength.CONFIRMED,
                created_at=datetime(2026, 7, 24, tzinfo=UTC),
            ),
            skill_ids=(SKILL_ID,),
        )


@pytest.mark.asyncio
async def test_achievement_history_excludes_other_eligible_evidence_types() -> None:
    provider = CareerRecordGrowthSourceProvider(_CareerRecordSource())  # type: ignore[arg-type]

    result = await provider.insights(OWNER_ID)

    assert [item.evidence_id for item in result.achievements] == [ACHIEVEMENT_ID]
    assert result.achievements[0].evidence_type == "achievement"
    assert {item.evidence_id for item in result.eligible_evidence} == {
        ACHIEVEMENT_ID,
        NOTE_ID,
    }
    assert result.skills[0].evidence_ids == (NOTE_ID, ACHIEVEMENT_ID)
