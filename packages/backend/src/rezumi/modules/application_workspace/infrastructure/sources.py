"""Application-service adapters for immutable Phase 8 source snapshots."""

from __future__ import annotations

import hashlib
from uuid import UUID

from rezumi.modules.application_workspace.application import (
    ApplicationInterviewEvidenceReference,
    ApplicationJobSnapshot,
    ApplicationResumeSnapshot,
    ApplicationSourceClaim,
    ApplicationSourceEvidenceReference,
)
from rezumi.modules.application_workspace.domain import (
    ApplicationEvidencePin,
    ApplicationRequirementSnapshot,
    ApplicationRequirementSupport,
    ApplicationWorkspaceConflict,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceUnavailable,
)
from rezumi.modules.career_record.application import (
    CareerRecordError,
    CareerRecordNotFound,
    CareerRecordService,
    CareerRecordUnavailable,
)
from rezumi.modules.job_match.application import JobMatchNotFound, JobMatchService
from rezumi.modules.resume_builder.application import (
    ResumeBuilderNotFound,
    ResumeBuilderService,
)


class JobMatchApplicationSnapshotProvider:
    """Copy a complete owner-scoped job revision through the Job Match service."""

    def __init__(self, service: JobMatchService) -> None:
        self._service = service

    async def snapshot(self, owner_user_id: UUID, job_id: UUID) -> ApplicationJobSnapshot:
        try:
            record = await self._service.get_job(owner_user_id, job_id)
            latest = await self._service.get_latest_analysis_for_job(
                owner_user_id,
                job_id,
            )
        except JobMatchNotFound as exc:
            raise ApplicationWorkspaceNotFound from exc
        latest_analysis_id = None
        requirement_support: tuple[ApplicationRequirementSupport, ...] = ()
        if latest is not None:
            job_input = latest.analysis.input_snapshot.get("job")
            if (
                isinstance(job_input, dict)
                and job_input.get("version") == record.job.version
                and job_input.get("sourceSha256") == record.job.source_sha256.hex()
            ):
                latest_analysis_id = latest.analysis.id
                requirement_ids_by_match = {
                    match.id: match.requirement_id for match in latest.requirement_matches
                }
                valid_requirement_ids = {requirement.id for requirement in record.requirements}
                requirement_support = tuple(
                    ApplicationRequirementSupport(
                        analysis_id=latest.analysis.id,
                        requirement_id=requirement_id,
                        evidence_id=link.evidence_id,
                    )
                    for link in latest.evidence_links
                    if (requirement_id := requirement_ids_by_match.get(link.requirement_match_id))
                    in valid_requirement_ids
                )
        return ApplicationJobSnapshot(
            job_id=record.job.id,
            version=record.job.version,
            title=record.job.title,
            company=record.job.company,
            location=record.job.location,
            application_deadline=record.job.application_deadline,
            latest_analysis_id=latest_analysis_id,
            source_sha256=record.job.source_sha256.hex(),
            source=record.job.source_kind.value,
            industry=None,
            requirements=tuple(
                ApplicationRequirementSnapshot(
                    id=requirement.id,
                    requirement_type=requirement.requirement_type.value,
                    importance=requirement.importance.value,
                    text=requirement.text,
                    source_start=requirement.source_start,
                    source_end=requirement.source_end,
                )
                for requirement in record.requirements
            ),
            requirement_support=requirement_support,
        )


class ResumeBuilderVersionSnapshotProvider:
    """Read an immutable resume version through the Resume Builder service."""

    def __init__(self, service: ResumeBuilderService) -> None:
        self._service = service

    async def snapshot(self, owner_user_id: UUID, version_id: UUID) -> ApplicationResumeSnapshot:
        try:
            version = await self._service.get_version(owner_user_id, version_id)
        except ResumeBuilderNotFound as exc:
            raise ApplicationWorkspaceNotFound from exc
        claims: list[ApplicationSourceClaim] = []
        references: list[ApplicationSourceEvidenceReference] = []
        claim_ids: set[UUID] = set()
        for section in version.sections:
            for item in section.items:
                if item.id in claim_ids:
                    raise ApplicationWorkspaceConflict(
                        "resume version contains duplicate claim identifiers"
                    )
                claim_ids.add(item.id)
                item_references = tuple(
                    ApplicationSourceEvidenceReference(
                        evidence_id=reference.evidence_id,
                        evidence_revision_id=reference.evidence_revision_id,
                        revision_number=reference.revision_number,
                        statement_sha256=reference.statement_sha256,
                        claim_sha256=reference.claim_sha256,
                        link_basis=reference.link_basis.value,
                        source_skill_id=reference.source_skill_id,
                    )
                    for reference in item.evidence_references
                )
                if (
                    not item_references
                    or tuple(reference.evidence_id for reference in item_references)
                    != item.evidence_ids
                    or any(
                        reference.claim_sha256
                        != hashlib.sha256(
                            " ".join(item.text.strip().split()).encode("utf-8")
                        ).hexdigest()
                        for reference in item_references
                    )
                ):
                    raise ApplicationWorkspaceConflict(
                        "resume version provenance ledger is incomplete or invalid"
                    )
                references.extend(item_references)
                claims.append(
                    ApplicationSourceClaim(
                        id=item.id,
                        text=item.text,
                        evidence_references=item_references,
                    )
                )
        evidence_ids = tuple(dict.fromkeys(reference.evidence_id for reference in references))
        if evidence_ids != version.source_evidence_ids:
            raise ApplicationWorkspaceConflict(
                "resume version evidence ledger does not match its claims"
            )
        return ApplicationResumeSnapshot(
            resume_id=version.resume_id,
            version_id=version.id,
            version_number=version.version_number,
            title=version.title,
            target_role=version.target_role,
            evidence_references=tuple(references),
            claims=tuple(claims),
            plain_text=version.plain_text,
        )


class CareerRecordApplicationEvidenceSnapshotProvider:
    """Pin exact, currently eligible evidence revisions through Career Record."""

    def __init__(self, service: CareerRecordService) -> None:
        self._service = service

    async def snapshot(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationSourceEvidenceReference, ...],
    ) -> tuple[ApplicationEvidencePin, ...]:
        references_by_id: dict[UUID, ApplicationSourceEvidenceReference] = {}
        for reference in references:
            existing = references_by_id.get(reference.evidence_id)
            if existing is not None and (
                existing.evidence_revision_id != reference.evidence_revision_id
                or existing.revision_number != reference.revision_number
                or existing.statement_sha256 != reference.statement_sha256
            ):
                raise ApplicationWorkspaceConflict(
                    "resume evidence references disagree on an exact revision"
                )
            references_by_id.setdefault(reference.evidence_id, reference)
        unique_ids = tuple(references_by_id)
        if not unique_ids:
            return ()
        try:
            snapshots = await self._service.get_evidence_batch_with_eligibility(
                owner_user_id,
                unique_ids,
            )
        except CareerRecordNotFound as exc:
            raise ApplicationWorkspaceNotFound from exc
        pins: list[ApplicationEvidencePin] = []
        for record, decision in snapshots:
            if not decision.eligible:
                raise ApplicationWorkspaceConflict(
                    "resume version references evidence that is no longer eligible"
                )
            reference = references_by_id[record.item.id]
            revision = next(
                (
                    candidate
                    for candidate in record.revisions
                    if candidate.id == reference.evidence_revision_id
                ),
                None,
            )
            if (
                revision is None
                or revision.evidence_id != reference.evidence_id
                or revision.revision != reference.revision_number
                or hashlib.sha256(revision.statement.encode("utf-8")).hexdigest()
                != reference.statement_sha256
            ):
                raise ApplicationWorkspaceConflict(
                    "resume evidence historical revision is unavailable or changed"
                )
            pins.append(
                ApplicationEvidencePin(
                    evidence_id=record.item.id,
                    evidence_revision_id=revision.id,
                    revision_number=revision.revision,
                    statement=revision.statement,
                    statement_sha256=hashlib.sha256(revision.statement.encode("utf-8")).hexdigest(),
                    strength=revision.strength.value,
                    has_numeric_claim=revision.has_numeric_claim,
                )
            )
        if set(unique_ids) != {pin.evidence_id for pin in pins}:
            raise ApplicationWorkspaceConflict("resume evidence snapshot is incomplete")
        return tuple(pins)

    async def validate_current(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationInterviewEvidenceReference, ...],
    ) -> None:
        """Apply live canonical eligibility and require the exact current revision."""

        references_by_id: dict[UUID, ApplicationInterviewEvidenceReference] = {}
        for reference in references:
            existing = references_by_id.get(reference.evidence_id)
            if existing is not None and existing != reference:
                raise ApplicationWorkspaceConflict(
                    "interview evidence references disagree on an exact revision"
                )
            references_by_id.setdefault(reference.evidence_id, reference)
        if not references_by_id:
            return

        try:
            snapshots = await self._service.get_evidence_batch_with_eligibility(
                owner_user_id,
                tuple(references_by_id),
            )
        except CareerRecordNotFound as exc:
            raise ApplicationWorkspaceConflict("interview evidence is no longer available") from exc
        except CareerRecordUnavailable as exc:
            raise ApplicationWorkspaceUnavailable from exc
        except CareerRecordError as exc:
            raise ApplicationWorkspaceConflict(
                "interview evidence eligibility could not be verified"
            ) from exc

        records_by_id = {record.item.id: (record, decision) for record, decision in snapshots}
        if set(records_by_id) != set(references_by_id):
            raise ApplicationWorkspaceConflict(
                "interview evidence eligibility snapshot is incomplete"
            )

        for evidence_id, reference in references_by_id.items():
            record, decision = records_by_id[evidence_id]
            revision = record.revision
            statement_sha256 = hashlib.sha256(revision.statement.encode("utf-8")).hexdigest()
            if not decision.eligible:
                raise ApplicationWorkspaceConflict(
                    "interview evidence is no longer eligible for generation"
                )
            if (
                revision.id != reference.evidence_revision_id
                or revision.evidence_id != reference.evidence_id
                or record.item.current_revision != reference.revision_number
                or revision.revision != reference.revision_number
                or statement_sha256 != reference.statement_sha256
                or revision.strength.value != reference.strength
                or revision.has_numeric_claim is not reference.has_numeric_claim
            ):
                raise ApplicationWorkspaceConflict(
                    "interview evidence pin does not match the exact current revision"
                )
