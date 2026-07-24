"""Application-boundary source providers for Phase 7 resume creation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from careeros.modules.career_record.application import CareerRecordService
from careeros.modules.change_studio.application import ChangeStudioService, ValidationStatus
from careeros.modules.resume_builder.application import (
    ResumeSourceBullet,
    ResumeSourceSnapshot,
)
from careeros.modules.resume_builder.application.ports import ResumeSourceProvider
from careeros.modules.resume_builder.domain import (
    ResumeBuilderValidationError,
    ResumeEvidenceLinkBasis,
    ResumeEvidenceReference,
)


@dataclass(frozen=True, slots=True)
class _PinnedChangeClaimSource:
    text: str
    evidence_id: UUID
    evidence_revision_id: UUID
    evidence_revision_number: int
    evidence_statement_sha256: str


class CareerRecordResumeSourceProvider(ResumeSourceProvider):
    """Build a grounded resume source snapshot from existing application services."""

    def __init__(
        self,
        career_record: CareerRecordService,
        *,
        change_studio: ChangeStudioService | None = None,
    ) -> None:
        self._career_record = career_record
        self._change_studio = change_studio

    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        change_set_id: UUID | None = None,
        change_set_version_id: UUID | None = None,
    ) -> ResumeSourceSnapshot:
        try:
            profile = await self._career_record.get_profile(owner_user_id)
            readiness = await self._career_record.readiness_snapshot(owner_user_id)
        except Exception as exc:
            raise ResumeBuilderValidationError(
                "career record must exist before building a resume"
            ) from exc

        current_references = {
            item.id: ResumeEvidenceReference(
                evidence_id=item.id,
                evidence_revision_id=item.evidence_revision_id,
                revision_number=item.revision_number,
                statement_sha256=item.statement_sha256,
                claim_sha256=hashlib.sha256(
                    " ".join(item.statement.strip().split()).encode("utf-8")
                ).hexdigest(),
                link_basis=ResumeEvidenceLinkBasis.EVIDENCE_STATEMENT,
            )
            for item in readiness.evidence
        }
        change_bullets = (
            await self._change_studio_bullets(
                owner_user_id,
                change_set_id,
                change_set_version_id,
            )
            if change_set_id is not None
            else ()
        )
        change_revisions: dict[UUID, UUID] = {}
        for bullet in change_bullets:
            for reference in bullet.evidence_references:
                existing = change_revisions.setdefault(
                    reference.evidence_id,
                    reference.evidence_revision_id,
                )
                if existing != reference.evidence_revision_id:
                    raise ResumeBuilderValidationError(
                        "change studio version cites multiple revisions of one evidence item"
                    )
        bullets: list[ResumeSourceBullet] = [
            ResumeSourceBullet(
                text=item.statement,
                evidence_ids=(item.id,),
                source="career_record",
                evidence_references=(current_references[item.id],),
            )
            for item in readiness.evidence
            if change_revisions.get(item.id, item.evidence_revision_id) == item.evidence_revision_id
        ]
        for skill in readiness.skills:
            linked = tuple(
                evidence.id
                for evidence in readiness.evidence
                if skill.id in evidence.skill_ids
                and change_revisions.get(
                    evidence.id,
                    evidence.evidence_revision_id,
                )
                == evidence.evidence_revision_id
            )
            if linked:
                bullets.append(
                    ResumeSourceBullet(
                        text=skill.name,
                        evidence_ids=linked[:3],
                        source="career_record",
                        evidence_references=tuple(
                            ResumeEvidenceReference(
                                evidence_id=evidence.id,
                                evidence_revision_id=evidence.evidence_revision_id,
                                revision_number=evidence.revision_number,
                                statement_sha256=evidence.statement_sha256,
                                claim_sha256=hashlib.sha256(
                                    " ".join(skill.name.strip().split()).encode("utf-8")
                                ).hexdigest(),
                                link_basis=ResumeEvidenceLinkBasis.EVIDENCE_SKILL,
                                source_skill_id=skill.id,
                            )
                            for evidence in readiness.evidence
                            if evidence.id in linked[:3]
                        ),
                        section_kind="skills",
                    )
                )
        bullets.extend(change_bullets)
        evidence_ids = tuple(
            dict.fromkeys(
                reference.evidence_id
                for bullet in bullets
                for reference in bullet.evidence_references
            )
        )
        if len(evidence_ids) > 200:
            raise ResumeBuilderValidationError(
                "resume source exceeds the 200-evidence provenance limit"
            )

        return ResumeSourceSnapshot(
            headline=profile.profile.professional_headline,
            summary=None,
            skills=(),
            bullets=tuple(dict.fromkeys(bullets)),
            source_evidence_ids=evidence_ids,
        )

    async def _change_studio_bullets(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        change_set_version_id: UUID | None,
    ) -> tuple[ResumeSourceBullet, ...]:
        if self._change_studio is None:
            raise ResumeBuilderValidationError("change studio source is unavailable")
        try:
            record = await self._change_studio.get_change_set(
                owner_user_id,
                change_set_id,
            )
        except Exception as exc:
            raise ResumeBuilderValidationError("change studio source is unavailable") from exc
        version = next(
            (
                candidate
                for candidate in record.versions
                if candidate.id == change_set_version_id
                or (
                    change_set_version_id is None
                    and candidate.id == record.change_set.current_version_id
                )
            ),
            None,
        )
        if version is None:
            raise ResumeBuilderValidationError("change studio version is unavailable")
        operations = {operation.id: operation for operation in record.operations}
        claims_by_operation = {
            operation_id: tuple(
                sorted(
                    (claim for claim in record.claims if claim.operation_id == operation_id),
                    key=lambda claim: (claim.sort_order, str(claim.id)),
                )
            )
            for operation_id in version.operation_ids
        }
        selected_claims: list[_PinnedChangeClaimSource] = []
        for operation_id in version.operation_ids:
            operation = operations.get(operation_id)
            claims = claims_by_operation[operation_id]
            if operation is None or not claims:
                raise ResumeBuilderValidationError(
                    "change studio version contains a legacy or ambiguous operation"
                )
            normalized_output = " ".join(operation.after_text.strip().split()).casefold()
            for claim in claims:
                evidence_revision_id = claim.evidence_revision_id
                evidence_revision_number = claim.evidence_revision_number
                evidence_statement_sha256 = claim.evidence_statement_sha256
                if (
                    not isinstance(evidence_revision_id, UUID)
                    or not isinstance(evidence_revision_number, int)
                    or not isinstance(evidence_statement_sha256, str)
                    or len(evidence_statement_sha256) != 64
                    or claim.validation_status is not ValidationStatus.PASSED
                    or " ".join(claim.text.strip().split()).casefold() not in normalized_output
                ):
                    raise ResumeBuilderValidationError(
                        "change studio version contains a legacy unpinned or ungrounded claim"
                    )
                selected_claims.append(
                    _PinnedChangeClaimSource(
                        text=claim.text,
                        evidence_id=claim.evidence_id,
                        evidence_revision_id=evidence_revision_id,
                        evidence_revision_number=evidence_revision_number,
                        evidence_statement_sha256=evidence_statement_sha256,
                    )
                )
        if not selected_claims:
            return ()
        evidence_ids = tuple(dict.fromkeys(selected.evidence_id for selected in selected_claims))
        try:
            records = await self._career_record.get_evidence_batch_with_eligibility(
                owner_user_id,
                evidence_ids,
            )
        except Exception as exc:
            raise ResumeBuilderValidationError(
                "change studio evidence history is unavailable"
            ) from exc
        records_by_id = {record.item.id: (record, decision) for record, decision in records}
        for selected in selected_claims:
            pair = records_by_id.get(selected.evidence_id)
            revision = (
                next(
                    (
                        candidate
                        for candidate in pair[0].revisions
                        if candidate.id == selected.evidence_revision_id
                    ),
                    None,
                )
                if pair is not None and pair[1].eligible
                else None
            )
            if (
                revision is None
                or revision.revision != selected.evidence_revision_number
                or hashlib.sha256(revision.statement.encode("utf-8")).hexdigest()
                != selected.evidence_statement_sha256
            ):
                raise ResumeBuilderValidationError(
                    "change studio claim evidence revision is unavailable"
                )
        return tuple(
            ResumeSourceBullet(
                text=selected.text,
                evidence_ids=(selected.evidence_id,),
                source="change_studio",
                evidence_references=(
                    ResumeEvidenceReference(
                        evidence_id=selected.evidence_id,
                        evidence_revision_id=selected.evidence_revision_id,
                        revision_number=selected.evidence_revision_number,
                        statement_sha256=selected.evidence_statement_sha256,
                        claim_sha256=hashlib.sha256(
                            " ".join(selected.text.strip().split()).encode("utf-8")
                        ).hexdigest(),
                        link_basis=ResumeEvidenceLinkBasis.CHANGE_STUDIO_CLAIM,
                    ),
                ),
            )
            for selected in selected_claims
        )
