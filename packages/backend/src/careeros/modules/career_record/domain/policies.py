"""Deterministic Career Record policies shared by every delivery surface."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from uuid import UUID

from .entities import (
    AttachmentStatus,
    CareerEntity,
    CareerEntityKind,
    EvidenceAttachment,
    EvidenceAuthority,
    EvidenceConflict,
    EvidenceInputKind,
    EvidenceItem,
    EvidenceLifecycle,
    EvidenceMetric,
    EvidenceRevision,
    EvidenceSource,
    EvidenceStateTransition,
    EvidenceStrength,
    EvidenceType,
    PartialDate,
    TimelineFinding,
    TimelineFindingKind,
    VerificationDecision,
)
from .errors import CareerRecordTransitionRejected, CareerRecordValidationError


def reorder_entities(entities: Sequence[CareerEntity], ordered_ids: Sequence[UUID]) -> None:
    """Apply a complete, duplicate-free ordering to one owned profile list."""

    if not entities:
        if ordered_ids:
            raise CareerRecordValidationError("cannot order unknown entities")
        return
    existing_ids = {entity.id for entity in entities}
    requested_ids = set(ordered_ids)
    if len(requested_ids) != len(ordered_ids):
        raise CareerRecordValidationError("entity order contains duplicate IDs")
    if requested_ids != existing_ids:
        raise CareerRecordValidationError("entity order must contain the complete owned set")
    position = {entity_id: index for index, entity_id in enumerate(ordered_ids)}
    for entity in entities:
        entity.sort_order = position[entity.id]


def timeline_findings(entities: Sequence[CareerEntity]) -> tuple[TimelineFinding, ...]:
    """Describe gaps/concurrency neutrally; never treat a gap as negative evidence."""

    experiences = sorted(
        (
            entity
            for entity in entities
            if entity.kind is CareerEntityKind.EXPERIENCE and entity.start_date is not None
        ),
        key=lambda entity: (
            entity.start_date.earliest_month if entity.start_date is not None else -1,
            entity.sort_order,
            str(entity.id),
        ),
    )
    findings: list[TimelineFinding] = []
    for left, right in pairwise(experiences):
        if right.start_date is None:
            continue
        if left.end_date is None:
            same_organization = (left.organization or "").casefold() == (
                right.organization or ""
            ).casefold()
            grouped = left.group_id is not None and left.group_id == right.group_id
            if same_organization and grouped:
                kind = TimelineFindingKind.PROMOTION_SEQUENCE
                code = "grouped_promotion_sequence"
            elif not same_organization:
                kind = TimelineFindingKind.CONCURRENT_ROLES
                code = "concurrent_current_role"
            else:
                kind = TimelineFindingKind.REVIEW_OVERLAP
                code = "same_employer_overlap_needs_review"
            findings.append(
                TimelineFinding(
                    kind=kind,
                    entity_ids=(left.id, right.id),
                    start=right.start_date,
                    end=None,
                    code=code,
                )
            )
            continue
        gap_months = right.start_date.earliest_month - left.end_date.latest_month - 1
        if gap_months > 0:
            findings.append(
                TimelineFinding(
                    kind=TimelineFindingKind.NEUTRAL_GAP,
                    entity_ids=(left.id, right.id),
                    start=_month_date(left.end_date.latest_month + 1),
                    end=_month_date(right.start_date.earliest_month - 1),
                    code="timeline_gap_observed",
                )
            )
            continue
        if gap_months < 0:
            same_organization = (left.organization or "").casefold() == (
                right.organization or ""
            ).casefold()
            grouped = left.group_id is not None and left.group_id == right.group_id
            if same_organization and grouped:
                kind = TimelineFindingKind.PROMOTION_SEQUENCE
                code = "grouped_promotion_sequence"
            elif not same_organization:
                kind = TimelineFindingKind.CONCURRENT_ROLES
                code = "concurrent_roles_observed"
            else:
                kind = TimelineFindingKind.REVIEW_OVERLAP
                code = "same_employer_overlap_needs_review"
            findings.append(
                TimelineFinding(
                    kind=kind,
                    entity_ids=(left.id, right.id),
                    start=right.start_date,
                    end=left.end_date,
                    code=code,
                )
            )
    return tuple(findings)


def _month_date(month_index: int) -> PartialDate:
    year, month_zero = divmod(month_index, 12)
    return PartialDate(year=year, month=month_zero + 1)


def initial_strength(
    input_kind: EvidenceInputKind, *, exact_span_validated: bool
) -> EvidenceStrength:
    """Derive initial strength; callers never submit the result directly."""

    if input_kind is EvidenceInputKind.EXACT_SOURCE_SPAN:
        if not exact_span_validated:
            raise CareerRecordValidationError("supported evidence requires a validated exact span")
        return EvidenceStrength.SUPPORTED
    if exact_span_validated:
        raise CareerRecordValidationError("only exact-source input can carry validated span status")
    return EvidenceStrength.INFERRED


def initial_revision(
    *,
    revision_id: UUID,
    owner_user_id: UUID,
    evidence_id: UUID,
    evidence_type: EvidenceType,
    title: str,
    statement: str,
    context: str | None,
    organization: str | None,
    project: str | None,
    start_date: PartialDate | None,
    end_date: PartialDate | None,
    input_kind: EvidenceInputKind,
    exact_span_validated: bool,
    created_at: datetime,
) -> EvidenceRevision:
    return EvidenceRevision(
        id=revision_id,
        owner_user_id=owner_user_id,
        evidence_id=evidence_id,
        revision=1,
        evidence_type=evidence_type,
        title=title,
        statement=statement,
        context=context,
        organization=organization,
        project=project,
        start_date=start_date,
        end_date=end_date,
        strength=initial_strength(input_kind, exact_span_validated=exact_span_validated),
        input_kind=input_kind,
        created_at=created_at,
    )


def transition_revision(
    *,
    current: EvidenceRevision,
    revision_id: UUID,
    transition_id: UUID,
    next_strength: EvidenceStrength,
    authority: EvidenceAuthority,
    reason_code: str,
    actor_user_id: UUID | None,
    request_id: str,
    trace_id: str,
    created_at: datetime,
    metrics: Sequence[EvidenceMetric] = (),
    verification: VerificationDecision | None = None,
) -> tuple[EvidenceRevision, EvidenceStateTransition]:
    """Create an immutable strength-transition successor and audit record."""

    _validate_transition(
        current=current,
        next_strength=next_strength,
        authority=authority,
        actor_user_id=actor_user_id,
        metrics=metrics,
        verification=verification,
    )
    successor = EvidenceRevision(
        id=revision_id,
        owner_user_id=current.owner_user_id,
        evidence_id=current.evidence_id,
        revision=current.revision + 1,
        evidence_type=current.evidence_type,
        title=current.title,
        statement=current.statement,
        context=current.context,
        organization=current.organization,
        project=current.project,
        start_date=current.start_date,
        end_date=current.end_date,
        strength=next_strength,
        input_kind=current.input_kind,
        created_at=created_at,
    )
    transition = EvidenceStateTransition(
        id=transition_id,
        owner_user_id=current.owner_user_id,
        evidence_id=current.evidence_id,
        from_revision_id=current.id,
        to_revision_id=successor.id,
        previous_strength=current.strength,
        next_strength=next_strength,
        authority=authority,
        reason_code=reason_code,
        actor_user_id=actor_user_id,
        verifier_reference=(verification.verifier_reference if verification is not None else None),
        request_id=request_id,
        trace_id=trace_id,
        created_at=created_at,
    )
    return successor, transition


def material_revision(
    *,
    current: EvidenceRevision,
    revision_id: UUID,
    transition_id: UUID,
    evidence_type: EvidenceType,
    title: str,
    statement: str,
    context: str | None,
    organization: str | None,
    project: str | None,
    start_date: PartialDate | None,
    end_date: PartialDate | None,
    actor_user_id: UUID,
    reason_code: str,
    request_id: str,
    trace_id: str,
    created_at: datetime,
) -> tuple[EvidenceRevision, EvidenceStateTransition]:
    """A factual edit always invalidates prior confirmation or verification."""

    successor = EvidenceRevision(
        id=revision_id,
        owner_user_id=current.owner_user_id,
        evidence_id=current.evidence_id,
        revision=current.revision + 1,
        evidence_type=evidence_type,
        title=title,
        statement=statement,
        context=context,
        organization=organization,
        project=project,
        start_date=start_date,
        end_date=end_date,
        strength=EvidenceStrength.INFERRED,
        input_kind=EvidenceInputKind.MATERIAL_EDIT,
        created_at=created_at,
    )
    transition = EvidenceStateTransition(
        id=transition_id,
        owner_user_id=current.owner_user_id,
        evidence_id=current.evidence_id,
        from_revision_id=current.id,
        to_revision_id=successor.id,
        previous_strength=current.strength,
        next_strength=EvidenceStrength.INFERRED,
        authority=EvidenceAuthority.MATERIAL_EDIT,
        reason_code=reason_code,
        actor_user_id=actor_user_id,
        verifier_reference=None,
        request_id=request_id,
        trace_id=trace_id,
        created_at=created_at,
    )
    return successor, transition


def _validate_transition(
    *,
    current: EvidenceRevision,
    next_strength: EvidenceStrength,
    authority: EvidenceAuthority,
    actor_user_id: UUID | None,
    metrics: Sequence[EvidenceMetric],
    verification: VerificationDecision | None,
) -> None:
    if next_strength is current.strength:
        raise CareerRecordTransitionRejected("evidence strength is unchanged")
    if next_strength is EvidenceStrength.CONFIRMED:
        if current.strength not in {EvidenceStrength.INFERRED, EvidenceStrength.SUPPORTED}:
            raise CareerRecordTransitionRejected("this evidence cannot be owner-confirmed")
        if authority is not EvidenceAuthority.OWNER_CONFIRMATION:
            raise CareerRecordTransitionRejected("confirmation requires owner authority")
        if actor_user_id != current.owner_user_id:
            raise CareerRecordTransitionRejected("only the evidence owner can confirm")
        if current.has_numeric_claim and (
            not metrics or any(not metric.complete for metric in metrics)
        ):
            raise CareerRecordValidationError(
                "numeric confirmation requires complete structured metric dimensions"
            )
        if any(metric.owner_user_id != current.owner_user_id for metric in metrics):
            raise CareerRecordValidationError("metric owner does not match evidence owner")
        if verification is not None:
            raise CareerRecordValidationError("owner confirmation cannot include verification")
        return
    if next_strength is EvidenceStrength.UNSUPPORTED:
        if authority not in {
            EvidenceAuthority.OWNER_REJECTION,
            EvidenceAuthority.DETERMINISTIC_POLICY,
        }:
            raise CareerRecordTransitionRejected("unsupported requires owner or policy authority")
        if (
            authority is EvidenceAuthority.OWNER_REJECTION
            and actor_user_id != current.owner_user_id
        ):
            raise CareerRecordTransitionRejected("only the owner can reject evidence")
        if verification is not None:
            raise CareerRecordValidationError("unsupported evidence cannot be verified")
        return
    if next_strength is EvidenceStrength.VERIFIED:
        if current.strength not in {EvidenceStrength.SUPPORTED, EvidenceStrength.CONFIRMED}:
            raise CareerRecordTransitionRejected(
                "only supported or confirmed evidence is verifiable"
            )
        if authority is not EvidenceAuthority.SERVER_VERIFICATION or verification is None:
            raise CareerRecordTransitionRejected("verified requires a server verification decision")
        if current.has_numeric_claim and (
            not metrics or any(not metric.complete for metric in metrics)
        ):
            raise CareerRecordValidationError(
                "numeric verification requires complete structured metric dimensions"
            )
        return
    raise CareerRecordTransitionRejected("requested evidence transition is not allowed")


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    factual_eligible: bool
    numeric_eligible: bool
    reason_codes: tuple[str, ...]
    has_numeric_claim: bool

    @property
    def eligible(self) -> bool:
        return self.factual_eligible and (not self.has_numeric_claim or self.numeric_eligible)


def evidence_eligibility(
    *,
    item: EvidenceItem,
    revision: EvidenceRevision,
    sources: Sequence[EvidenceSource],
    metrics: Sequence[EvidenceMetric],
    attachments: Sequence[EvidenceAttachment],
    conflicts: Sequence[EvidenceConflict],
    source_availability: Mapping[UUID, bool],
    authorized_owner_user_id: UUID,
) -> EligibilityDecision:
    """Apply the sole deterministic downstream evidence-selection boundary."""

    factual_reasons: list[str] = []
    if (
        item.owner_user_id != authorized_owner_user_id
        or revision.owner_user_id != item.owner_user_id
    ):
        factual_reasons.append("unauthorized")
    if item.lifecycle is not EvidenceLifecycle.ACTIVE:
        factual_reasons.append(f"lifecycle_{item.lifecycle.value}")
    if revision.strength in {EvidenceStrength.INFERRED, EvidenceStrength.UNSUPPORTED}:
        factual_reasons.append(f"strength_{revision.strength.value}")
    if any(conflict.status.value == "open" for conflict in conflicts):
        factual_reasons.append("open_conflict")
    if not sources:
        factual_reasons.append("missing_provenance")
    effective_available = [
        source.available and source_availability.get(source.id, source.available)
        for source in sources
    ]
    if sources and not any(effective_available):
        factual_reasons.append("source_unavailable")
    if revision.strength is EvidenceStrength.SUPPORTED and not any(
        source.exact_span_validated and effective_available[index]
        for index, source in enumerate(sources)
    ):
        factual_reasons.append("supported_scope_unavailable")
    if any(attachment.status is not AttachmentStatus.CLEAN for attachment in attachments):
        factual_reasons.append("attachment_not_clean")
    numeric_reasons = list(factual_reasons)
    if revision.has_numeric_claim:
        if revision.strength not in {EvidenceStrength.CONFIRMED, EvidenceStrength.VERIFIED}:
            numeric_reasons.append("numeric_strength_insufficient")
        if not metrics or any(not metric.complete for metric in metrics):
            numeric_reasons.append("numeric_dimensions_incomplete")
    return EligibilityDecision(
        factual_eligible=not factual_reasons,
        numeric_eligible=revision.has_numeric_claim and not numeric_reasons,
        reason_codes=tuple(dict.fromkeys((*factual_reasons, *numeric_reasons))),
        has_numeric_claim=revision.has_numeric_claim,
    )
