"""Deterministic fictional graph used by the guarded local seed command."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen.canvas import Canvas

from careeros.modules.application_workspace.infrastructure.models import (
    ApplicationRecordModel,
)
from careeros.modules.career_analytics.application import (
    METRIC_DEFINITION_VERSION,
    AnalyticsBreakdown,
    AnalyticsPayload,
    AnalyticsRate,
    AnalyticsTimeBucket,
    RequirementCoverageTrendPoint,
    ResumeVersionOutcomePerformance,
)
from careeros.modules.career_analytics.domain import AnalyticsScope
from careeros.modules.career_analytics.infrastructure.models import (
    AnalyticsRefreshJobModel,
    AnalyticsSnapshotModel,
)
from careeros.modules.career_growth.infrastructure.models import CareerGoalModel
from careeros.modules.career_record.infrastructure.models import (
    CareerEntityConfirmationModel,
    CareerEntityModel,
    CareerPersonalFactModel,
    CareerProfileModel,
    CareerSkillConfirmationModel,
    CareerSkillModel,
    EvidenceEntityLinkModel,
    EvidenceItemModel,
    EvidenceRevisionModel,
    EvidenceSkillLinkModel,
    EvidenceSourceModel,
    EvidenceStateTransitionModel,
)
from careeros.modules.change_studio.infrastructure.models import (
    ChangeClaimModel,
    ChangeOperationModel,
    ChangeSetModel,
    ChangeSetVersionModel,
)
from careeros.modules.identity.infrastructure.models import (
    OnboardingProgressModel,
    UserModel,
    UserProfileModel,
)
from careeros.modules.interview_prep.infrastructure.models import StarStoryModel
from careeros.modules.job_match.infrastructure.models import (
    JobPostingModel,
    JobRequirementModel,
)
from careeros.modules.networking.infrastructure.models import (
    NetworkingConsentEventModel,
    NetworkingContactModel,
    NetworkingOrganizationModel,
)
from careeros.modules.resume_builder.domain import (
    ResumeBullet,
    ResumeEntityFact,
    ResumeEvidenceLinkBasis,
    ResumeEvidenceReference,
    ResumeLayout,
    ResumePartialDate,
    ResumePersonalFact,
    ResumeSection,
    ResumeTemplate,
    ResumeVersion,
    build_fidelity_manifest,
    fidelity_manifest_payload,
    fidelity_manifest_sha256,
)
from careeros.modules.resume_builder.infrastructure.models import (
    ResumeExportModel,
    ResumeModel,
    ResumeVerificationReportModel,
    ResumeVersionModel,
)
from careeros.modules.resume_builder.infrastructure.renderers import (
    RENDERER_VERSION,
    DeterministicResumeRenderer,
)
from careeros.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    CanonicalSemantics,
    SectionKind,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SemanticSourceAnchor,
    SourceSpan,
)
from careeros.modules.resume_health.domain.scoring import ResumeHealthFeatures, score_resume_health
from careeros.modules.resume_health.infrastructure.models import (
    CanonicalResumeSnapshotModel,
    ResumeHealthAnalysisModel,
    ResumeHealthComponentModel,
    ResumeHealthFeatureContributionModel,
    ResumeHealthFindingModel,
    ResumeProcessingJobModel,
    ResumeUploadModel,
    SourceDocumentModel,
)
from careeros.modules.role_readiness.infrastructure.models import SavedRoleModel

FIXTURE_CREATED_AT = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
FIXTURE_EMAIL = "alex.morgan@example.invalid"
FIXTURE_PASSWORD = "Fictional-Local-Only-2026!"  # noqa: S105 - public local fixture
EXPECTED_MIGRATION_HEAD = "20260726_0014"
PRODUCT_MANAGER_ROLE_ID = UUID("00000000-0000-4000-8000-000000000411")
PRODUCT_MANAGER_ROLE_SLUG = "product-manager"
PRODUCT_MANAGER_TAXONOMY_VERSION = "careeros-seed-roles/2026-07-19"

_FIXTURE_NAMESPACE = uuid5(NAMESPACE_URL, "https://careeros.local/fictional-seed/v1")


def fixture_id(name: str) -> UUID:
    """Return a stable UUID reserved for this one explicitly fictional graph."""

    return uuid5(_FIXTURE_NAMESPACE, name)


@dataclass(frozen=True, slots=True)
class SeedObject:
    key: str
    content: bytes
    media_type: str
    sha256_digest: str


@dataclass(frozen=True, slots=True)
class SeedBatch:
    phase: int
    table: Any
    rows: tuple[dict[str, Any], ...]
    immutable: bool = False


@dataclass(frozen=True, slots=True)
class FictionalSeedManifest:
    user_id: UUID
    email: str
    batches: tuple[SeedBatch, ...]
    objects: tuple[SeedObject, ...]
    resume_version: ResumeVersion

    @property
    def phases(self) -> tuple[int, ...]:
        return tuple(sorted({batch.phase for batch in self.batches}))

    @property
    def expected_row_count(self) -> int:
        return sum(len(batch.rows) for batch in self.batches)


def build_fictional_seed_manifest(password_hash: str) -> FictionalSeedManifest:
    """Build the complete Phase 1-9 fixture without reading external state."""

    now = FIXTURE_CREATED_AT
    user_id = fixture_id("user")
    profile_id = fixture_id("career-profile")
    entity_id = fixture_id("career-entity-experience")
    skill_id = fixture_id("career-skill-product-discovery")
    personal_name_id = fixture_id("career-personal-name")
    personal_email_id = fixture_id("career-personal-email")
    personal_location_id = fixture_id("career-personal-location")
    evidence_id = fixture_id("evidence")
    evidence_revision_id = fixture_id("evidence-revision")
    evidence_source_id = fixture_id("evidence-source")
    evidence_transition_id = fixture_id("evidence-transition")
    source_statement = (
        "Coordinated fictional customer discovery and roadmap prioritization across "
        "product, design, and engineering for a synthetic local workflow."
    )
    evidence_statement_sha256 = _sha256_text(source_statement)

    upload_id = fixture_id("resume-upload")
    document_id = fixture_id("source-document")
    snapshot_id = fixture_id("canonical-snapshot")
    canonical_section_id = fixture_id("canonical-experience-section")
    canonical_block_id = fixture_id("canonical-achievement-block")
    canonical_semantic_entity_id = fixture_id("canonical-semantic-entity")
    canonical_semantic_field_id = fixture_id("canonical-semantic-field")
    analysis_job_id = fixture_id("resume-health-job")
    health_analysis_id = fixture_id("resume-health-analysis")

    source_plain_text = "\n".join(
        (
            "FICTIONAL LOCAL FIXTURE - NOT A REAL PERSON",
            "Alex Morgan (fictional local fixture)",
            FIXTURE_EMAIL,
            "Product Discovery Lead",
            "Example Labs (fictional)",
            source_statement,
            "Product discovery",
        )
    )
    source_pdf = _fictional_source_pdf(source_plain_text.splitlines())
    source_object_key = f"fictional-local-seed/{user_id.hex}/source/fictional-local-resume.pdf"
    source_object = SeedObject(
        key=source_object_key,
        content=source_pdf,
        media_type="application/pdf",
        sha256_digest=_sha256_bytes(source_pdf),
    )
    canonical_resume = _canonical_resume(
        section_id=canonical_section_id,
        block_id=canonical_block_id,
        semantic_entity_id=canonical_semantic_entity_id,
        semantic_field_id=canonical_semantic_field_id,
        statement=source_statement,
    )
    features = ResumeHealthFeatures(
        text_characters=len(source_plain_text),
        page_count=1,
        image_only=False,
        section_count=3,
        recognized_section_count=3,
        block_count=7,
        concise_block_count=7,
        bullet_count=1,
        action_bullet_count=1,
        outcome_bullet_count=0,
        duplicate_block_count=0,
        chronology_signal_count=0,
        warning_count=0,
        reading_order_violation_count=0,
        average_confidence_basis_points=9_500,
        semantic_entity_count=1,
        semantic_field_count=1,
        parsed_semantic_field_count=1,
        source_anchored_field_count=1,
        reviewed_semantic_field_count=1,
        date_field_count=0,
        precise_date_field_count=0,
    )
    health_score = score_resume_health(features)

    saved_role_id = fixture_id("saved-role")
    job_id = fixture_id("job")
    first_requirement_id = fixture_id("job-requirement-discovery")
    second_requirement_id = fixture_id("job-requirement-collaboration")
    job_source_text = "\n".join(
        (
            "FICTIONAL LOCAL JOB - NOT A REAL OPENING",
            "Senior Product Manager",
            "Example Company (fictional)",
            "Lead customer discovery and roadmap prioritization.",
            "Collaborate across product, design, and engineering.",
        )
    )
    first_requirement_text = "Lead customer discovery and roadmap prioritization."
    second_requirement_text = "Collaborate across product, design, and engineering."
    job_source_sha256 = _sha256_text(job_source_text)

    change_set_id = fixture_id("change-set")
    change_operation_id = fixture_id("change-operation")
    change_claim_id = fixture_id("change-claim")
    change_version_id = fixture_id("change-version")
    tailored_statement = (
        "Coordinated fictional customer discovery and roadmap prioritization with "
        "product, design, and engineering partners."
    )
    tailored_claim_sha256 = _sha256_text(tailored_statement)

    resume_id = fixture_id("resume")
    resume_version_id = fixture_id("resume-version")
    resume_section_id = fixture_id("resume-experience-section")
    resume_bullet_id = fixture_id("resume-bullet")
    resume_version = ResumeVersion(
        id=resume_version_id,
        owner_user_id=user_id,
        resume_id=resume_id,
        version_number=1,
        parent_version_id=None,
        title="Fictional Product Resume",
        target_role="Senior Product Manager (fictional)",
        template=ResumeTemplate.STANDARD_PROFESSIONAL,
        sections=(
            ResumeSection(
                id=resume_section_id,
                title="Experience",
                kind="experience",
                items=(
                    ResumeBullet(
                        id=resume_bullet_id,
                        text=tailored_statement,
                        evidence_ids=(evidence_id,),
                        source="change_studio",
                        evidence_references=(
                            ResumeEvidenceReference(
                                evidence_id=evidence_id,
                                evidence_revision_id=evidence_revision_id,
                                revision_number=1,
                                statement_sha256=evidence_statement_sha256,
                                claim_sha256=tailored_claim_sha256,
                                link_basis=ResumeEvidenceLinkBasis.CHANGE_STUDIO_CLAIM,
                            ),
                        ),
                        entity_id=entity_id,
                    ),
                ),
            ),
        ),
        plain_text="",
        source_evidence_ids=(evidence_id,),
        source_change_set_id=change_set_id,
        source_change_set_version_id=change_version_id,
        created_at=now,
        personal_facts=(
            ResumePersonalFact(
                id=personal_name_id,
                kind="name",
                value="Alex Morgan (fictional local fixture)",
                label=None,
                is_primary=True,
            ),
            ResumePersonalFact(
                id=personal_email_id,
                kind="email",
                value=FIXTURE_EMAIL,
                label=None,
                is_primary=True,
            ),
            ResumePersonalFact(
                id=personal_location_id,
                kind="location",
                value="Example City (fictional)",
                label=None,
                is_primary=True,
            ),
        ),
        entities=(
            ResumeEntityFact(
                id=entity_id,
                kind="experience",
                title="Product Discovery Lead",
                organization="Example Labs (fictional)",
                official_title="Product Discovery Lead",
                display_title="Product Discovery Lead",
                location="Example City (fictional)",
                start_date=ResumePartialDate(2024, 1),
                end_date=None,
                is_current=True,
                evidence_ids=(evidence_id,),
            ),
        ),
        layout=ResumeLayout(),
    )
    rendered = DeterministicResumeRenderer().render(resume_version, fmt="text")
    resume_version = _with_plain_text(resume_version, rendered.content.decode("utf-8").strip())
    fidelity_manifest = build_fidelity_manifest(resume_version)
    fidelity_payload = fidelity_manifest_payload(fidelity_manifest)
    fidelity_sha256 = fidelity_manifest_sha256(fidelity_manifest)
    export_content_sha256 = _sha256_bytes(rendered.content)
    export_id = fixture_id("resume-export")
    verification_report_id = fixture_id("resume-export-verification")
    export_object_key = (
        f"resume-exports/{user_id.hex}/{resume_version_id.hex}/{export_id.hex}/"
        "attempt-1/resume.text"
    )
    export_object = SeedObject(
        key=export_object_key,
        content=rendered.content,
        media_type=rendered.media_type,
        sha256_digest=export_content_sha256,
    )

    application_id = fixture_id("application")
    evidence_pin = {
        "evidenceId": str(evidence_id),
        "evidenceRevisionId": str(evidence_revision_id),
        "revisionNumber": 1,
        "statement": source_statement,
        "statementSha256": evidence_statement_sha256,
        "strength": "confirmed",
        "hasNumericClaim": False,
    }
    application_claim = {
        "id": str(resume_bullet_id),
        "text": tailored_statement,
        "evidenceLinks": [
            {
                "evidenceId": str(evidence_id),
                "evidenceRevisionId": str(evidence_revision_id),
            }
        ],
        "requirementIds": [str(first_requirement_id), str(second_requirement_id)],
    }

    networking_organization_id = fixture_id("networking-organization")
    networking_contact_id = fixture_id("networking-contact")
    career_goal_id = fixture_id("career-goal")
    analytics_job_id = fixture_id("analytics-job")
    analytics_snapshot_id = fixture_id("analytics-snapshot")
    analytics_payload = _analytics_payload(
        resume_version_id=resume_version_id,
        resume_version_number=resume_version.version_number,
    )
    analytics_payload_json = analytics_payload.as_dict()
    analytics_payload_sha256 = _canonical_json_sha256(analytics_payload_json)
    analytics_watermark = {
        "applications": {
            "recordCount": 1,
            "maxUpdatedAt": now.isoformat(),
            "versionSum": 1,
        },
        "careerRecord": {
            "recordCount": 1,
            "maxRevisionCreatedAt": now.isoformat(),
            "versionSum": 1,
        },
        "roleReadiness": {
            "recordCount": 0,
            "maxCreatedAt": None,
        },
    }

    batches = (
        SeedBatch(
            phase=1,
            table=UserModel.__table__,
            rows=(
                {
                    "id": user_id,
                    "email_normalized": FIXTURE_EMAIL,
                    "password_hash": password_hash,
                    "status": "active",
                    "email_verified_at": now,
                    "auth_version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=1,
            table=UserProfileModel.__table__,
            rows=(
                {
                    "user_id": user_id,
                    "display_name": "Alex Morgan (fictional local fixture)",
                    "locale": "en",
                    "timezone": "UTC",
                    "target_role": "Senior Product Manager (fictional)",
                    "preferred_location": "Example City (fictional)",
                    "work_model": "hybrid",
                    "seniority": "senior",
                    "industry": "Technology (fictional)",
                    "language": "en",
                    "writing_style": "balanced",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=1,
            table=OnboardingProgressModel.__table__,
            rows=(
                {
                    "user_id": user_id,
                    "status": "completed",
                    "current_step": "complete",
                    "resume_handoff": "skipped",
                    "parsed_review_handoff": "skipped",
                    "skipped_steps": [],
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=2,
            table=ResumeUploadModel.__table__,
            rows=(
                {
                    "id": upload_id,
                    "owner_user_id": user_id,
                    "guest_session_id": None,
                    "display_filename": "fictional-local-resume.pdf",
                    "expected_media_type": "application/pdf",
                    "expected_size": len(source_pdf),
                    "staging_object_key": (
                        f"fictional-local-seed/{user_id.hex}/staging/finalized-upload.pdf"
                    ),
                    "status": "finalized",
                    "created_at": now,
                    "expires_at": now + timedelta(minutes=15),
                    "staging_cleaned_at": now,
                    "finalized_document_id": document_id,
                    "safe_error_code": None,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=SourceDocumentModel.__table__,
            rows=(
                {
                    "id": document_id,
                    "upload_id": upload_id,
                    "owner_user_id": user_id,
                    "guest_session_id": None,
                    "display_filename": "fictional-local-resume.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": len(source_pdf),
                    "quarantine_object_key": source_object_key,
                    "status": "ready",
                    "malware_status": "clean",
                    "content_sha256": bytes.fromhex(source_object.sha256_digest),
                    "page_count": 1,
                    "safe_error_code": None,
                    "retention_expires_at": None,
                    "deleted_at": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=CanonicalResumeSnapshotModel.__table__,
            rows=(
                {
                    "id": snapshot_id,
                    "document_id": document_id,
                    "owner_user_id": user_id,
                    "guest_session_id": None,
                    "revision": 1,
                    "canonical_json": canonical_resume.to_dict(),
                    "plain_text_sha256": hashlib.sha256(source_plain_text.encode()).digest(),
                    "parser_version": "fictional-local-parser/1",
                    "based_on_snapshot_id": None,
                    "corrected_by_user": False,
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=ResumeProcessingJobModel.__table__,
            rows=(
                {
                    "id": analysis_job_id,
                    "document_id": document_id,
                    "owner_user_id": user_id,
                    "guest_session_id": None,
                    "kind": "analyze",
                    "idempotency_key": "fictional-local-resume-health-v1",
                    "request_hash": hashlib.sha256(b"fictional-local-analysis-v1").digest(),
                    "trace_id": "fictional-local-analysis",
                    "status": "succeeded",
                    "stage": "complete",
                    "progress": 100,
                    "attempts": 1,
                    "max_attempts": 3,
                    "started_at": now,
                    "completed_at": now,
                    "cancellation_requested_at": None,
                    "safe_error_code": None,
                    "retryable": False,
                    "dead_lettered_at": None,
                    "result_id": health_analysis_id,
                    "input_snapshot_id": snapshot_id,
                    "execution_token_hash": None,
                    "lease_expires_at": None,
                    "recovery_attempts": 0,
                    "max_recovery_attempts": 3,
                    "next_recovery_at": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=ResumeHealthAnalysisModel.__table__,
            rows=(
                {
                    "id": health_analysis_id,
                    "job_id": analysis_job_id,
                    "document_id": document_id,
                    "snapshot_id": snapshot_id,
                    "owner_user_id": user_id,
                    "guest_session_id": None,
                    "status": "succeeded",
                    "engine_version": health_score.engine_version,
                    "configuration_version": health_score.configuration_version,
                    "feature_schema_version": health_score.feature_schema_version,
                    "feature_values": health_score.feature_values,
                    "feature_set_hash": health_score.feature_set_hash,
                    "raw_score_basis_points": health_score.raw_score_basis_points,
                    "display_score": health_score.display_score,
                    "computed_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=ResumeHealthComponentModel.__table__,
            rows=tuple(
                {
                    "id": fixture_id(f"resume-health-component-{component.code}"),
                    "analysis_id": health_analysis_id,
                    "code": component.code,
                    "weight_basis_points": component.weight_basis_points,
                    "score_basis_points": component.score_basis_points,
                    "contribution_basis_points": component.contribution_basis_points,
                    "explanation": component.explanation,
                }
                for component in health_score.components
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=ResumeHealthFeatureContributionModel.__table__,
            rows=tuple(
                {
                    "id": fixture_id(
                        "resume-health-feature-"
                        f"{contribution.component_code}-{contribution.feature_code}"
                    ),
                    "analysis_id": health_analysis_id,
                    "component_code": contribution.component_code,
                    "feature_code": contribution.feature_code,
                    "feature_value_basis_points": contribution.feature_value_basis_points,
                    "weight_basis_points": contribution.weight_basis_points,
                    "contribution_basis_points": contribution.contribution_basis_points,
                }
                for contribution in health_score.feature_contributions
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=2,
            table=ResumeHealthFindingModel.__table__,
            rows=tuple(
                {
                    "id": fixture_id(f"resume-health-finding-{finding.code}"),
                    "analysis_id": health_analysis_id,
                    "code": finding.code,
                    "severity": finding.severity,
                    "component_code": finding.component_code,
                    "message": finding.message,
                    "quick_win": finding.quick_win,
                    "sort_order": index,
                }
                for index, finding in enumerate(health_score.findings)
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=3,
            table=CareerProfileModel.__table__,
            rows=(
                {
                    "id": profile_id,
                    "owner_user_id": user_id,
                    "professional_headline": "Fictional product discovery lead",
                    "summary": (
                        "Explicitly fictional local data for exercising CareerOS workflows."
                    ),
                    "work_authorization": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=3,
            table=CareerEntityModel.__table__,
            rows=(
                {
                    "id": entity_id,
                    "owner_user_id": user_id,
                    "profile_id": profile_id,
                    "kind": "experience",
                    "title": "Product Discovery Lead",
                    "organization": "Example Labs (fictional)",
                    "description": (
                        "Synthetic experience record; not a claim about a real person."
                    ),
                    "official_title": "Product Discovery Lead",
                    "display_title": "Product Discovery Lead",
                    "employment_type": "full_time",
                    "location": "Example City (fictional)",
                    "external_url": None,
                    "start_year": 2024,
                    "start_month": 1,
                    "end_year": None,
                    "end_month": None,
                    "is_current": True,
                    "sort_order": 0,
                    "group_id": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=3,
            table=CareerEntityConfirmationModel.__table__,
            rows=(
                {
                    "entity_id": entity_id,
                    "owner_user_id": user_id,
                    "state": "confirmed",
                    "version": 1,
                    "updated_at": now,
                    "confirmed_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=3,
            table=CareerSkillModel.__table__,
            rows=(
                {
                    "id": skill_id,
                    "owner_user_id": user_id,
                    "profile_id": profile_id,
                    "name": "Product discovery",
                    "name_normalized": "product discovery",
                    "category": "Product",
                    "proficiency": "advanced",
                    "sort_order": 0,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=3,
            table=CareerSkillConfirmationModel.__table__,
            rows=(
                {
                    "skill_id": skill_id,
                    "owner_user_id": user_id,
                    "state": "confirmed",
                    "version": 1,
                    "updated_at": now,
                    "confirmed_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=3,
            table=CareerPersonalFactModel.__table__,
            rows=(
                _personal_fact_row(
                    personal_name_id,
                    user_id,
                    profile_id,
                    "name",
                    "Alex Morgan (fictional local fixture)",
                    now,
                ),
                _personal_fact_row(
                    personal_email_id,
                    user_id,
                    profile_id,
                    "email",
                    FIXTURE_EMAIL,
                    now,
                ),
                _personal_fact_row(
                    personal_location_id,
                    user_id,
                    profile_id,
                    "location",
                    "Example City (fictional)",
                    now,
                ),
            ),
        ),
        SeedBatch(
            phase=3,
            table=EvidenceItemModel.__table__,
            rows=(
                {
                    "id": evidence_id,
                    "owner_user_id": user_id,
                    "lifecycle": "active",
                    "current_revision": 1,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "archived_at": None,
                    "deleted_at": None,
                },
            ),
        ),
        SeedBatch(
            phase=3,
            table=EvidenceRevisionModel.__table__,
            rows=(
                {
                    "id": evidence_revision_id,
                    "owner_user_id": user_id,
                    "evidence_id": evidence_id,
                    "revision": 1,
                    "evidence_type": "achievement",
                    "title": "Fictional product discovery coordination",
                    "statement": source_statement,
                    "context": "Synthetic local seed data only",
                    "organization": "Example Labs (fictional)",
                    "project": "Fictional product workflow",
                    "start_year": 2024,
                    "start_month": 1,
                    "end_year": None,
                    "end_month": None,
                    "strength": "confirmed",
                    "input_kind": "exact_source_span",
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=3,
            table=EvidenceStateTransitionModel.__table__,
            rows=(
                {
                    "id": evidence_transition_id,
                    "owner_user_id": user_id,
                    "evidence_id": evidence_id,
                    "from_revision_id": None,
                    "to_revision_id": evidence_revision_id,
                    "previous_strength": None,
                    "next_strength": "confirmed",
                    "authority": "owner_confirmation",
                    "reason_code": "fictional_local_seed_owner_confirmation",
                    "actor_user_id": user_id,
                    "verifier_reference": None,
                    "request_id": "fictional-local-seed-v1",
                    "trace_id": "fictional-local-seed-v1",
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=3,
            table=EvidenceSourceModel.__table__,
            rows=(
                {
                    "id": evidence_source_id,
                    "owner_user_id": user_id,
                    "evidence_revision_id": evidence_revision_id,
                    "kind": "resume",
                    "label": "Fictional reviewed resume source",
                    "attachment_id": None,
                    "external_url": None,
                    "available": True,
                    "exact_span_validated": True,
                    "document_id": document_id,
                    "snapshot_id": snapshot_id,
                    "snapshot_revision": 1,
                    "schema_version": "canonical-resume/2.0.0",
                    "parser_version": "fictional-local-parser/1",
                    "block_id": canonical_block_id,
                    "page": 1,
                    "start_offset": 0,
                    "end_offset": len(source_statement),
                    "source_sha256": hashlib.sha256(source_statement.encode()).digest(),
                    "review_excerpt": source_statement,
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=3,
            table=EvidenceEntityLinkModel.__table__,
            rows=(
                {
                    "id": fixture_id("evidence-entity-link"),
                    "owner_user_id": user_id,
                    "evidence_id": evidence_id,
                    "entity_id": entity_id,
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=3,
            table=EvidenceSkillLinkModel.__table__,
            rows=(
                {
                    "id": fixture_id("evidence-skill-link"),
                    "owner_user_id": user_id,
                    "evidence_id": evidence_id,
                    "skill_id": skill_id,
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=4,
            table=SavedRoleModel.__table__,
            rows=(
                {
                    "id": saved_role_id,
                    "owner_user_id": user_id,
                    "role_id": PRODUCT_MANAGER_ROLE_ID,
                    "notes": "Explicitly fictional local role exploration.",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=5,
            table=JobPostingModel.__table__,
            rows=(
                {
                    "id": job_id,
                    "owner_user_id": user_id,
                    "title": "Senior Product Manager (fictional)",
                    "company": "Example Company (fictional)",
                    "location": "Example City (fictional)",
                    "work_model": "hybrid",
                    "employment_type": "full_time",
                    "compensation": None,
                    "application_deadline": None,
                    "source_kind": "paste",
                    "source_url": None,
                    "source_text": job_source_text,
                    "source_sha256": bytes.fromhex(job_source_sha256),
                    "idempotency_key": "fictional-local-job-v1",
                    "idempotency_fingerprint": _sha256_text("fictional-local-job-v1"),
                    "target_role_id": PRODUCT_MANAGER_ROLE_ID,
                    "target_role_title": "Product Manager",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=5,
            table=JobRequirementModel.__table__,
            rows=(
                _requirement_row(
                    first_requirement_id,
                    user_id,
                    job_id,
                    first_requirement_text,
                    job_source_text,
                    0,
                ),
                _requirement_row(
                    second_requirement_id,
                    user_id,
                    job_id,
                    second_requirement_text,
                    job_source_text,
                    1,
                ),
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=6,
            table=ChangeSetModel.__table__,
            rows=(
                {
                    "id": change_set_id,
                    "owner_user_id": user_id,
                    "purpose": "job_tailoring",
                    "target_kind": "tailored_resume_bullet",
                    "status": "applied",
                    "job_id": job_id,
                    "analysis_id": None,
                    "current_version_id": change_version_id,
                    "provider_name": "deterministic-local",
                    "provider_model": "fictional-seed-v1",
                    "prompt_version": "fictional-seed-prompt/1",
                    "policy_version": "career-grounding/1",
                    "schema_version": "change-studio/1",
                    "grounding_version": "exact-evidence-revision/1",
                    "idempotency_key": "fictional-local-change-set-v1",
                    "idempotency_fingerprint": _sha256_text("fictional-local-change-set-v1"),
                    "version": 2,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=6,
            table=ChangeOperationModel.__table__,
            rows=(
                {
                    "id": change_operation_id,
                    "owner_user_id": user_id,
                    "change_set_id": change_set_id,
                    "operation_type": "replace_bullet",
                    "target_kind": "tailored_resume_bullet",
                    "target_id": evidence_id,
                    "before_text": source_statement,
                    "after_text": tailored_statement,
                    "reason": ("Align the fictional wording to the saved fictional requirement."),
                    "status": "accepted",
                    "risk": "low",
                    "confidence_basis_points": 9_000,
                    "requires_confirmation": True,
                    "grounding_status": "grounded",
                    "grounding_codes": ["exact_evidence_revision"],
                    "expected_score_delta_basis_points": None,
                    "requirement_id": first_requirement_id,
                    "requirement_text": first_requirement_text,
                    "locked": False,
                    "sort_order": 0,
                    "version": 2,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=6,
            table=ChangeClaimModel.__table__,
            rows=(
                {
                    "id": change_claim_id,
                    "owner_user_id": user_id,
                    "change_set_id": change_set_id,
                    "operation_id": change_operation_id,
                    "claim_kind": "achievement",
                    "text": tailored_statement,
                    "evidence_id": evidence_id,
                    "evidence_revision_id": evidence_revision_id,
                    "evidence_revision_number": 1,
                    "evidence_statement_sha256": evidence_statement_sha256,
                    "evidence_title": "Fictional product discovery coordination",
                    "evidence_strength": "confirmed",
                    "source_excerpt": source_statement,
                    "validation_status": "passed",
                    "validation_codes": ["exact_evidence_revision"],
                    "sort_order": 0,
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=6,
            table=ChangeSetVersionModel.__table__,
            rows=(
                {
                    "id": change_version_id,
                    "owner_user_id": user_id,
                    "change_set_id": change_set_id,
                    "version_number": 1,
                    "parent_version_id": None,
                    "created_by_operation_id": change_operation_id,
                    "title": "Accepted fictional tailoring",
                    "content": tailored_statement,
                    "operation_ids": [str(change_operation_id)],
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=7,
            table=ResumeModel.__table__,
            rows=(
                {
                    "id": resume_id,
                    "owner_user_id": user_id,
                    "title": resume_version.title,
                    "target_role": resume_version.target_role,
                    "template": resume_version.template.value,
                    "layout": _layout_payload(resume_version),
                    "current_version_id": resume_version_id,
                    "source_change_set_id": change_set_id,
                    "source_change_set_version_id": change_version_id,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=7,
            table=ResumeVersionModel.__table__,
            rows=(_resume_version_row(resume_version),),
            immutable=True,
        ),
        SeedBatch(
            phase=7,
            table=ResumeExportModel.__table__,
            rows=(
                {
                    "id": export_id,
                    "owner_user_id": user_id,
                    "resume_id": resume_id,
                    "version_id": resume_version_id,
                    "format": "text",
                    "status": "verified",
                    "object_key": export_object_key,
                    "media_type": rendered.media_type,
                    "size_bytes": len(rendered.content),
                    "sha256_digest": export_content_sha256,
                    "version_content_sha256": fidelity_manifest.version_content_sha256,
                    "fidelity_manifest": fidelity_payload,
                    "fidelity_manifest_sha256": fidelity_sha256,
                    "verification_status": "passed",
                    "verification_codes": [
                        "manifest_version_pinned",
                        "all_claims_grounded",
                        "numeric_claims_grounded",
                        "exact_occurrences_verified",
                        "reading_order_verified",
                        "page_limit_verified",
                        "searchable_output",
                    ],
                    "critical_failures": [],
                    "warnings": [],
                    "renderer_version": RENDERER_VERSION,
                    "parser_version": "structured-export-verifier-v1",
                    "idempotency_key": "fictional-local-resume-export-v1",
                    "idempotency_fingerprint": _sha256_text("fictional-local-resume-export-v1"),
                    "trace_id": "fictional-local-resume-export-v1",
                    "attempts": 1,
                    "max_attempts": 3,
                    "cleanup_attempts": 0,
                    "cleanup_max_attempts": 3,
                    "fence": 1,
                    "execution_token_hash": None,
                    "lease_expires_at": None,
                    "retry_at": None,
                    "dead_lettered_at": None,
                    "requested_at": now,
                    "completed_at": now,
                    "deleted_at": None,
                    "last_error": None,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=7,
            table=ResumeVerificationReportModel.__table__,
            rows=(
                {
                    "id": verification_report_id,
                    "owner_user_id": user_id,
                    "export_id": export_id,
                    "version_id": resume_version_id,
                    "status": "passed",
                    "critical_failures": [],
                    "warnings": [],
                    "detected_lines": [entry.text for entry in fidelity_manifest.entries],
                    "missing_lines": [],
                    "duplicate_lines": [],
                    "reading_order": list(rendered.reading_order),
                    "grounding_codes": [
                        "manifest_version_pinned",
                        "all_claims_grounded",
                        "numeric_claims_grounded",
                        "exact_occurrences_verified",
                        "reading_order_verified",
                        "page_limit_verified",
                        "searchable_output",
                    ],
                    "file_sha256": export_content_sha256,
                    "parser_version": "structured-export-verifier-v1",
                    "occurrence_mismatches": [],
                    "reading_order_failures": [],
                    "manifest_sha256": fidelity_sha256,
                    "version_content_sha256": fidelity_manifest.version_content_sha256,
                    "page_count": rendered.page_count,
                    "created_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=8,
            table=ApplicationRecordModel.__table__,
            rows=(
                {
                    "id": application_id,
                    "owner_user_id": user_id,
                    "job_id": job_id,
                    "job_version": 1,
                    "job_title": "Senior Product Manager (fictional)",
                    "company": "Example Company (fictional)",
                    "location": "Example City (fictional)",
                    "job_analysis_id": None,
                    "job_source_sha256": job_source_sha256,
                    "job_requirements": [
                        _application_requirement(
                            first_requirement_id,
                            first_requirement_text,
                            job_source_text,
                        ),
                        _application_requirement(
                            second_requirement_id,
                            second_requirement_text,
                            job_source_text,
                        ),
                    ],
                    "requirement_support": [],
                    "resume_id": resume_id,
                    "resume_version_id": resume_version_id,
                    "resume_version_number": 1,
                    "resume_title": resume_version.title,
                    "resume_evidence_ids": [str(evidence_id)],
                    "evidence_pins": [evidence_pin],
                    "resume_claims": [application_claim],
                    "source": "Fictional local seed",
                    "industry": "Technology (fictional)",
                    "stage": "preparing",
                    "application_deadline": None,
                    "follow_up_at": None,
                    "contacts": [],
                    "referral_status": "none",
                    "outcome_status": "none",
                    "rejection_reason": None,
                    "offer_summary": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=9,
            table=StarStoryModel.__table__,
            rows=(
                {
                    "id": fixture_id("interview-story"),
                    "owner_user_id": user_id,
                    "application_id": application_id,
                    "title": "Fictional discovery alignment draft",
                    "situation": (
                        "A synthetic product team needed a shared view of a fictional problem."
                    ),
                    "task": (
                        "The fixture character needed to organize discovery and prioritization."
                    ),
                    "action": (
                        "They documented fictional inputs and coordinated an example review."
                    ),
                    "result": ("The synthetic team had a clearer fictional planning artifact."),
                    "personal_contribution": (
                        "This is draft fixture text and is not a claim about a real person."
                    ),
                    "metric_explanation": None,
                    "confidence": 3,
                    "follow_up_questions": [
                        "Which parts of this fictional story would need real evidence?"
                    ],
                    "status": "draft",
                    "origin": "user_authored",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=9,
            table=NetworkingOrganizationModel.__table__,
            rows=(
                {
                    "id": networking_organization_id,
                    "owner_user_id": user_id,
                    "name": "Example Network (fictional)",
                    "website": "https://example.invalid",
                    "industry": "Technology (fictional)",
                    "location": "Example City (fictional)",
                    "tags": ["fictional-local-seed"],
                    "normalized_search": (
                        "example network fictional technology example city fictional"
                    ),
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "deleted_at": None,
                },
            ),
        ),
        SeedBatch(
            phase=9,
            table=NetworkingContactModel.__table__,
            rows=(
                {
                    "id": networking_contact_id,
                    "owner_user_id": user_id,
                    "organization_id": networking_organization_id,
                    "name": "Jordan Lee (fictional)",
                    "role": "Example contact",
                    "email": "jordan.lee@example.invalid",
                    "phone": None,
                    "profile_url": None,
                    "location": "Example City (fictional)",
                    "relationship_stage": "new",
                    "referral_state": "none",
                    "tags": ["fictional-local-seed"],
                    "normalized_search": (
                        "jordan lee fictional example contact example city fictional"
                    ),
                    "last_contact_at": None,
                    "next_contact_at": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "deleted_at": None,
                },
            ),
        ),
        SeedBatch(
            phase=9,
            table=NetworkingConsentEventModel.__table__,
            rows=(
                _networking_consent_row(
                    fixture_id("networking-consent-collection"),
                    user_id,
                    networking_contact_id,
                    "collection",
                    1,
                    now,
                ),
                _networking_consent_row(
                    fixture_id("networking-consent-storage"),
                    user_id,
                    networking_contact_id,
                    "storage",
                    2,
                    now,
                ),
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=9,
            table=CareerGoalModel.__table__,
            rows=(
                {
                    "id": career_goal_id,
                    "owner_user_id": user_id,
                    "title": "Review fictional product leadership evidence",
                    "description": (
                        "Synthetic local goal; replace it with a real, evidenced goal."
                    ),
                    "status": "active",
                    "target_date": date(2026, 12, 31),
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        ),
        SeedBatch(
            phase=9,
            table=AnalyticsRefreshJobModel.__table__,
            rows=(
                {
                    "id": analytics_job_id,
                    "owner_user_id": user_id,
                    "scope": "overview",
                    "window_start": date(2026, 1, 1),
                    "window_end": date(2026, 12, 31),
                    "timezone": "UTC",
                    "idempotency_key": "fictional-local-analytics-v1",
                    "request_fingerprint": _sha256_text("fictional-local-analytics-overview-2026"),
                    "status": "completed",
                    "attempts": 1,
                    "max_attempts": 3,
                    "trace_id": _sha256_text("fictional-local-analytics-trace")[:32],
                    "source_watermark_before": {},
                    "source_watermark_after": analytics_watermark,
                    "lease_token": None,
                    "leased_until": None,
                    "next_attempt_at": now,
                    "safe_error_code": None,
                    "version": 2,
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": now,
                },
            ),
            immutable=True,
        ),
        SeedBatch(
            phase=9,
            table=AnalyticsSnapshotModel.__table__,
            rows=(
                {
                    "id": analytics_snapshot_id,
                    "owner_user_id": user_id,
                    "job_id": analytics_job_id,
                    "scope": "overview",
                    "metric_definition_version": METRIC_DEFINITION_VERSION,
                    "window_start": date(2026, 1, 1),
                    "window_end": date(2026, 12, 31),
                    "timezone": "UTC",
                    "source_watermark": analytics_watermark,
                    "payload": analytics_payload_json,
                    "payload_sha256": analytics_payload_sha256,
                    "status": "ready",
                    "created_at": now,
                    "stale_at": None,
                },
            ),
            immutable=True,
        ),
    )
    return FictionalSeedManifest(
        user_id=user_id,
        email=FIXTURE_EMAIL,
        batches=tuple(batch for batch in batches if batch.rows),
        objects=(source_object, export_object),
        resume_version=resume_version,
    )


def _canonical_resume(
    *,
    section_id: UUID,
    block_id: UUID,
    semantic_entity_id: UUID,
    semantic_field_id: UUID,
    statement: str,
) -> CanonicalResume:
    block = CanonicalBlock(
        id=block_id,
        kind=BlockKind.BULLET,
        text=statement,
        confidence_basis_points=9_500,
        spans=(SourceSpan(page=1, start=0, end=len(statement)),),
    )
    section = CanonicalSection(
        id=section_id,
        kind=SectionKind.EXPERIENCE,
        title="Experience",
        confidence_basis_points=9_500,
        blocks=(block,),
    )
    semantic_field = SemanticField(
        id=semantic_field_id,
        name="achievement",
        field_type=SemanticFieldType.BULLET,
        value=statement,
        confidence_basis_points=9_500,
        review_state=SemanticReviewState.CONFIRMED,
        anchors=(
            SemanticSourceAnchor(
                block_id=block_id,
                page=1,
                start=0,
                end=len(statement),
                source_sha256=_sha256_text(statement),
            ),
        ),
    )
    semantics = CanonicalSemantics(
        schema_version="canonical-semantics/1.0.0",
        parser_version="fictional-local-parser/1",
        entities=(
            SemanticEntity(
                id=semantic_entity_id,
                kind=SemanticEntityKind.EXPERIENCE,
                review_state=SemanticReviewState.CONFIRMED,
                fields=(semantic_field,),
                source_section_id=section_id,
            ),
        ),
        review_state=SemanticReviewState.CONFIRMED,
    )
    return CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=(section,),
        source_sections=(section,),
        semantics=semantics,
        warnings=(),
    )


def _with_plain_text(version: ResumeVersion, plain_text: str) -> ResumeVersion:
    return ResumeVersion(
        id=version.id,
        owner_user_id=version.owner_user_id,
        resume_id=version.resume_id,
        version_number=version.version_number,
        parent_version_id=version.parent_version_id,
        title=version.title,
        target_role=version.target_role,
        template=version.template,
        sections=version.sections,
        plain_text=plain_text,
        source_evidence_ids=version.source_evidence_ids,
        source_change_set_id=version.source_change_set_id,
        source_change_set_version_id=version.source_change_set_version_id,
        created_at=version.created_at,
        personal_facts=version.personal_facts,
        entities=version.entities,
        layout=version.layout,
    )


def _layout_payload(version: ResumeVersion) -> dict[str, object]:
    return {
        "fontFamily": version.layout.font_family.value,
        "fontSizePt": version.layout.font_size_pt,
        "lineSpacing": version.layout.line_spacing.value,
        "margins": version.layout.margins.value,
        "pageLimit": version.layout.page_limit,
        "pageSize": version.layout.page_size.value,
    }


def _resume_version_row(version: ResumeVersion) -> dict[str, object]:
    return {
        "id": version.id,
        "owner_user_id": version.owner_user_id,
        "resume_id": version.resume_id,
        "version_number": version.version_number,
        "parent_version_id": version.parent_version_id,
        "title": version.title,
        "target_role": version.target_role,
        "template": version.template.value,
        "layout": _layout_payload(version),
        "personal_facts": [
            {
                "id": str(fact.id),
                "kind": fact.kind,
                "value": fact.value,
                "label": fact.label,
                "isPrimary": fact.is_primary,
            }
            for fact in version.personal_facts
        ],
        "entities": [
            {
                "id": str(entity.id),
                "kind": entity.kind,
                "title": entity.title,
                "organization": entity.organization,
                "officialTitle": entity.official_title,
                "displayTitle": entity.display_title,
                "location": entity.location,
                "startDate": (
                    {"year": entity.start_date.year, "month": entity.start_date.month}
                    if entity.start_date is not None
                    else None
                ),
                "endDate": (
                    {"year": entity.end_date.year, "month": entity.end_date.month}
                    if entity.end_date is not None
                    else None
                ),
                "isCurrent": entity.is_current,
                "evidenceIds": [str(value) for value in entity.evidence_ids],
            }
            for entity in version.entities
        ],
        "sections": [
            {
                "id": str(section.id),
                "title": section.title,
                "kind": section.kind,
                "items": [
                    {
                        "id": str(item.id),
                        "text": item.text,
                        "evidenceIds": [str(value) for value in item.evidence_ids],
                        "source": item.source,
                        "entityId": str(item.entity_id) if item.entity_id is not None else None,
                        "evidenceReferences": [
                            {
                                "evidenceId": str(reference.evidence_id),
                                "evidenceRevisionId": str(reference.evidence_revision_id),
                                "revisionNumber": reference.revision_number,
                                "statementSha256": reference.statement_sha256,
                                "claimSha256": reference.claim_sha256,
                                "linkBasis": reference.link_basis.value,
                                "sourceSkillId": (
                                    str(reference.source_skill_id)
                                    if reference.source_skill_id is not None
                                    else None
                                ),
                            }
                            for reference in item.evidence_references
                        ],
                    }
                    for item in section.items
                ],
            }
            for section in version.sections
        ],
        "plain_text": version.plain_text,
        "source_evidence_ids": [str(value) for value in version.source_evidence_ids],
        "source_change_set_id": version.source_change_set_id,
        "source_change_set_version_id": version.source_change_set_version_id,
        "created_at": version.created_at,
    }


def _personal_fact_row(
    fact_id: UUID,
    owner_user_id: UUID,
    profile_id: UUID,
    kind: str,
    value: str,
    now: datetime,
) -> dict[str, object]:
    return {
        "id": fact_id,
        "owner_user_id": owner_user_id,
        "profile_id": profile_id,
        "kind": kind,
        "value": value,
        "value_sha256": hashlib.sha256(value.encode()).digest(),
        "label": None,
        "is_primary": True,
        "confirmation": "confirmed",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "confirmed_at": now,
    }


def _requirement_row(
    requirement_id: UUID,
    owner_user_id: UUID,
    job_id: UUID,
    text: str,
    source: str,
    sort_order: int,
) -> dict[str, object]:
    start = source.index(text)
    return {
        "id": requirement_id,
        "owner_user_id": owner_user_id,
        "job_id": job_id,
        "requirement_type": "responsibility",
        "text": text,
        "normalized_text": " ".join(text.casefold().split()),
        "importance": "mandatory",
        "source_start": start,
        "source_end": start + len(text),
        "confidence_basis_points": 10_000,
        "sort_order": sort_order,
    }


def _application_requirement(
    requirement_id: UUID,
    text: str,
    source: str,
) -> dict[str, object]:
    start = source.index(text)
    return {
        "id": str(requirement_id),
        "type": "responsibility",
        "importance": "mandatory",
        "text": text,
        "sourceStart": start,
        "sourceEnd": start + len(text),
    }


def _networking_consent_row(
    event_id: UUID,
    owner_user_id: UUID,
    contact_id: UUID,
    purpose: str,
    sequence: int,
    now: datetime,
) -> dict[str, object]:
    return {
        "id": event_id,
        "owner_user_id": owner_user_id,
        "contact_id": contact_id,
        "purpose": purpose,
        "action": "granted",
        "policy_version": "networking-contact-consent/1",
        "actor_user_id": owner_user_id,
        "sequence": sequence,
        "occurred_at": now,
    }


def _analytics_payload(
    *,
    resume_version_id: UUID,
    resume_version_number: int,
) -> AnalyticsPayload:
    suppressed = AnalyticsRate.calculate(0, 1)
    return AnalyticsPayload(
        scope=AnalyticsScope.OVERVIEW,
        counts={
            "achievements": 1,
            "applications": 1,
            "interviews": 0,
            "offers": 0,
            "responses": 0,
        },
        rates={
            "interviewRate": suppressed,
            "offerRate": suppressed,
            "responseRate": suppressed,
        },
        breakdowns={
            "applicationStages": (AnalyticsBreakdown(key="preparing", count=1),),
            "industries": (AnalyticsBreakdown(key="Technology (fictional)", count=1),),
            "roles": (
                AnalyticsBreakdown(
                    key="Senior Product Manager (fictional)",
                    count=1,
                ),
            ),
            "sources": (AnalyticsBreakdown(key="Fictional local seed", count=1),),
        },
        time_buckets=(
            AnalyticsTimeBucket(
                start=date(2026, 7, 1),
                end=date(2026, 7, 31),
                applications=1,
                interviews=0,
                offers=0,
                achievements=1,
            ),
        ),
        requirement_coverage_trend=(
            RequirementCoverageTrendPoint.calculate(
                start=date(2026, 7, 1),
                end=date(2026, 7, 31),
                values=(10_000,),
            ),
        ),
        outcomes_by_resume_version=(
            ResumeVersionOutcomePerformance(
                resume_version_id=resume_version_id,
                resume_version_number=resume_version_number,
                application_count=1,
                response_rate=suppressed,
                interview_rate=suppressed,
                offer_rate=suppressed,
            ),
        ),
        readiness_history=(),
    )


def _fictional_source_pdf(lines: list[str]) -> bytes:
    output = BytesIO()
    canvas = Canvas(
        output,
        pagesize=LETTER,
        pageCompression=1,
        invariant=1,
    )
    canvas.setTitle("CareerOS fictional local seed")
    canvas.setAuthor("CareerOS")
    canvas.setCreator("careeros-fictional-local-seed/1")
    canvas.setFont("Helvetica", 10)
    y = LETTER[1] - 72
    for line in lines:
        canvas.drawString(72, y, line)
        y -= 18
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
