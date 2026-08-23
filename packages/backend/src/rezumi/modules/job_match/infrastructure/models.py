"""SQLAlchemy mappings for Phase 5 Job Match and Opportunity Priority."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rezumi.foundation.database import Base

_SOURCE_KINDS = ("paste", "url", "manual", "greenhouse", "fake")
_WORK_MODELS = ("remote", "hybrid", "onsite", "unknown")
_EMPLOYMENT_TYPES = ("full_time", "part_time", "contract", "internship", "temporary", "unknown")
_REQUIREMENT_TYPES = (
    "responsibility",
    "skill",
    "experience",
    "seniority",
    "education",
    "certification",
    "domain",
    "work_authorization",
    "travel",
    "compensation",
    "other",
)
_IMPORTANCE = ("mandatory", "preferred", "helpful")
_MATCH_STATES = ("strong", "partial", "transferable", "unknown", "missing", "not_applicable")
_READINESS_LABELS = ("strong", "viable", "needs_work", "insufficient_data")
_PREFERENCE_FITS = ("strong", "acceptable", "unknown", "mismatch")
_TAILORING_EFFORTS = ("low", "medium", "high")
_PRIORITY_LABELS = ("high", "medium", "low", "defer")
_AUDIT_ACTIONS = (
    "job_imported",
    "job_created",
    "job_updated",
    "job_deleted",
    "job_analyzed",
    "opportunity_prioritized",
    "jobs_synced_from_source",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class JobPostingModel(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        CheckConstraint(f"source_kind IN ({_values(_SOURCE_KINDS)})", name="source_kind_valid"),
        CheckConstraint(f"work_model IN ({_values(_WORK_MODELS)})", name="work_model_valid"),
        CheckConstraint(
            f"employment_type IN ({_values(_EMPLOYMENT_TYPES)})",
            name="employment_type_valid",
        ),
        CheckConstraint("octet_length(source_sha256) = 32", name="source_hash_length"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", "id", name="uq_job_postings_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_job_postings_owner_idempotency",
        ),
        Index(
            "ix_job_postings_owner_source_external",
            "owner_user_id",
            "source_kind",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_job_postings_owner_updated", "owner_user_id", "updated_at", "id"),
        Index("ix_job_postings_owner_target_role", "owner_user_id", "target_role_id", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    work_model: Mapped[str] = mapped_column(String(16), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    compensation: Mapped[str | None] = mapped_column(String(200))
    application_deadline: Mapped[date | None] = mapped_column(Date)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(String(200))
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    target_role_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_role_title: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JobRequirementModel(Base):
    __tablename__ = "job_requirements"
    __table_args__ = (
        CheckConstraint(
            f"requirement_type IN ({_values(_REQUIREMENT_TYPES)})",
            name="requirement_type_valid",
        ),
        CheckConstraint(f"importance IN ({_values(_IMPORTANCE)})", name="importance_valid"),
        CheckConstraint(
            "source_start >= 0 AND source_end > source_start", name="source_span_valid"
        ),
        CheckConstraint(
            "confidence_basis_points BETWEEN 0 AND 10000",
            name="confidence_valid",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["job_postings.owner_user_id", "job_postings.id"],
            name="fk_job_requirements_owner_job",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_job_requirements_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "job_id",
            "normalized_text",
            name="uq_job_requirements_job_normalized",
        ),
        Index("ix_job_requirements_job_order", "owner_user_id", "job_id", "sort_order", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    importance: Mapped[str] = mapped_column(String(16), nullable=False)
    source_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_end: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class JobMatchAnalysisModel(Base):
    __tablename__ = "job_match_analyses"
    __table_args__ = (
        CheckConstraint(
            "raw_score_basis_points IS NULL OR raw_score_basis_points BETWEEN 0 AND 10000",
            name="raw_score_valid",
        ),
        CheckConstraint(
            "display_score IS NULL OR display_score BETWEEN 0 AND 100",
            name="display_score_valid",
        ),
        CheckConstraint(
            f"readiness_label IN ({_values(_READINESS_LABELS)})",
            name="readiness_label_valid",
        ),
        CheckConstraint("hard_gap_count >= 0", name="hard_gap_count_nonnegative"),
        CheckConstraint("octet_length(feature_set_hash) = 32", name="feature_hash_length"),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["job_postings.owner_user_id", "job_postings.id"],
            name="fk_job_match_analyses_owner_job",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_job_match_analyses_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_job_match_analyses_owner_idempotency",
        ),
        Index("ix_job_match_analyses_owner_job_created", "owner_user_id", "job_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(120), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_set_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    raw_score_basis_points: Mapped[int | None] = mapped_column(Integer)
    display_score: Mapped[int | None] = mapped_column(Integer)
    readiness_label: Mapped[str] = mapped_column(String(32), nullable=False)
    hard_gap_count: Mapped[int] = mapped_column(Integer, nullable=False)
    insufficient_reason: Mapped[str | None] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JobMatchComponentModel(Base):
    __tablename__ = "job_match_components"
    __table_args__ = (
        CheckConstraint("weight_basis_points BETWEEN 0 AND 10000", name="weight_valid"),
        CheckConstraint("score_basis_points BETWEEN 0 AND 10000", name="score_valid"),
        CheckConstraint(
            "contribution_basis_points BETWEEN 0 AND 10000",
            name="contribution_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_job_match_components_owner_analysis",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_job_match_components_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "dimension",
            name="uq_job_match_components_dimension",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dimension: Mapped[str] = mapped_column(String(80), nullable=False)
    weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementMatchModel(Base):
    __tablename__ = "requirement_matches"
    __table_args__ = (
        CheckConstraint(
            f"requirement_type IN ({_values(_REQUIREMENT_TYPES)})",
            name="requirement_type_valid",
        ),
        CheckConstraint(f"importance IN ({_values(_IMPORTANCE)})", name="importance_valid"),
        CheckConstraint(f"match_state IN ({_values(_MATCH_STATES)})", name="match_state_valid"),
        CheckConstraint("score_basis_points BETWEEN 0 AND 10000", name="score_valid"),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_requirement_matches_owner_analysis",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_requirement_matches_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "requirement_id",
            name="uq_requirement_matches_analysis_requirement",
        ),
        Index("ix_requirement_matches_analysis", "owner_user_id", "analysis_id", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    importance: Mapped[str] = mapped_column(String(16), nullable=False)
    match_state: Mapped[str] = mapped_column(String(32), nullable=False)
    score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    hard_gap: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RequirementEvidenceLinkModel(Base):
    __tablename__ = "requirement_evidence_links"
    __table_args__ = (
        CheckConstraint("relevance_basis_points BETWEEN 0 AND 10000", name="relevance_valid"),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_requirement_evidence_links_owner_analysis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "requirement_match_id"],
            ["requirement_matches.owner_user_id", "requirement_matches.id"],
            name="fk_requirement_evidence_links_owner_match",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_requirement_evidence_links_owner_id"),
        Index(
            "ix_requirement_evidence_links_match",
            "owner_user_id",
            "requirement_match_id",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requirement_match_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_title: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(40), nullable=False)
    relevance_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)


class OpportunityPriorityModel(Base):
    __tablename__ = "opportunity_priorities"
    __table_args__ = (
        CheckConstraint(
            f"priority_label IN ({_values(_PRIORITY_LABELS)})",
            name="priority_label_valid",
        ),
        CheckConstraint(
            "priority_score_basis_points BETWEEN 0 AND 10000",
            name="priority_score_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            ["job_postings.owner_user_id", "job_postings.id"],
            name="fk_opportunity_priorities_owner_job",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["job_match_analyses.owner_user_id", "job_match_analyses.id"],
            name="fk_opportunity_priorities_owner_analysis",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_opportunity_priorities_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_opportunity_priorities_owner_idempotency",
        ),
        Index(
            "ix_opportunity_priorities_owner_job_created",
            "owner_user_id",
            "job_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    priority_label: Mapped[str] = mapped_column(String(16), nullable=False)
    priority_score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reasons_for: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reconsiderations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    blockers: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RolePreferenceModel(Base):
    __tablename__ = "job_catalog_role_preferences"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", name="uq_job_catalog_role_preferences_owner"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_titles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JobMatchAuditEventModel(Base):
    __tablename__ = "job_match_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        Index("ix_job_match_audit_owner_created", "owner_user_id", "created_at", "id"),
        Index("ix_job_match_audit_target", "target_kind", "target_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
