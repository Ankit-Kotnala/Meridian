"""Domain-policy tests for Phase 8 application tracking and evidence pins."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from rezumi.modules.application_workspace.domain import (
    ApplicationClaimEvidenceLink,
    ApplicationDocumentClaim,
    ApplicationEvidencePin,
    ApplicationRecord,
    ApplicationRequirementSnapshot,
    ApplicationStage,
    ApplicationWorkspaceValidationError,
    OutcomeStatus,
    ReferralStatus,
    validate_stage_transition,
)

_OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
_APPLICATION_ID = UUID("00000000-0000-0000-0000-000000000002")
_JOB_ID = UUID("00000000-0000-0000-0000-000000000003")
_RESUME_ID = UUID("00000000-0000-0000-0000-000000000004")
_RESUME_VERSION_ID = UUID("00000000-0000-0000-0000-000000000005")
_EVIDENCE_ID = UUID("00000000-0000-0000-0000-000000000006")
_EVIDENCE_REVISION_ID = UUID("00000000-0000-0000-0000-000000000007")
_REQUIREMENT_ID = UUID("00000000-0000-0000-0000-000000000008")
_CLAIM_ID = UUID("00000000-0000-0000-0000-000000000009")
_NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)


def _record() -> ApplicationRecord:
    statement = "Led cross-functional product delivery."
    requirement = ApplicationRequirementSnapshot(
        id=_REQUIREMENT_ID,
        requirement_type="responsibility",
        importance="mandatory",
        text="Lead cross-functional product delivery.",
        source_start=10,
        source_end=49,
    )
    pin = ApplicationEvidencePin(
        evidence_id=_EVIDENCE_ID,
        evidence_revision_id=_EVIDENCE_REVISION_ID,
        revision_number=3,
        statement=statement,
        statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        strength="confirmed",
        has_numeric_claim=False,
    )
    claim = ApplicationDocumentClaim(
        id=_CLAIM_ID,
        text=statement,
        evidence_links=(
            ApplicationClaimEvidenceLink(
                evidence_id=pin.evidence_id,
                evidence_revision_id=pin.evidence_revision_id,
            ),
        ),
        requirement_ids=(requirement.id,),
    )
    return ApplicationRecord(
        id=_APPLICATION_ID,
        owner_user_id=_OWNER_ID,
        job_id=_JOB_ID,
        job_version=4,
        job_title="Principal Product Engineer",
        company="Example Co",
        location="Remote",
        job_analysis_id=None,
        job_source_sha256="a" * 64,
        job_requirements=(requirement,),
        requirement_support=(),
        resume_id=_RESUME_ID,
        resume_version_id=_RESUME_VERSION_ID,
        resume_version_number=7,
        resume_title="Product resume",
        resume_evidence_ids=(pin.evidence_id,),
        evidence_pins=(pin,),
        resume_claims=(claim,),
        source="referral",
        industry="software",
        stage=ApplicationStage.PREPARING,
        application_deadline=None,
        follow_up_at=None,
        contacts=(),
        referral_status=ReferralStatus.REQUESTED,
        outcome_status=OutcomeStatus.NONE,
        rejection_reason=None,
        offer_summary=None,
        version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (ApplicationStage.SAVED, ApplicationStage.APPLIED),
        (ApplicationStage.PREPARING, ApplicationStage.READY_TO_APPLY),
        (ApplicationStage.APPLIED, ApplicationStage.INTERVIEW),
        (ApplicationStage.INTERVIEW, ApplicationStage.OFFER),
        (ApplicationStage.OFFER, ApplicationStage.REJECTED),
    ],
)
def test_allowed_stage_transitions(current: ApplicationStage, requested: ApplicationStage) -> None:
    assert validate_stage_transition(current, requested) is None


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (ApplicationStage.SAVED, ApplicationStage.INTERVIEW),
        (ApplicationStage.PREPARING, ApplicationStage.RECRUITER_SCREEN),
        (ApplicationStage.APPLIED, ApplicationStage.SAVED),
        (ApplicationStage.OFFER, ApplicationStage.APPLIED),
    ],
)
def test_invalid_stage_transitions_are_rejected(
    current: ApplicationStage,
    requested: ApplicationStage,
) -> None:
    with pytest.raises(ApplicationWorkspaceValidationError):
        validate_stage_transition(current, requested)


@pytest.mark.parametrize(
    "terminal",
    [ApplicationStage.REJECTED, ApplicationStage.WITHDRAWN],
)
def test_terminal_application_reopen_requires_a_reason(
    terminal: ApplicationStage,
) -> None:
    with pytest.raises(ApplicationWorkspaceValidationError):
        validate_stage_transition(terminal, ApplicationStage.APPLIED)

    assert (
        validate_stage_transition(
            terminal,
            ApplicationStage.APPLIED,
            reopen_reason="  Recruiter re-opened the role.  ",
        )
        == "Recruiter re-opened the role."
    )
    with pytest.raises(ApplicationWorkspaceValidationError):
        validate_stage_transition(
            terminal,
            ApplicationStage.INTERVIEW,
            reopen_reason="Recruiter called.",
        )


def test_record_requires_exact_evidence_revision_and_requirement_pins() -> None:
    record = _record()
    claim = record.resume_claims[0]
    with pytest.raises(
        ApplicationWorkspaceValidationError,
        match="evidence revision is not pinned",
    ):
        replace(
            record,
            resume_claims=(
                replace(
                    claim,
                    evidence_links=(
                        replace(
                            claim.evidence_links[0],
                            evidence_revision_id=UUID("00000000-0000-0000-0000-000000000099"),
                        ),
                    ),
                ),
            ),
        )
    with pytest.raises(
        ApplicationWorkspaceValidationError,
        match="requirement is not pinned",
    ):
        replace(
            record,
            resume_claims=(
                replace(
                    claim,
                    requirement_ids=(UUID("00000000-0000-0000-0000-000000000098"),),
                ),
            ),
        )


def test_stage_and_outcome_are_one_consistent_state() -> None:
    record = _record()
    with pytest.raises(
        ApplicationWorkspaceValidationError,
        match="stage and outcome",
    ):
        replace(record, outcome_status=OutcomeStatus.OFFER)

    offer = replace(
        record,
        stage=ApplicationStage.OFFER,
        outcome_status=OutcomeStatus.OFFER,
        offer_summary="Offer received.",
    )
    assert offer.outcome_status == OutcomeStatus.OFFER
    with pytest.raises(
        ApplicationWorkspaceValidationError,
        match="offer summary requires",
    ):
        replace(record, offer_summary="Unsupported offer state.")
