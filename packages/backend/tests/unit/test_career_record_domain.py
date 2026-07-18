"""Focused executable invariants for the Phase 3 career/evidence domain."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from careeros.modules.career_record.domain import (
    CareerEntity,
    CareerEntityKind,
    CareerRecordTransitionRejected,
    CareerRecordValidationError,
    EmploymentType,
    EvidenceAuthority,
    EvidenceInputKind,
    EvidenceMetric,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceStrength,
    EvidenceType,
    MetricPrecision,
    PartialDate,
    ReminderPreferences,
    TimelineFindingKind,
    VerificationDecision,
    VerificationMethod,
    initial_revision,
    reorder_entities,
    timeline_findings,
    transition_revision,
)

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


def _experience(
    title: str,
    start: PartialDate,
    end: PartialDate | None,
    order: int,
    *,
    organization: str = "Example Corp",
    group_id: object | None = None,
) -> CareerEntity:
    owner = uuid4()
    return CareerEntity(
        id=uuid4(),
        owner_user_id=owner,
        profile_id=uuid4(),
        kind=CareerEntityKind.EXPERIENCE,
        title=title,
        organization=organization,
        description=None,
        official_title=title,
        display_title=None,
        employment_type=EmploymentType.FULL_TIME,
        location=None,
        external_url=None,
        start_date=start,
        end_date=end,
        is_current=end is None,
        sort_order=order,
        group_id=group_id if isinstance(group_id, type(owner)) else None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def test_partial_dates_urls_and_reminder_preferences_are_strict() -> None:
    with pytest.raises(CareerRecordValidationError):
        PartialDate(2020, 13)
    with pytest.raises(CareerRecordValidationError):
        CareerEntity(
            id=uuid4(),
            owner_user_id=uuid4(),
            profile_id=uuid4(),
            kind=CareerEntityKind.PORTFOLIO_LINK,
            title="Portfolio",
            organization=None,
            description=None,
            official_title=None,
            display_title=None,
            employment_type=None,
            location=None,
            external_url="https://user:secret@example.com/work",
            start_date=None,
            end_date=None,
            is_current=False,
            sort_order=0,
            group_id=None,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
    with pytest.raises(CareerRecordValidationError):
        ReminderPreferences(uuid4(), uuid4(), True, 29, "UTC", 1, NOW, NOW)
    preferences = ReminderPreferences(uuid4(), uuid4(), True, 15, "Asia/Kolkata", 1, NOW, NOW)
    assert preferences.day_of_month == 15


def test_timeline_findings_are_neutral_and_reorder_requires_complete_set() -> None:
    first = _experience("Engineer", PartialDate(2020, 1), PartialDate(2021, 1), 0)
    second = _experience("Engineer II", PartialDate(2021, 4), PartialDate(2022, 1), 1)
    findings = timeline_findings([first, second])
    assert [finding.kind for finding in findings] == [TimelineFindingKind.NEUTRAL_GAP]

    reorder_entities([first, second], [second.id, first.id])
    assert (first.sort_order, second.sort_order) == (1, 0)
    with pytest.raises(CareerRecordValidationError):
        reorder_entities([first, second], [first.id, first.id])


def test_external_url_is_provenance_only_and_cannot_self_support() -> None:
    source = EvidenceSource(
        id=uuid4(),
        owner_user_id=uuid4(),
        evidence_revision_id=uuid4(),
        kind=EvidenceSourceKind.EXTERNAL_URL,
        label="Public portfolio",
        provenance=None,
        attachment_id=None,
        external_url="https://example.com/work",
        available=True,
        exact_span_validated=False,
        created_at=NOW,
    )
    assert source.external_url == "https://example.com/work"
    with pytest.raises(CareerRecordValidationError):
        EvidenceSource(
            id=uuid4(),
            owner_user_id=source.owner_user_id,
            evidence_revision_id=uuid4(),
            kind=EvidenceSourceKind.EXTERNAL_URL,
            label="Invalid exact link",
            provenance=None,
            attachment_id=None,
            external_url="https://example.com/work",
            available=True,
            exact_span_validated=True,
            created_at=NOW,
        )


def test_numeric_confirmation_and_verification_authority_are_enforced() -> None:
    owner = uuid4()
    evidence_id = uuid4()
    revision = initial_revision(
        revision_id=uuid4(),
        owner_user_id=owner,
        evidence_id=evidence_id,
        evidence_type=EvidenceType.METRIC,
        title="Preparation time",
        statement="Reduced preparation time by 30%.",
        context=None,
        organization="Example Corp",
        project=None,
        start_date=None,
        end_date=None,
        input_kind=EvidenceInputKind.MANUAL,
        exact_span_validated=False,
        created_at=NOW,
    )
    with pytest.raises(CareerRecordValidationError):
        transition_revision(
            current=revision,
            revision_id=uuid4(),
            transition_id=uuid4(),
            next_strength=EvidenceStrength.CONFIRMED,
            authority=EvidenceAuthority.OWNER_CONFIRMATION,
            reason_code="owner_confirmed_scope",
            actor_user_id=owner,
            request_id="request",
            trace_id="trace",
            created_at=NOW,
        )
    metric = EvidenceMetric(
        id=uuid4(),
        owner_user_id=owner,
        evidence_revision_id=revision.id,
        name="Preparation time reduction",
        value=Decimal("30"),
        value_max=None,
        unit="percent",
        currency=None,
        period="Q2 2026",
        baseline=None,
        comparator="before implementation",
        comparison_applicable=True,
        precision=MetricPrecision.EXACT,
        attribution="My reporting automation",
        created_at=NOW,
    )
    confirmed, _ = transition_revision(
        current=revision,
        revision_id=uuid4(),
        transition_id=uuid4(),
        next_strength=EvidenceStrength.CONFIRMED,
        authority=EvidenceAuthority.OWNER_CONFIRMATION,
        reason_code="owner_confirmed_scope",
        actor_user_id=owner,
        request_id="request",
        trace_id="trace",
        created_at=NOW,
        metrics=(metric,),
    )
    with pytest.raises(CareerRecordTransitionRejected):
        transition_revision(
            current=confirmed,
            revision_id=uuid4(),
            transition_id=uuid4(),
            next_strength=EvidenceStrength.VERIFIED,
            authority=EvidenceAuthority.OWNER_CONFIRMATION,
            reason_code="client_requested_verified",
            actor_user_id=owner,
            request_id="request",
            trace_id="trace",
            created_at=NOW,
            metrics=(metric,),
        )
    decision = VerificationDecision(
        VerificationMethod.APPROVED_MANUAL_REVIEW,
        "review-123",
        "internal-review-record",
        "exact metric statement",
        NOW,
    )
    verified, _ = transition_revision(
        current=confirmed,
        revision_id=uuid4(),
        transition_id=uuid4(),
        next_strength=EvidenceStrength.VERIFIED,
        authority=EvidenceAuthority.SERVER_VERIFICATION,
        reason_code="server_verification_authorized",
        actor_user_id=owner,
        request_id="request",
        trace_id="trace",
        created_at=NOW,
        metrics=(metric,),
        verification=decision,
    )
    assert verified.strength is EvidenceStrength.VERIFIED
