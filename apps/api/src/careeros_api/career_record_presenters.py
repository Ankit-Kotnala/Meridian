"""Pure Career Record wire presenters; no authorization or persistence lives here."""

from __future__ import annotations

from hashlib import sha256
from typing import Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from careeros.modules.career_record.application.models import EvidenceRecord
from careeros.modules.career_record.domain import (
    AchievementDraft,
    AchievementMetric,
    AchievementStatus,
    AttachmentStatus,
    CareerEntity,
    CareerEntityRelationship,
    CareerFieldProvenance,
    CareerProfile,
    EvidenceAttachment,
    EvidenceConflict,
    EvidenceConflictKind,
    EvidenceMetric,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceStrength,
    ImportProposal,
    PartialDate,
    PersonalFact,
    ReminderPreferences,
    SemanticFieldOrigin,
    SemanticImportProposal,
    Skill,
    SkillProficiency,
    TimelineFinding,
    TimelineFindingKind,
)
from careeros.modules.career_record.domain.errors import CareerRecordValidationError
from careeros.modules.career_record.domain.policies import EligibilityDecision
from careeros.modules.identity.application.models import CurrentUser

from careeros_api.career_record_schemas import (
    AccountPreferenceSnapshotResponse,
    AchievementAnswers,
    AchievementResponse,
    CareerItemResponse,
    CareerProfileResponse,
    CareerRelationshipResponse,
    EvidenceAttachmentResponse,
    EvidenceConflictResponse,
    EvidenceHistoryResponse,
    EvidenceMetricResponse,
    EvidenceResponse,
    EvidenceUsageResponse,
    ExperienceResponse,
    ImportProposalChangeResponse,
    ImportProposalResponse,
    PersonalFactResponse,
    ProfileConflictResponse,
    ProvenanceResponse,
    ReminderPreferencesResponse,
    SemanticImportAnchorResponse,
    SemanticImportFieldResponse,
    SemanticImportProposalResponse,
    SkillResponse,
    SourceSpanResponse,
)


def year_month(value: PartialDate | None) -> str | None:
    if value is None:
        return None
    if value.month is None:
        return f"{value.year:04d}"
    return f"{value.year:04d}-{value.month:02d}"


def profile_response(profile: CareerProfile, account: CurrentUser) -> CareerProfileResponse:
    return CareerProfileResponse(
        id=profile.id,
        version=profile.version,
        professional_headline=profile.professional_headline or "",
        professional_summary=profile.summary or "",
        work_authorization=profile.work_authorization or "",
        account_preferences=AccountPreferenceSnapshotResponse(
            display_name=account.display_name,
            email=account.email,
            target_role=account.target_role,
            preferred_location=account.preferred_location,
            work_model=account.work_model,
            seniority=account.seniority,
            industry=account.industry,
            language=account.language,
        ),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def personal_fact_response(
    fact: PersonalFact,
    *,
    provenance: list[ProvenanceResponse] | None = None,
) -> PersonalFactResponse:
    return PersonalFactResponse(
        id=fact.id,
        kind=fact.kind.value,
        value=fact.value,
        label=fact.label,
        is_primary=fact.is_primary,
        confirmation=fact.confirmation.value,
        version=fact.version,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
        confirmed_at=fact.confirmed_at,
        provenance=provenance or [],
    )


def career_relationship_response(
    relationship: CareerEntityRelationship,
) -> CareerRelationshipResponse:
    return CareerRelationshipResponse(
        id=relationship.id,
        experience_id=relationship.source_entity_id,
        project_id=relationship.target_entity_id,
        kind=relationship.kind.value,
        created_at=relationship.created_at,
    )


def field_provenance_response(
    value: CareerFieldProvenance,
    *,
    available: bool,
) -> ProvenanceResponse:
    labels = {
        SemanticFieldOrigin.RESUME_PARSER: "Confirmed typed resume field",
        SemanticFieldOrigin.RESUME_USER_ADDED: "Added during typed resume review",
        SemanticFieldOrigin.OWNER_EDIT: "Edited during typed resume import review",
        SemanticFieldOrigin.OWNER_ATTESTATION: "Owner-confirmed current field",
    }
    return ProvenanceResponse(
        id=value.id,
        source_type=(
            "manual" if value.origin is SemanticFieldOrigin.OWNER_ATTESTATION else "resume"
        ),
        source_label=f"{labels[value.origin]}: {value.field_name.replace('_', ' ')}",
        source_document_id=value.document_id,
        source_snapshot_id=value.snapshot_id,
        source_revision=value.snapshot_revision,
        parser_version=value.parser_version,
        confidence=None,
        user_confirmed=True,
        available=available,
        spans=[
            SourceSpanResponse(
                id=uuid5(
                    NAMESPACE_URL,
                    (
                        f"careeros:field-provenance:{value.id}:"
                        f"{anchor.block_id}:{anchor.start_offset}"
                    ),
                ),
                page=anchor.page,
                start=anchor.start_offset,
                end=anchor.end_offset,
                excerpt=anchor.source_excerpt,
                digest=f"sha256:{anchor.source_sha256.hex()}",
            )
            for anchor in value.anchors
        ],
    )


def experience_response(
    entity: CareerEntity,
    *,
    user_confirmed: bool = False,
    findings: tuple[TimelineFinding, ...] = (),
    skill_ids: tuple[UUID, ...] = (),
    provenance: list[ProvenanceResponse] | None = None,
) -> ExperienceResponse:
    if entity.start_date is None:
        raise CareerRecordValidationError("an experience needs a known start month for this view")
    related = tuple(item for item in findings if entity.id in item.entity_ids)
    promotion_group = (
        entity.group_id
        if any(item.kind is TimelineFindingKind.PROMOTION_SEQUENCE for item in related)
        else None
    )
    concurrent_group = (
        entity.group_id
        if any(item.kind is TimelineFindingKind.CONCURRENT_ROLES for item in related)
        else None
    )
    return ExperienceResponse(
        id=entity.id,
        employer=entity.organization or "",
        official_title=entity.official_title or entity.title,
        display_title=entity.display_title,
        start_date=year_month(entity.start_date),  # type: ignore[arg-type]
        end_date=year_month(entity.end_date),
        current=entity.is_current,
        location=entity.location,
        employment_type=entity.employment_type.value if entity.employment_type else None,
        description=entity.description or "",
        skill_ids=list(skill_ids),
        version=entity.version,
        order=entity.sort_order,
        user_confirmed=user_confirmed,
        promotion_group_id=promotion_group,
        concurrent_group_id=concurrent_group,
        conflicts=[timeline_finding_response(item) for item in related],
        provenance=provenance or [],
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def career_item_response(
    entity: CareerEntity,
    *,
    user_confirmed: bool = False,
    provenance: list[ProvenanceResponse] | None = None,
) -> CareerItemResponse:
    return CareerItemResponse(
        id=entity.id,
        kind=entity.kind.value,  # type: ignore[arg-type]
        title=entity.title,
        organization=entity.organization,
        description=entity.description or "",
        start_date=year_month(entity.start_date),
        end_date=year_month(entity.end_date),
        url=entity.external_url,  # type: ignore[arg-type]
        version=entity.version,
        order=entity.sort_order,
        user_confirmed=user_confirmed,
        provenance=provenance or [],
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def skill_response(
    skill: Skill,
    *,
    user_confirmed: bool = False,
    provenance: list[ProvenanceResponse] | None = None,
) -> SkillResponse:
    proficiency = (
        None
        if skill.proficiency is None
        else {
            SkillProficiency.BEGINNER: "learning",
            SkillProficiency.INTERMEDIATE: "working",
            SkillProficiency.ADVANCED: "advanced",
            SkillProficiency.EXPERT: "expert",
        }[skill.proficiency]
    )
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        category=skill.category,
        proficiency=proficiency,  # type: ignore[arg-type]
        version=skill.version,
        order=skill.sort_order,
        user_confirmed=user_confirmed,
        provenance=provenance or [],
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def timeline_finding_response(value: TimelineFinding) -> ProfileConflictResponse:
    messages = {
        TimelineFindingKind.NEUTRAL_GAP: "A gap is shown for review; it is not scored negatively.",
        TimelineFindingKind.CONCURRENT_ROLES: "These roles overlap and may be concurrent.",
        TimelineFindingKind.PROMOTION_SEQUENCE: "These grouped roles form a promotion sequence.",
        TimelineFindingKind.REVIEW_OVERLAP: "These dates overlap and need your review.",
    }
    identity = uuid5(
        NAMESPACE_URL,
        "careeros:timeline:" + value.code + ":" + ":".join(map(str, value.entity_ids)),
    )
    return ProfileConflictResponse(
        id=identity,
        field="timeline",
        code=value.code,
        message=messages[value.kind],
        severity="information"
        if value.kind is not TimelineFindingKind.REVIEW_OVERLAP
        else "review",
        related_entity_ids=list(value.entity_ids),
    )


def proposal_response(
    proposal: ImportProposal,
    *,
    source_document_name: str,
    current: CareerEntity | None,
    source_available: bool,
) -> ImportProposalResponse:
    proposed = proposal.proposed_entity
    values: tuple[tuple[str, str, str | None, str], ...] = (
        ("title", "Title", current.title if current else None, proposed.title),
        (
            "organization",
            "Organization",
            current.organization if current else None,
            proposed.organization or "",
        ),
        (
            "description",
            "Description",
            current.description if current else None,
            proposed.description or "",
        ),
        (
            "startDate",
            "Start month",
            year_month(current.start_date) if current else None,
            year_month(proposed.start_date) or "",
        ),
        (
            "endDate",
            "End month",
            year_month(current.end_date) if current else None,
            year_month(proposed.end_date) or "",
        ),
    )
    source = provenance_from_proposal(proposal, available=source_available)
    changes = [
        ImportProposalChangeResponse(
            id=uuid5(NAMESPACE_URL, f"careeros:proposal:{proposal.id}:{field}"),
            field=field,
            label=label,
            current_value=old,
            proposed_value=new,
            conflict=proposal.conflict_code,
            source=source,
        )
        for field, label, old, new in values
        if old != new
    ]
    if not changes:
        changes.append(
            ImportProposalChangeResponse(
                id=uuid5(NAMESPACE_URL, f"careeros:proposal:{proposal.id}:review"),
                field="review",
                label="Review source",
                current_value=None,
                proposed_value=proposed.title,
                conflict=proposal.conflict_code,
                source=source,
            )
        )
    return ImportProposalResponse(
        id=proposal.id,
        source_document_name=source_document_name,
        status=proposal.status.value,
        version=proposal.version,
        changes=changes,
        created_at=proposal.created_at,
        decided_at=proposal.reviewed_at,
    )


def provenance_from_proposal(proposal: ImportProposal, *, available: bool) -> ProvenanceResponse:
    value = proposal.provenance
    return ProvenanceResponse(
        id=uuid5(NAMESPACE_URL, f"careeros:proposal-source:{proposal.id}"),
        source_type="resume",
        source_label=(
            "Legacy resume context — owner-reviewed, not field-validated"
            if proposal.status.value == "accepted"
            else "Legacy resume context — needs semantic review"
        ),
        source_document_id=value.document_id,
        source_snapshot_id=value.snapshot_id,
        source_revision=value.snapshot_revision,
        parser_version=value.parser_version,
        confidence=None,
        user_confirmed=proposal.status.value == "accepted",
        available=available,
        spans=[
            SourceSpanResponse(
                id=value.block_id,
                page=value.page,
                start=value.start_offset,
                end=max(value.end_offset, value.start_offset + 1),
                excerpt=value.review_excerpt,
                digest=f"sha256:{value.source_sha256.hex()}",
            )
        ],
    )


def semantic_import_proposal_response(
    proposal: SemanticImportProposal,
    *,
    source_available: bool,
) -> SemanticImportProposalResponse:
    accepted = proposal.accepted_values or {}
    return SemanticImportProposalResponse(
        id=proposal.id,
        target=cast(
            Literal["personalFacts", "entity", "skill"],
            {
                "personal_facts": "personalFacts",
                "entity": "entity",
                "skill": "skill",
            }[proposal.target.value],
        ),
        target_record_id=proposal.target_record_id,
        document_id=proposal.document_id,
        snapshot_id=proposal.snapshot_id,
        snapshot_revision=proposal.snapshot_revision,
        schema_version=proposal.schema_version,
        parser_version=proposal.parser_version,
        semantic_entity_id=proposal.semantic_entity_id,
        semantic_kind=proposal.semantic_kind.value,
        status=proposal.status.value,
        conflict_code=proposal.conflict_code,
        source_available=source_available,
        version=proposal.version,
        fields=[
            SemanticImportFieldResponse(
                id=field.semantic_field_id,
                name=field.name,
                field_type=cast(
                    Literal["text", "email", "phone", "url", "date", "bullet"],
                    field.field_type,
                ),
                proposed_value=field.value,
                accepted_value=accepted.get(str(field.semantic_field_id)),
                review_state=field.review_state.value,
                confidence=field.confidence_basis_points / 10_000,
                date_precision=cast(
                    Literal["day", "month", "year", "unknown"] | None,
                    field.date_precision,
                ),
                anchors=[
                    SemanticImportAnchorResponse(
                        block_id=anchor.block_id,
                        page=anchor.page,
                        start=anchor.start_offset,
                        end=anchor.end_offset,
                        digest=f"sha256:{anchor.source_sha256.hex()}",
                        excerpt=anchor.source_excerpt,
                    )
                    for anchor in field.anchors
                ],
            )
            for field in proposal.fields
        ],
        created_at=proposal.created_at,
        reviewed_at=proposal.reviewed_at,
    )


def evidence_response(record: EvidenceRecord, decision: EligibilityDecision) -> EvidenceResponse:
    revision = record.revision
    return EvidenceResponse(
        id=record.item.id,
        type=_wire_evidence_type(revision.evidence_type.value),
        title=revision.title,
        description=revision.statement,
        organization_or_project=revision.organization or revision.project,
        start_date=year_month(revision.start_date),
        end_date=year_month(revision.end_date),
        state=revision.strength.value,
        lifecycle=record.item.lifecycle.value,  # type: ignore[arg-type]
        version=record.item.version,
        revision=revision.revision,
        user_confirmed=revision.strength in {EvidenceStrength.CONFIRMED, EvidenceStrength.VERIFIED},
        factual_eligible=decision.factual_eligible,
        numeric_eligible=decision.numeric_eligible,
        eligibility_reasons=list(decision.reason_codes),
        archived_at=record.item.archived_at,
        provenance=[source_response(item, revision.strength) for item in record.sources],
        metrics=[metric_response(item) for item in record.metrics],
        attachments=[attachment_response(item) for item in record.attachments],
        usage=[
            EvidenceUsageResponse(
                id=item.id,
                type=_usage_type(item.consumer_kind),
                label=item.purpose,
            )
            for item in record.usage
        ],
        history=[
            EvidenceHistoryResponse(
                id=item.id,
                from_state=item.previous_strength.value if item.previous_strength else None,
                to_state=item.next_strength.value,
                reason=item.reason_code.replace("_", " ").capitalize(),
                actor_label="You" if item.actor_user_id == record.item.owner_user_id else "System",
                created_at=item.created_at,
            )
            for item in record.transitions
        ],
        conflicts=[conflict_response(item) for item in record.conflicts],
        created_at=record.item.created_at,
        updated_at=record.item.updated_at,
    )


def source_response(source: EvidenceSource, strength: EvidenceStrength) -> ProvenanceResponse:
    provenance = source.provenance
    spans: list[SourceSpanResponse] = []
    if provenance is not None:
        spans.append(
            SourceSpanResponse(
                id=provenance.block_id,
                page=provenance.page,
                start=provenance.start_offset,
                end=max(provenance.end_offset, provenance.start_offset + 1),
                excerpt=provenance.review_excerpt,
                digest=f"sha256:{provenance.source_sha256.hex()}",
            )
        )
    return ProvenanceResponse(
        id=source.id,
        source_type=cast(
            Literal["manual", "resume", "achievement", "attachment", "url"],
            {
                EvidenceSourceKind.USER_ATTESTATION: "manual",
                EvidenceSourceKind.RESUME: "resume",
                EvidenceSourceKind.ATTACHMENT: "attachment",
                EvidenceSourceKind.ACHIEVEMENT: "achievement",
                EvidenceSourceKind.EXTERNAL_URL: "url",
                EvidenceSourceKind.INDEPENDENT_VERIFIER: "manual",
            }[source.kind],
        ),
        source_label=source.label,
        source_document_id=provenance.document_id if provenance else None,
        source_snapshot_id=provenance.snapshot_id if provenance else None,
        source_revision=provenance.snapshot_revision if provenance else None,
        parser_version=provenance.parser_version if provenance else None,
        confidence=None,
        user_confirmed=strength in {EvidenceStrength.CONFIRMED, EvidenceStrength.VERIFIED},
        available=source.available,
        spans=spans,
    )


def metric_response(
    value: EvidenceMetric | AchievementMetric,
) -> EvidenceMetricResponse:
    period_start, _, period_end = value.period.partition("/")
    return EvidenceMetricResponse(
        id=value.id if isinstance(value, EvidenceMetric) else None,
        name=value.name or "Measured result",
        value=value.value,
        unit=value.unit,
        period_start=period_start,
        period_end=period_end or None,
        baseline=value.baseline,
        comparator=value.comparator,
        precision=_wire_precision(value.precision.value),
        attribution=_wire_attribution(value.attribution),
    )


def attachment_response(value: EvidenceAttachment) -> EvidenceAttachmentResponse:
    return EvidenceAttachmentResponse(
        id=value.id,
        display_filename=value.display_filename,
        media_type=value.media_type,
        size_bytes=value.size_bytes,
        status={
            AttachmentStatus.PENDING: "uploading",
            AttachmentStatus.QUARANTINED: "scanning",
            AttachmentStatus.CLEAN: "ready",
            AttachmentStatus.REJECTED: "failed",
            AttachmentStatus.DELETING: "deleting",
            AttachmentStatus.DELETED: "deleting",
        }[value.status],  # type: ignore[arg-type]
        safe_error_code="attachment_rejected"
        if value.status is AttachmentStatus.REJECTED
        else None,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def conflict_response(value: EvidenceConflict) -> EvidenceConflictResponse:
    code = cast(
        Literal["duplicate_claim", "metric_mismatch", "entity_mismatch", "date_mismatch"],
        {
            EvidenceConflictKind.DATE: "date_mismatch",
            EvidenceConflictKind.TITLE: "entity_mismatch",
            EvidenceConflictKind.METRIC: "metric_mismatch",
            EvidenceConflictKind.ENTITY: "entity_mismatch",
            EvidenceConflictKind.SOURCE: "duplicate_claim",
        }[value.kind],
    )
    return EvidenceConflictResponse(
        id=value.id,
        code=code,
        message=value.code.replace("_", " ").capitalize(),
        related_evidence_id=value.conflicting_evidence_id or value.evidence_id,
        status="open" if value.status.value == "open" else "resolved",
        version=value.version,
    )


def achievement_response(value: AchievementDraft) -> AchievementResponse:
    status = value.status.value
    if value.status is AchievementStatus.DRAFT and all(
        (value.delivered, value.problem, value.effect)
    ):
        status = "ready"
    return AchievementResponse(
        id=value.id,
        title=value.title,
        answers=AchievementAnswers(
            delivered=value.delivered or "",
            problem=value.problem or "",
            changed=value.effect or "",
            affected=value.audience or "",
            measurement=value.measurement or "",
            collaboration=value.collaboration or "",
            methods=value.methods or "",
        ),
        metric=None if value.metric is None else metric_response(value.metric),
        employer_id=value.entity_id,
        project_id=None,
        status=status,  # type: ignore[arg-type]
        evidence_id=value.converted_evidence_id,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def reminder_response(value: ReminderPreferences) -> ReminderPreferencesResponse:
    return ReminderPreferencesResponse(
        enabled=value.enabled,
        day_of_month=value.day_of_month,
        timezone=value.timezone,
        version=value.version,
        updated_at=value.updated_at,
    )


def _wire_evidence_type(value: str) -> str:
    return {
        "achievement": "user_confirmed_achievement",
        "credential": "certificate",
        "review_excerpt": "performance_review_excerpt",
        "portfolio": "portfolio_link",
        "support_document": "supporting_document",
        "note": "user_note",
    }.get(value, value)


def _wire_attribution(value: str) -> Literal["individual", "team", "shared"]:
    normalized = value.casefold()
    if normalized in {"individual", "team", "shared"}:
        return cast(Literal["individual", "team", "shared"], normalized)
    return "shared"


def _wire_precision(value: str) -> Literal["exact", "approximate"]:
    return "exact" if value == "exact" else "approximate"


def _usage_type(value: str) -> Literal["experience", "skill", "requirement", "output"]:
    if value in {"experience", "skill", "requirement", "output"}:
        return cast(Literal["experience", "skill", "requirement", "output"], value)
    return "output"


def stable_content_digest(value: str) -> str:
    """Useful in tests without exposing stored content in identifiers or logs."""

    return sha256(value.encode("utf-8")).hexdigest()
