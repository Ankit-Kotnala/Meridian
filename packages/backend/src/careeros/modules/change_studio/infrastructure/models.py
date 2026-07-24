"""SQLAlchemy mappings for Phase 6 Change Studio."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careeros.foundation.database import Base

_CHANGE_SET_PURPOSES = ("job_tailoring",)
_CHANGE_TARGET_KINDS = ("tailored_resume_bullet", "profile_summary")
_CHANGE_SET_STATUSES = ("draft", "applied")
_OPERATION_TYPES = ("add_bullet", "replace_bullet", "replace_summary")
_OPERATION_STATUSES = ("proposed", "accepted", "rejected", "edited", "blocked")
_GROUNDING_STATUSES = ("grounded", "blocked", "needs_clarification")
_RISK_LEVELS = ("low", "medium", "high")
_CLAIM_KINDS = (
    "responsibility",
    "achievement",
    "metric_outcome",
    "skill",
    "credential",
    "experience",
    "other",
)
_VALIDATION_STATUSES = ("passed", "failed")
_CLARIFICATION_STATUSES = ("open", "answered", "dismissed")
_PROVIDER_RUN_STATUSES = ("succeeded", "failed", "blocked")
_AUDIT_ACTIONS = (
    "change_set_created",
    "operation_accepted",
    "operation_rejected",
    "operation_edited",
    "operation_alternative_created",
    "operation_locked",
    "operation_unlocked",
    "safe_changes_applied",
    "change_set_undone",
    "change_set_redone",
    "version_restored",
    "clarification_answered",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class ChangeSetModel(Base):
    __tablename__ = "change_sets"
    __table_args__ = (
        CheckConstraint(f"purpose IN ({_values(_CHANGE_SET_PURPOSES)})", name="purpose_valid"),
        CheckConstraint(
            f"target_kind IN ({_values(_CHANGE_TARGET_KINDS)})",
            name="target_kind_valid",
        ),
        CheckConstraint(f"status IN ({_values(_CHANGE_SET_STATUSES)})", name="status_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", "id", name="uq_change_sets_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_change_sets_owner_idempotency",
        ),
        Index("ix_change_sets_owner_updated", "owner_user_id", "updated_at", "id"),
        Index("ix_change_sets_owner_analysis", "owner_user_id", "analysis_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    job_id: Mapped[UUID | None] = mapped_column(Uuid)
    analysis_id: Mapped[UUID | None] = mapped_column(Uuid)
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    grounding_version: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChangeOperationModel(Base):
    __tablename__ = "change_operations"
    __table_args__ = (
        CheckConstraint(
            f"operation_type IN ({_values(_OPERATION_TYPES)})",
            name="operation_type_valid",
        ),
        CheckConstraint(
            f"target_kind IN ({_values(_CHANGE_TARGET_KINDS)})",
            name="target_kind_valid",
        ),
        CheckConstraint(
            f"status IN ({_values(_OPERATION_STATUSES)})",
            name="status_valid",
        ),
        CheckConstraint(
            f"risk IN ({_values(_RISK_LEVELS)})",
            name="risk_valid",
        ),
        CheckConstraint(
            f"grounding_status IN ({_values(_GROUNDING_STATUSES)})",
            name="grounding_status_valid",
        ),
        CheckConstraint(
            "confidence_basis_points BETWEEN 0 AND 10000",
            name="confidence_valid",
        ),
        CheckConstraint(
            "expected_score_delta_basis_points IS NULL OR "
            "expected_score_delta_basis_points BETWEEN -10000 AND 10000",
            name="expected_score_delta_valid",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_operations_owner_change_set",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_change_operations_owner_id"),
        Index(
            "ix_change_operations_change_set_order",
            "owner_user_id",
            "change_set_id",
            "sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    change_set_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    before_text: Mapped[str] = mapped_column(Text, nullable=False)
    after_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    grounding_status: Mapped[str] = mapped_column(String(32), nullable=False)
    grounding_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    expected_score_delta_basis_points: Mapped[int | None] = mapped_column(Integer)
    requirement_id: Mapped[UUID | None] = mapped_column(Uuid)
    requirement_text: Mapped[str | None] = mapped_column(Text)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChangeClaimModel(Base):
    __tablename__ = "change_operation_claims"
    __table_args__ = (
        CheckConstraint(f"claim_kind IN ({_values(_CLAIM_KINDS)})", name="claim_kind_valid"),
        CheckConstraint(
            f"validation_status IN ({_values(_VALIDATION_STATUSES)})",
            name="validation_status_valid",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint(
            "(evidence_revision_id IS NULL "
            "AND evidence_revision_number IS NULL "
            "AND evidence_statement_sha256 IS NULL) "
            "OR "
            "(evidence_revision_id IS NOT NULL "
            "AND evidence_revision_number IS NOT NULL "
            "AND evidence_statement_sha256 IS NOT NULL "
            "AND evidence_revision_number > 0 "
            "AND evidence_statement_sha256 ~ '^[0-9a-f]{64}$')",
            name="evidence_provenance_complete",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_claims_owner_change_set",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "operation_id"],
            ["change_operations.owner_user_id", "change_operations.id"],
            name="fk_change_claims_owner_operation",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_change_claims_owner_id"),
        Index("ix_change_claims_operation_order", "owner_user_id", "operation_id", "sort_order"),
        Index("ix_change_claims_evidence", "owner_user_id", "evidence_id", "operation_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    change_set_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    claim_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    evidence_revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    evidence_revision_number: Mapped[int | None] = mapped_column(Integer)
    evidence_statement_sha256: Mapped[str | None] = mapped_column(String(64))
    evidence_title: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(40), nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False)
    validation_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClarifyingQuestionModel(Base):
    __tablename__ = "change_clarifying_questions"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_CLARIFICATION_STATUSES)})",
            name="status_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_questions_owner_change_set",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "operation_id"],
            ["change_operations.owner_user_id", "change_operations.id"],
            name="fk_change_questions_owner_operation",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_change_questions_owner_id"),
        Index("ix_change_questions_change_set", "owner_user_id", "change_set_id", "created_at"),
        Index("ix_change_questions_requirement", "owner_user_id", "requirement_id", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    change_set_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation_id: Mapped[UUID | None] = mapped_column(Uuid)
    requirement_id: Mapped[UUID | None] = mapped_column(Uuid)
    evidence_id: Mapped[UUID | None] = mapped_column(Uuid)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChangeSetVersionModel(Base):
    __tablename__ = "change_set_versions"
    __table_args__ = (
        CheckConstraint("version_number > 0", name="version_number_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_versions_owner_change_set",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "parent_version_id"],
            ["change_set_versions.owner_user_id", "change_set_versions.id"],
            name="fk_change_versions_owner_parent",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "created_by_operation_id"],
            ["change_operations.owner_user_id", "change_operations.id"],
            name="fk_change_versions_owner_operation",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_change_versions_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "change_set_id",
            "version_number",
            name="uq_change_versions_change_set_number",
        ),
        Index(
            "ix_change_versions_change_set_number",
            "owner_user_id",
            "change_set_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    change_set_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_by_operation_id: Mapped[UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    operation_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderRunModel(Base):
    __tablename__ = "change_provider_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values(_PROVIDER_RUN_STATUSES)})",
            name="status_valid",
        ),
        CheckConstraint("output_operation_count BETWEEN 0 AND 100", name="output_count_valid"),
        CheckConstraint("latency_ms >= 0", name="latency_nonnegative"),
        CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0",
            name="prompt_tokens_nonnegative",
        ),
        CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="completion_tokens_nonnegative",
        ),
        CheckConstraint(
            "cost_micros IS NULL OR cost_micros >= 0",
            name="cost_micros_nonnegative",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "change_set_id"],
            ["change_sets.owner_user_id", "change_sets.id"],
            name="fk_change_provider_runs_owner_change_set",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_change_provider_runs_owner_id"),
        Index("ix_change_provider_runs_change_set", "owner_user_id", "change_set_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    change_set_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    grounding_version: Mapped[str] = mapped_column(String(120), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    input_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    input_requirement_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    output_operation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_micros: Mapped[int | None] = mapped_column(Integer)
    validation_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChangeStudioIdempotencyModel(Base):
    __tablename__ = "change_studio_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_change_studio_idempotency_owner_key",
        ),
        Index("ix_change_studio_idempotency_target", "owner_user_id", "target_kind", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChangeStudioAuditEventModel(Base):
    __tablename__ = "change_studio_audit_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_values(_AUDIT_ACTIONS)})", name="action_valid"),
        Index("ix_change_studio_audit_owner_created", "owner_user_id", "created_at", "id"),
        Index("ix_change_studio_audit_target", "target_kind", "target_id", "created_at"),
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
