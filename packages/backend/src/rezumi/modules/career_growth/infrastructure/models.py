"""SQLAlchemy mappings for Career Growth and deterministic Career Health."""

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

_GOAL_STATUSES = ("active", "paused", "completed", "cancelled")
_MILESTONE_STATUSES = ("pending", "in_progress", "completed", "cancelled")
_DEVELOPMENT_KINDS = (
    "learning",
    "certification",
    "performance_review",
    "promotion",
    "internal_mobility",
    "annual_resume_refresh",
)
_DEVELOPMENT_STATUSES = ("planned", "in_progress", "paused", "completed", "cancelled")
_REVIEW_CADENCES = ("quarterly", "annual")
_REVIEW_STATUSES = ("draft", "finalized")
_EVIDENCE_TARGET_KINDS = ("goal", "milestone", "development_item", "review_version")
_HEALTH_STATUSES = ("complete", "insufficient_data")
_HEALTH_LABELS = (
    "well_maintained",
    "developing",
    "needs_attention",
    "insufficient_data",
)
_HEALTH_DIMENSIONS = (
    "evidence_currency",
    "goal_progress",
    "development_follow_through",
    "review_cadence",
    "readiness_maintenance",
)
_FINDING_SEVERITIES = ("information", "attention")
_AUDIT_ACTIONS = (
    "goal_created",
    "goal_updated",
    "goal_deleted",
    "milestone_created",
    "milestone_updated",
    "milestone_deleted",
    "development_item_created",
    "development_item_updated",
    "development_item_deleted",
    "review_created",
    "review_revised",
    "review_finalized",
    "review_deleted",
    "career_health_analyzed",
    "career_health_deleted",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class CareerGoalModel(Base):
    __tablename__ = "career_growth_goals"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_GOAL_STATUSES)})", name="status_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", "id", name="uq_career_growth_goals_owner_id"),
        Index(
            "ix_career_growth_goals_owner_updated",
            "owner_user_id",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GoalMilestoneModel(Base):
    __tablename__ = "career_growth_milestones"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_MILESTONE_STATUSES)})", name="status_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="completion_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "goal_id"],
            ["career_growth_goals.owner_user_id", "career_growth_goals.id"],
            name="fk_career_growth_milestones_owner_goal",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_growth_milestones_owner_id"),
        Index(
            "ix_career_growth_milestones_owner_goal_target",
            "owner_user_id",
            "goal_id",
            "target_date",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DevelopmentItemModel(Base):
    __tablename__ = "career_growth_development_items"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(_DEVELOPMENT_KINDS)})", name="kind_valid"),
        CheckConstraint(f"status IN ({_values(_DEVELOPMENT_STATUSES)})", name="status_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="completion_state_valid",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_growth_development_items_owner_id"),
        Index(
            "ix_career_growth_development_items_owner_updated",
            "owner_user_id",
            "updated_at",
            "id",
        ),
        Index(
            "ix_career_growth_development_items_owner_kind_status",
            "owner_user_id",
            "kind",
            "status",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerReviewModel(Base):
    __tablename__ = "career_growth_reviews"
    __table_args__ = (
        CheckConstraint(f"cadence IN ({_values(_REVIEW_CADENCES)})", name="cadence_valid"),
        CheckConstraint(
            f"latest_status IN ({_values(_REVIEW_STATUSES)})",
            name="latest_status_valid",
        ),
        CheckConstraint("period_end >= period_start", name="period_valid"),
        CheckConstraint("latest_version_number > 0", name="latest_version_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            [
                "owner_user_id",
                "id",
                "latest_version_id",
                "latest_version_number",
                "latest_status",
            ],
            [
                "career_growth_review_versions.owner_user_id",
                "career_growth_review_versions.review_id",
                "career_growth_review_versions.id",
                "career_growth_review_versions.version_number",
                "career_growth_review_versions.status",
            ],
            name="fk_career_growth_reviews_owner_latest_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_growth_reviews_owner_id"),
        Index(
            "ix_career_growth_reviews_owner_period",
            "owner_user_id",
            "period_end",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    latest_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    latest_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerReviewVersionModel(Base):
    __tablename__ = "career_growth_review_versions"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_REVIEW_STATUSES)})", name="status_valid"),
        CheckConstraint("version_number > 0", name="version_number_positive"),
        CheckConstraint("octet_length(content_sha256) = 32", name="content_hash_length"),
        CheckConstraint(
            "(version_number = 1 AND supersedes_version_id IS NULL) OR "
            "(version_number > 1 AND supersedes_version_id IS NOT NULL)",
            name="predecessor_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "review_id"],
            ["career_growth_reviews.owner_user_id", "career_growth_reviews.id"],
            name="fk_career_growth_review_versions_owner_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "review_id", "supersedes_version_id"],
            [
                "career_growth_review_versions.owner_user_id",
                "career_growth_review_versions.review_id",
                "career_growth_review_versions.id",
            ],
            name="fk_career_growth_review_versions_owner_predecessor",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_growth_review_versions_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "review_id",
            "version_number",
            name="uq_career_growth_review_versions_number",
        ),
        UniqueConstraint(
            "owner_user_id",
            "review_id",
            "id",
            name="uq_career_growth_review_versions_owner_review_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "review_id",
            "id",
            "version_number",
            "status",
            name="uq_career_growth_review_versions_latest_state",
        ),
        Index(
            "ix_career_growth_review_versions_owner_review",
            "owner_user_id",
            "review_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    review_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    achievements: Mapped[str | None] = mapped_column(Text)
    growth_areas: Mapped[str | None] = mapped_column(Text)
    next_focus: Mapped[str | None] = mapped_column(Text)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    material_change: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supersedes_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    content_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerGrowthEvidenceLinkModel(Base):
    __tablename__ = "career_growth_evidence_links"
    __table_args__ = (
        CheckConstraint(
            f"target_kind IN ({_values(_EVIDENCE_TARGET_KINDS)})",
            name="target_kind_valid",
        ),
        CheckConstraint("revision_number > 0", name="revision_number_positive"),
        CheckConstraint("octet_length(statement_sha256) = 32", name="statement_hash_length"),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id", "evidence_revision_id"],
            [
                "evidence_revisions.owner_user_id",
                "evidence_revisions.evidence_id",
                "evidence_revisions.id",
            ],
            name="fk_career_growth_evidence_links_owner_revision",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_career_growth_evidence_links_owner_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "target_kind",
            "target_id",
            "evidence_id",
            name="uq_career_growth_evidence_links_target_evidence",
        ),
        Index(
            "ix_career_growth_evidence_links_owner_target",
            "owner_user_id",
            "target_kind",
            "target_id",
        ),
        Index(
            "ix_career_growth_evidence_links_owner_evidence",
            "owner_user_id",
            "evidence_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_revision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    evidence_revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerGrowthIdempotencyModel(Base):
    __tablename__ = "career_growth_idempotency"
    __table_args__ = (
        CheckConstraint("octet_length(request_fingerprint) = 32", name="fingerprint_length"),
        UniqueConstraint("owner_user_id", "id", name="uq_career_growth_idempotency_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_career_growth_idempotency_owner_key",
        ),
        Index(
            "ix_career_growth_idempotency_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    result_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerHealthAnalysisModel(Base):
    __tablename__ = "career_health_analyses"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(_HEALTH_STATUSES)})", name="status_valid"),
        CheckConstraint(f"label IN ({_values(_HEALTH_LABELS)})", name="label_valid"),
        CheckConstraint(
            "raw_score_basis_points IS NULL OR raw_score_basis_points BETWEEN 0 AND 10000",
            name="raw_score_valid",
        ),
        CheckConstraint(
            "display_score IS NULL OR display_score BETWEEN 0 AND 100",
            name="display_score_valid",
        ),
        CheckConstraint(
            "applicable_component_count BETWEEN 0 AND 5",
            name="component_count_valid",
        ),
        CheckConstraint(
            "applicable_weight_basis_points BETWEEN 0 AND 10000",
            name="applicable_weight_valid",
        ),
        CheckConstraint("octet_length(snapshot_sha256) = 32", name="snapshot_hash_length"),
        CheckConstraint(
            "(status = 'complete' AND raw_score_basis_points IS NOT NULL "
            "AND display_score IS NOT NULL AND insufficient_reason IS NULL "
            "AND label <> 'insufficient_data') OR "
            "(status = 'insufficient_data' AND raw_score_basis_points IS NULL "
            "AND display_score IS NULL AND insufficient_reason IS NOT NULL "
            "AND label = 'insufficient_data')",
            name="result_state_valid",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_health_analyses_owner_id"),
        Index(
            "ix_career_health_analyses_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(120), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    formula_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    raw_score_basis_points: Mapped[int | None] = mapped_column(Integer)
    display_score: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    applicable_component_count: Mapped[int] = mapped_column(Integer, nullable=False)
    applicable_weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    insufficient_reason: Mapped[str | None] = mapped_column(String(500))
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerHealthComponentModel(Base):
    __tablename__ = "career_health_components"
    __table_args__ = (
        CheckConstraint(f"dimension IN ({_values(_HEALTH_DIMENSIONS)})", name="dimension_valid"),
        CheckConstraint(
            "configured_weight_basis_points BETWEEN 0 AND 10000",
            name="weight_valid",
        ),
        CheckConstraint(
            "score_basis_points IS NULL OR score_basis_points BETWEEN 0 AND 10000",
            name="score_valid",
        ),
        CheckConstraint(
            "contribution_basis_points IS NULL OR contribution_basis_points BETWEEN 0 AND 10000",
            name="contribution_valid",
        ),
        CheckConstraint(
            "(score_basis_points IS NULL AND contribution_basis_points IS NULL) OR "
            "(score_basis_points IS NOT NULL AND contribution_basis_points IS NOT NULL)",
            name="score_contribution_pair_valid",
        ),
        CheckConstraint(
            "applicable OR (score_basis_points IS NULL AND contribution_basis_points IS NULL)",
            name="applicability_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["career_health_analyses.owner_user_id", "career_health_analyses.id"],
            name="fk_career_health_components_owner_analysis",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_health_components_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "dimension",
            name="uq_career_health_components_dimension",
        ),
        Index(
            "ix_career_health_components_owner_analysis",
            "owner_user_id",
            "analysis_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    configured_weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    applicable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score_basis_points: Mapped[int | None] = mapped_column(Integer)
    contribution_basis_points: Mapped[int | None] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class CareerHealthFindingModel(Base):
    __tablename__ = "career_health_findings"
    __table_args__ = (
        CheckConstraint(f"severity IN ({_values(_FINDING_SEVERITIES)})", name="severity_valid"),
        ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["career_health_analyses.owner_user_id", "career_health_analyses.id"],
            name="fk_career_health_findings_owner_analysis",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_health_findings_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "code",
            name="uq_career_health_findings_code",
        ),
        Index(
            "ix_career_health_findings_owner_analysis",
            "owner_user_id",
            "analysis_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)


class CareerGrowthAuditEventModel(Base):
    __tablename__ = "career_growth_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        UniqueConstraint("owner_user_id", "id", name="uq_career_growth_audit_events_owner_id"),
        Index(
            "ix_career_growth_audit_events_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_career_growth_audit_events_owner_target",
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
