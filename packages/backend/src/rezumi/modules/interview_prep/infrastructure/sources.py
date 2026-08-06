"""Purpose-minimized Phase 8 application-context adapter for Interview Prep."""

from __future__ import annotations

import hashlib
import re
from typing import Never, Protocol
from uuid import UUID

from rezumi.modules.application_workspace.application import (
    ApplicationInterviewContext,
    ApplicationInterviewEvidenceReference,
)
from rezumi.modules.interview_prep.application import (
    InterviewSourceSnapshot,
    SourceClaim,
    SourceRequirement,
)
from rezumi.modules.interview_prep.domain import (
    EvidenceRevisionPin,
    InterviewPrepConflict,
    InterviewPrepNotFound,
    InterviewPrepUnavailable,
)

_STRONG_TOKEN = re.compile(r"(?<!\w)(?:[$]?[-+]?\d[\d,]*(?:\.\d+)?%?|(?:19|20)\d{2})(?!\w)")


class _ApplicationWorkspaceInterviewService(Protocol):
    async def get_interview_context(
        self, owner_user_id: UUID, application_id: UUID
    ) -> ApplicationInterviewContext: ...

    async def validate_interview_evidence(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        references: tuple[ApplicationInterviewEvidenceReference, ...],
    ) -> None: ...


class ApplicationWorkspaceInterviewContextProvider:
    """Consume the explicit Phase 8 service view, never another module's tables."""

    def __init__(self, service: _ApplicationWorkspaceInterviewService) -> None:
        self._service = service

    async def snapshot(self, owner_user_id: UUID, application_id: UUID) -> InterviewSourceSnapshot:
        try:
            source = await self._service.get_interview_context(owner_user_id, application_id)
        except Exception as exc:
            _raise_interview_source_error(exc)
        evidence_by_revision = {
            (pin.evidence_id, pin.evidence_revision_id): pin for pin in source.evidence_pins
        }
        requirements = tuple(
            SourceRequirement(
                id=requirement.id,
                text=requirement.text,
                importance=requirement.importance,
            )
            for requirement in source.requirements
        )
        mandatory_ids = {
            requirement.id
            for requirement in source.requirements
            if requirement.importance == "mandatory"
        }
        claims: list[SourceClaim] = []
        for claim in source.claims:
            pins: list[EvidenceRevisionPin] = []
            for link in claim.evidence_links:
                pin = evidence_by_revision.get((link.evidence_id, link.evidence_revision_id))
                if pin is None:
                    raise InterviewPrepConflict(
                        "application interview context has an incomplete evidence ledger"
                    )
                pins.append(
                    EvidenceRevisionPin(
                        evidence_id=pin.evidence_id,
                        evidence_revision_id=pin.evidence_revision_id,
                        revision_number=pin.revision_number,
                        statement=pin.statement,
                        statement_sha256=pin.statement_sha256,
                        strength=pin.strength,
                        has_numeric_claim=pin.has_numeric_claim,
                    )
                )
            normalized_claim = claim.text.strip()
            claims.append(
                SourceClaim(
                    id=claim.id,
                    text=normalized_claim,
                    text_sha256=hashlib.sha256(normalized_claim.encode("utf-8")).hexdigest(),
                    strong=bool(_STRONG_TOKEN.search(normalized_claim))
                    or bool(set(claim.requirement_ids) & mandatory_ids),
                    requirement_ids=claim.requirement_ids,
                    evidence_pins=tuple(pins),
                )
            )
        return InterviewSourceSnapshot(
            application_id=source.application_id,
            job_id=source.job_id,
            job_version=source.job_version,
            job_title=source.job_title,
            company=source.company,
            resume_version_id=source.resume_version_id,
            resume_version_number=source.resume_version_number,
            claims=tuple(claims),
            requirements=requirements,
        )

    async def validate_current_evidence(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        evidence_pins: tuple[EvidenceRevisionPin, ...],
    ) -> None:
        references = tuple(
            ApplicationInterviewEvidenceReference(
                evidence_id=pin.evidence_id,
                evidence_revision_id=pin.evidence_revision_id,
                revision_number=pin.revision_number,
                statement_sha256=pin.statement_sha256,
                strength=pin.strength,
                has_numeric_claim=pin.has_numeric_claim,
            )
            for pin in evidence_pins
        )
        try:
            await self._service.validate_interview_evidence(
                owner_user_id,
                application_id,
                references,
            )
        except Exception as exc:
            _raise_interview_source_error(exc)


def _raise_interview_source_error(exc: Exception) -> Never:
    code = getattr(exc, "code", None)
    if code == "application_workspace_not_found":
        raise InterviewPrepNotFound from exc
    if code == "application_workspace_unavailable":
        raise InterviewPrepUnavailable from exc
    if code in {
        "application_workspace_conflict",
        "application_workspace_version_conflict",
        "application_workspace_idempotency_conflict",
        "application_workspace_validation_failed",
    }:
        raise InterviewPrepConflict(
            "application evidence is no longer eligible for grounded interview output"
        ) from exc
    raise exc
