"""Purpose-minimized Career Record adapter for Career Growth."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from uuid import UUID

from rezumi.modules.career_growth.application.models import (
    CareerGrowthInsightSource,
    GrowthAchievementSnapshot,
    GrowthSkillSnapshot,
)
from rezumi.modules.career_growth.domain import (
    CareerGrowthConflict,
    CareerGrowthNotFound,
    CareerGrowthSourceSnapshot,
    GrowthEvidenceSnapshot,
)
from rezumi.modules.career_record.application import (
    CareerRecordNotFound,
    CareerRecordService,
    EvidenceRecord,
)


class CareerRecordGrowthSourceProvider:
    """Read exact eligible revisions through the Career Record application service."""

    def __init__(
        self,
        service: CareerRecordService,
        *,
        evidence_limit: int = 2_000,
        evidence_detail_limit: int = 25,
    ) -> None:
        if not 1 <= evidence_limit <= 2_000:
            raise ValueError("career growth evidence limit is invalid")
        if not 1 <= evidence_detail_limit <= 100:
            raise ValueError("career growth evidence detail limit is invalid")
        self._service = service
        self._evidence_limit = evidence_limit
        self._evidence_detail_limit = evidence_detail_limit

    async def snapshot(self, owner_user_id: UUID) -> CareerGrowthSourceSnapshot:
        source = await self._service.readiness_snapshot(
            owner_user_id, evidence_limit=self._evidence_limit
        )
        evidence_ids = tuple(item.id for item in source.evidence)
        records_by_id: dict[UUID, tuple[EvidenceRecord, bool]] = {}
        try:
            for start in range(0, len(evidence_ids), 200):
                batch = await self._service.get_evidence_batch_with_eligibility(
                    owner_user_id, evidence_ids[start : start + 200]
                )
                records_by_id.update(
                    (record.item.id, (record, decision.eligible)) for record, decision in batch
                )
        except CareerRecordNotFound as exc:
            raise CareerGrowthConflict(
                "Career Record evidence changed while the growth snapshot was built"
            ) from exc
        snapshots: list[GrowthEvidenceSnapshot] = []
        for item in source.evidence:
            pair = records_by_id.get(item.id)
            if pair is None:
                raise CareerGrowthConflict("Career Record evidence snapshot is incomplete")
            record, eligible = pair
            revision = record.revision
            statement_sha256 = hashlib.sha256(revision.statement.encode("utf-8")).hexdigest()
            if (
                not eligible
                or revision.id != item.evidence_revision_id
                or revision.revision != item.revision_number
                or statement_sha256 != item.statement_sha256
            ):
                raise CareerGrowthConflict(
                    "Career Record evidence changed while the growth snapshot was built"
                )
            snapshots.append(
                GrowthEvidenceSnapshot(
                    evidence_id=item.id,
                    evidence_revision_id=revision.id,
                    revision_number=revision.revision,
                    statement_sha256=statement_sha256,
                    revised_at=revision.created_at,
                    skill_ids=item.skill_ids,
                )
            )
        return CareerGrowthSourceSnapshot(
            evidence=tuple(snapshots),
            skill_ids=tuple(skill.id for skill in source.skills),
        )

    async def resolve_evidence(
        self, owner_user_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        unique_ids = tuple(dict.fromkeys(evidence_ids))
        if not unique_ids or len(unique_ids) != len(evidence_ids) or len(unique_ids) > 100:
            raise CareerGrowthConflict(
                "growth evidence resolution requires one to 100 distinct evidence IDs"
            )
        try:
            records = await self._service.get_evidence_batch_with_eligibility(
                owner_user_id, unique_ids
            )
        except CareerRecordNotFound as exc:
            raise CareerGrowthNotFound from exc
        snapshots: list[GrowthEvidenceSnapshot] = []
        for record, decision in records:
            if not decision.eligible:
                raise CareerGrowthConflict(
                    "only currently eligible Career Record evidence may be linked"
                )
            revision = record.revision
            snapshots.append(
                GrowthEvidenceSnapshot(
                    evidence_id=record.item.id,
                    evidence_revision_id=revision.id,
                    revision_number=revision.revision,
                    statement_sha256=hashlib.sha256(revision.statement.encode("utf-8")).hexdigest(),
                    revised_at=revision.created_at,
                    skill_ids=record.skill_ids,
                )
            )
        if tuple(item.evidence_id for item in snapshots) != unique_ids:
            raise CareerGrowthConflict("Career Record evidence resolution is incomplete")
        return tuple(snapshots)

    async def current_evidence(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        """Resolve live status in bounded batches while tolerating revoked/deleted IDs."""

        unique_ids = tuple(dict.fromkeys(evidence_ids))
        if len(unique_ids) != len(evidence_ids) or len(unique_ids) > self._evidence_limit:
            raise CareerGrowthConflict("growth evidence status request exceeds supported bounds")
        snapshots: list[GrowthEvidenceSnapshot] = []
        for start in range(0, len(unique_ids), 200):
            snapshots.extend(
                await self._current_batch(owner_user_id, unique_ids[start : start + 200])
            )
        return tuple(snapshots)

    async def _current_batch(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        if not evidence_ids:
            return ()
        try:
            records = await self._service.get_evidence_batch_with_eligibility(
                owner_user_id,
                evidence_ids,
            )
        except CareerRecordNotFound:
            if len(evidence_ids) == 1:
                return ()
            middle = len(evidence_ids) // 2
            left = await self._current_batch(owner_user_id, evidence_ids[:middle])
            right = await self._current_batch(owner_user_id, evidence_ids[middle:])
            return (*left, *right)
        return tuple(
            GrowthEvidenceSnapshot(
                evidence_id=record.item.id,
                evidence_revision_id=record.revision.id,
                revision_number=record.revision.revision,
                statement_sha256=hashlib.sha256(
                    record.revision.statement.encode("utf-8")
                ).hexdigest(),
                revised_at=record.revision.created_at,
                skill_ids=record.skill_ids,
            )
            for record, decision in records
            if decision.eligible
        )

    async def insights(self, owner_user_id: UUID) -> CareerGrowthInsightSource:
        """Return eligible display data without persisting a second source of truth."""

        source = await self._service.readiness_snapshot(
            owner_user_id,
            evidence_limit=self._evidence_limit,
        )
        evidence_ids = tuple(item.id for item in source.evidence)
        records_by_id: dict[UUID, tuple[EvidenceRecord, bool]] = {}
        try:
            for start in range(0, len(evidence_ids), 200):
                batch = await self._service.get_evidence_batch_with_eligibility(
                    owner_user_id,
                    evidence_ids[start : start + 200],
                )
                records_by_id.update(
                    (record.item.id, (record, decision.eligible)) for record, decision in batch
                )
        except CareerRecordNotFound as exc:
            raise CareerGrowthConflict(
                "Career Record evidence changed while growth insights were built"
            ) from exc

        achievements: list[GrowthAchievementSnapshot] = []
        eligible_evidence: list[GrowthEvidenceSnapshot] = []
        evidence_by_skill: defaultdict[UUID, list[tuple[UUID, datetime]]] = defaultdict(list)
        for item in source.evidence:
            pair = records_by_id.get(item.id)
            if pair is None:
                raise CareerGrowthConflict("Career Record insight snapshot is incomplete")
            record, eligible = pair
            revision = record.revision
            statement_sha256 = hashlib.sha256(revision.statement.encode("utf-8")).hexdigest()
            if (
                not eligible
                or revision.id != item.evidence_revision_id
                or revision.revision != item.revision_number
                or statement_sha256 != item.statement_sha256
            ):
                raise CareerGrowthConflict(
                    "Career Record evidence changed while growth insights were built"
                )
            eligible_evidence.append(
                GrowthEvidenceSnapshot(
                    evidence_id=item.id,
                    evidence_revision_id=revision.id,
                    revision_number=revision.revision,
                    statement_sha256=statement_sha256,
                    revised_at=revision.created_at,
                    skill_ids=record.skill_ids,
                )
            )
            for skill_id in record.skill_ids:
                evidence_by_skill[skill_id].append((item.id, revision.created_at))
            if revision.evidence_type.value == "achievement":
                achievements.append(
                    GrowthAchievementSnapshot(
                        evidence_id=item.id,
                        evidence_revision_id=revision.id,
                        revision_number=revision.revision,
                        title=revision.title,
                        statement=revision.statement,
                        evidence_type=revision.evidence_type.value,
                        strength=revision.strength.value,
                        revised_at=revision.created_at,
                        skill_ids=record.skill_ids,
                    )
                )

        skills: list[GrowthSkillSnapshot] = []
        for skill in source.skills:
            ordered_evidence = sorted(
                evidence_by_skill[skill.id],
                key=lambda value: (value[1], str(value[0])),
                reverse=True,
            )
            skills.append(
                GrowthSkillSnapshot(
                    skill_id=skill.id,
                    name=skill.name,
                    category=skill.category,
                    proficiency=skill.proficiency,
                    evidence_count=len(ordered_evidence),
                    evidence_ids=tuple(
                        evidence_id
                        for evidence_id, _revised_at in ordered_evidence[
                            : self._evidence_detail_limit
                        ]
                    ),
                    latest_evidence_at=(ordered_evidence[0][1] if ordered_evidence else None),
                )
            )
        return CareerGrowthInsightSource(
            achievements=tuple(
                sorted(
                    achievements,
                    key=lambda item: (item.revised_at, str(item.evidence_id)),
                    reverse=True,
                )
            ),
            skills=tuple(skills),
            eligible_evidence=tuple(eligible_evidence),
        )
