"""SQLAlchemy mappings for Phase 4 Role Explorer and readiness snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

from careeros.foundation.database import Base

_SENIORITIES = ("entry", "mid", "senior", "lead", "executive")
_DIMENSIONS = (
    "core_competency",
    "responsibility_alignment",
    "seniority_alignment",
    "leadership_evidence",
    "domain_knowledge",
    "technical_skills",
    "business_impact",
    "education_certification",
    "evidence_strength",
)
_IMPORTANCE = ("required", "helpful")
_MATCH_STATES = ("demonstrated", "listed", "transferable", "adjacent", "missing", "unknown")
_READINESS_LABELS = ("strong", "developing", "needs_evidence", "insufficient_data")
_AUDIT_ACTIONS = (
    "saved_role_created",
    "saved_role_updated",
    "saved_role_deleted",
    "readiness_analyzed",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class RoleTaxonomyVersionModel(Base):
    __tablename__ = "role_taxonomy_versions"
    __table_args__ = (
        UniqueConstraint("version", name="uq_role_taxonomy_versions_version"),
        Index(
            "ix_role_taxonomy_versions_active_published",
            "active",
            "published_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_license: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RoleDefinitionModel(Base):
    __tablename__ = "role_definitions"
    __table_args__ = (
        CheckConstraint(f"seniority IN ({_values(_SENIORITIES)})", name="seniority_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["role_taxonomy_versions.id"],
            name="fk_role_definitions_taxonomy",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("taxonomy_version_id", "slug", name="uq_role_definitions_taxonomy_slug"),
        Index(
            "ix_role_definitions_taxonomy_title",
            "taxonomy_version_id",
            "title",
            "id",
        ),
        Index(
            "ix_role_definitions_filter",
            "seniority",
            "industry",
            "domain",
            "title",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    taxonomy_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    seniority: Mapped[str] = mapped_column(String(16), nullable=False)
    industry: Mapped[str] = mapped_column(String(120), nullable=False)
    domain: Mapped[str] = mapped_column(String(120), nullable=False)
    location_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    company_type: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RoleCompetencyModel(Base):
    __tablename__ = "role_competencies"
    __table_args__ = (
        CheckConstraint(f"dimension IN ({_values(_DIMENSIONS)})", name="dimension_valid"),
        CheckConstraint(f"importance IN ({_values(_IMPORTANCE)})", name="importance_valid"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        ForeignKeyConstraint(
            ["role_id"],
            ["role_definitions.id"],
            name="fk_role_competencies_role",
            ondelete="CASCADE",
        ),
        UniqueConstraint("role_id", "label", name="uq_role_competencies_role_label"),
        Index("ix_role_competencies_role_order", "role_id", "sort_order", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[str] = mapped_column(String(16), nullable=False)
    skill_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    transferable_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    adjacent_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class SavedRoleModel(Base):
    __tablename__ = "saved_roles"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["role_id"],
            ["role_definitions.id"],
            name="fk_saved_roles_role",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_saved_roles_owner_id"),
        UniqueConstraint("owner_user_id", "role_id", name="uq_saved_roles_owner_role"),
        Index(
            "ix_saved_roles_owner_updated",
            "owner_user_id",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RoleReadinessAnalysisModel(Base):
    __tablename__ = "role_readiness_analyses"
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
        CheckConstraint("octet_length(feature_set_hash) = 32", name="feature_hash_length"),
        ForeignKeyConstraint(
            ["role_id"],
            ["role_definitions.id"],
            name="fk_role_readiness_analyses_role",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_role_readiness_analyses_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_role_readiness_analyses_owner_idempotency",
        ),
        Index(
            "ix_role_readiness_analyses_owner_role_created",
            "owner_user_id",
            "role_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    saved_role_id: Mapped[UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(120), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_set_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    raw_score_basis_points: Mapped[int | None] = mapped_column(Integer)
    display_score: Mapped[int | None] = mapped_column(Integer)
    readiness_label: Mapped[str] = mapped_column(String(32), nullable=False)
    insufficient_reason: Mapped[str | None] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RoleReadinessComponentModel(Base):
    __tablename__ = "role_readiness_components"
    __table_args__ = (
        CheckConstraint("weight_basis_points BETWEEN 0 AND 10000", name="weight_valid"),
        CheckConstraint("score_basis_points BETWEEN 0 AND 10000", name="score_valid"),
        CheckConstraint(
            "contribution_basis_points BETWEEN 0 AND 10000",
            name="contribution_valid",
        ),
        CheckConstraint(f"dimension IN ({_values(_DIMENSIONS)})", name="dimension_valid"),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["role_readiness_analyses.owner_user_id", "role_readiness_analyses.id"],
            name="fk_role_readiness_components_owner_analysis",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_role_readiness_components_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "dimension",
            name="uq_role_readiness_components_dimension",
        ),
        Index("ix_role_readiness_components_analysis", "owner_user_id", "analysis_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class CompetencyResultModel(Base):
    __tablename__ = "role_competency_results"
    __table_args__ = (
        CheckConstraint(f"dimension IN ({_values(_DIMENSIONS)})", name="dimension_valid"),
        CheckConstraint(f"importance IN ({_values(_IMPORTANCE)})", name="importance_valid"),
        CheckConstraint(f"match_state IN ({_values(_MATCH_STATES)})", name="match_state_valid"),
        CheckConstraint("score_basis_points BETWEEN 0 AND 10000", name="score_valid"),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["role_readiness_analyses.owner_user_id", "role_readiness_analyses.id"],
            name="fk_role_competency_results_owner_analysis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["competency_id"],
            ["role_competencies.id"],
            name="fk_role_competency_results_competency",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_role_competency_results_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "competency_id",
            name="uq_role_competency_results_competency",
        ),
        Index("ix_role_competency_results_analysis", "owner_user_id", "analysis_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    competency_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    importance: Mapped[str] = mapped_column(String(16), nullable=False)
    match_state: Mapped[str] = mapped_column(String(24), nullable=False)
    score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    gap_kind: Mapped[str | None] = mapped_column(String(80))


class CompetencyEvidenceLinkModel(Base):
    __tablename__ = "role_competency_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "relevance_basis_points BETWEEN 0 AND 10000",
            name="relevance_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["role_readiness_analyses.owner_user_id", "role_readiness_analyses.id"],
            name="fk_role_competency_evidence_links_owner_analysis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "competency_result_id"],
            ["role_competency_results.owner_user_id", "role_competency_results.id"],
            name="fk_role_competency_evidence_links_owner_result",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_role_competency_evidence_links_owner_id",
        ),
        Index(
            "ix_role_competency_evidence_links_result",
            "owner_user_id",
            "competency_result_id",
        ),
        Index(
            "ix_role_competency_evidence_links_evidence",
            "owner_user_id",
            "evidence_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    competency_result_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_title: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(40), nullable=False)
    relevance_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)


class RoleReadinessAuditEventModel(Base):
    __tablename__ = "role_readiness_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        UniqueConstraint("owner_user_id", "id", name="uq_role_readiness_audit_events_owner_id"),
        Index(
            "ix_role_readiness_audit_events_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_role_readiness_audit_events_owner_target",
            "owner_user_id",
            "target_kind",
            "target_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
