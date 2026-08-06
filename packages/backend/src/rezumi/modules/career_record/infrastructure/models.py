"""SQLAlchemy mappings for owned Phase 3 career and evidence records."""

from datetime import datetime
from decimal import Decimal
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rezumi.foundation.database import Base

_ENTITY_KINDS = (
    "experience",
    "education",
    "project",
    "credential",
    "publication",
    "award",
    "volunteering",
    "language",
    "portfolio_link",
)
_EMPLOYMENT_TYPES = (
    "full_time",
    "part_time",
    "contract",
    "internship",
    "temporary",
    "volunteer",
    "other",
)
_EVIDENCE_TYPES = (
    "resume_statement",
    "achievement",
    "metric",
    "project",
    "credential",
    "publication",
    "award",
    "review_excerpt",
    "portfolio",
    "testimonial",
    "support_document",
    "note",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class CareerProfileModel(Base):
    __tablename__ = "career_profiles"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", name="uq_career_profiles_owner_user_id"),
        UniqueConstraint("owner_user_id", "id", name="uq_career_profiles_owner_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    professional_headline: Mapped[str | None] = mapped_column(String(240))
    summary: Mapped[str | None] = mapped_column(Text)
    work_authorization: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerEntityModel(Base):
    __tablename__ = "career_entities"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(_ENTITY_KINDS)})", name="kind_valid"),
        CheckConstraint(
            f"employment_type IS NULL OR employment_type IN ({_values(_EMPLOYMENT_TYPES)})",
            name="employment_type_valid",
        ),
        CheckConstraint(
            "kind = 'experience' OR employment_type IS NULL",
            name="employment_type_experience_only",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "start_year IS NULL OR (start_year BETWEEN 1900 AND 2200)",
            name="start_year_valid",
        ),
        CheckConstraint(
            "end_year IS NULL OR (end_year BETWEEN 1900 AND 2200)",
            name="end_year_valid",
        ),
        CheckConstraint(
            "start_month IS NULL OR (start_year IS NOT NULL AND start_month BETWEEN 1 AND 12)",
            name="start_month_valid",
        ),
        CheckConstraint(
            "end_month IS NULL OR (end_year IS NOT NULL AND end_month BETWEEN 1 AND 12)",
            name="end_month_valid",
        ),
        CheckConstraint("NOT is_current OR end_year IS NULL", name="current_has_no_end"),
        CheckConstraint(
            "start_year IS NULL OR end_year IS NULL OR "
            "(end_year * 12 + COALESCE(end_month, 12)) >= "
            "(start_year * 12 + COALESCE(start_month, 1))",
            name="date_order_valid",
        ),
        CheckConstraint(
            "external_url IS NULL OR external_url LIKE 'http://%' OR external_url LIKE 'https://%'",
            name="external_url_http",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_entities_owner_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_entities_owner_id"),
        Index(
            "ix_career_entities_owner_profile_order",
            "owner_user_id",
            "profile_id",
            "sort_order",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    official_title: Mapped[str | None] = mapped_column(String(300))
    display_title: Mapped[str | None] = mapped_column(String(300))
    employment_type: Mapped[str | None] = mapped_column(String(24))
    location: Mapped[str | None] = mapped_column(String(240))
    external_url: Mapped[str | None] = mapped_column(String(2048))
    start_year: Mapped[int | None] = mapped_column(Integer)
    start_month: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer)
    end_month: Mapped[int | None] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[UUID | None] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerEntityConfirmationModel(Base):
    __tablename__ = "career_entity_confirmations"
    __table_args__ = (
        CheckConstraint("state IN ('needs_review','confirmed')", name="state_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(state = 'confirmed' AND confirmed_at IS NOT NULL) OR "
            "(state = 'needs_review' AND confirmed_at IS NULL)",
            name="confirmation_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_confirmations_owner_entity",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id", "entity_id", name="uq_career_entity_confirmations_owner_entity"
        ),
        {"info": {"introduced_in_revision": "20260726_0011"}},
    )

    entity_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareerSkillModel(Base):
    __tablename__ = "career_skills"
    __table_args__ = (
        CheckConstraint(
            "proficiency IS NULL OR proficiency IN ('beginner','intermediate','advanced','expert')",
            name="proficiency_valid",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_skills_owner_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_skills_owner_id"),
        UniqueConstraint(
            "owner_user_id", "profile_id", "name_normalized", name="uq_career_skills_owner_name"
        ),
        Index(
            "ix_career_skills_owner_profile_order",
            "owner_user_id",
            "profile_id",
            "sort_order",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    proficiency: Mapped[str | None] = mapped_column(String(24))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerSkillConfirmationModel(Base):
    __tablename__ = "career_skill_confirmations"
    __table_args__ = (
        CheckConstraint("state IN ('needs_review','confirmed')", name="state_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(state = 'confirmed' AND confirmed_at IS NOT NULL) OR "
            "(state = 'needs_review' AND confirmed_at IS NULL)",
            name="confirmation_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_career_skill_confirmations_owner_skill",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id", "skill_id", name="uq_career_skill_confirmations_owner_skill"
        ),
        {"info": {"introduced_in_revision": "20260726_0011"}},
    )

    skill_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareerPersonalFactModel(Base):
    __tablename__ = "career_personal_facts"
    __table_args__ = (
        CheckConstraint("kind IN ('name','email','phone','location','link')", name="kind_valid"),
        CheckConstraint("confirmation IN ('needs_review','confirmed')", name="confirmation_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(confirmation = 'confirmed' AND confirmed_at IS NOT NULL) OR "
            "(confirmation = 'needs_review' AND confirmed_at IS NULL)",
            name="confirmation_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_personal_facts_owner_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_personal_facts_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "profile_id",
            "kind",
            "value_sha256",
            name="uq_career_personal_facts_owner_value",
        ),
        Index(
            "ix_career_personal_facts_owner_profile_kind",
            "owner_user_id",
            "profile_id",
            "kind",
            "created_at",
        ),
        Index(
            "uq_career_personal_facts_owner_primary_kind",
            "owner_user_id",
            "profile_id",
            "kind",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        {"info": {"introduced_in_revision": "20260726_0011"}},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    value_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(80))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmation: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareerFieldProvenanceModel(Base):
    __tablename__ = "career_field_provenance"
    __table_args__ = (
        CheckConstraint("target IN ('personal_fact','entity','skill')", name="target_valid"),
        CheckConstraint(
            "origin IN ('resume_parser','resume_user_added','owner_edit','owner_attestation')",
            name="origin_valid",
        ),
        CheckConstraint("octet_length(value_sha256) = 32", name="value_sha256_length"),
        CheckConstraint(
            "(target = 'personal_fact' AND personal_fact_id IS NOT NULL "
            "AND entity_id IS NULL AND skill_id IS NULL) OR "
            "(target = 'entity' AND personal_fact_id IS NULL "
            "AND entity_id IS NOT NULL AND skill_id IS NULL) OR "
            "(target = 'skill' AND personal_fact_id IS NULL "
            "AND entity_id IS NULL AND skill_id IS NOT NULL)",
            name="target_reference_valid",
        ),
        CheckConstraint(
            "(origin = 'owner_attestation' AND document_id IS NULL "
            "AND snapshot_id IS NULL AND snapshot_revision IS NULL "
            "AND schema_version IS NULL AND parser_version IS NULL "
            "AND semantic_entity_id IS NULL AND semantic_field_id IS NULL "
            "AND anchors_json = '[]'::jsonb) OR "
            "(origin <> 'owner_attestation' AND document_id IS NOT NULL "
            "AND snapshot_id IS NOT NULL AND snapshot_revision > 0 "
            "AND schema_version IS NOT NULL AND parser_version IS NOT NULL "
            "AND semantic_entity_id IS NOT NULL AND semantic_field_id IS NOT NULL)",
            name="semantic_identity_complete",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_field_provenance_owner_profile",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "personal_fact_id"],
            ["career_personal_facts.owner_user_id", "career_personal_facts.id"],
            name="fk_career_field_provenance_owner_fact",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_field_provenance_owner_entity",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_career_field_provenance_owner_skill",
            ondelete="CASCADE",
        ),
        Index(
            "ix_career_field_provenance_owner_target",
            "owner_user_id",
            "personal_fact_id",
            "entity_id",
            "skill_id",
            "created_at",
        ),
        {"info": {"introduced_in_revision": "20260726_0011"}},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target: Mapped[str] = mapped_column(String(24), nullable=False)
    personal_fact_id: Mapped[UUID | None] = mapped_column(Uuid)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    skill_id: Mapped[UUID | None] = mapped_column(Uuid)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(Uuid)
    snapshot_id: Mapped[UUID | None] = mapped_column(Uuid)
    snapshot_revision: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str | None] = mapped_column(String(80))
    parser_version: Mapped[str | None] = mapped_column(String(120))
    semantic_entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    semantic_field_id: Mapped[UUID | None] = mapped_column(Uuid)
    anchors_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerSemanticImportProposalModel(Base):
    __tablename__ = "career_semantic_import_proposals"
    __table_args__ = (
        CheckConstraint("target IN ('personal_facts','entity','skill')", name="target_valid"),
        CheckConstraint(
            "semantic_kind IN "
            "('contact','experience','education','project','skill','certification')",
            name="semantic_kind_valid",
        ),
        CheckConstraint("status IN ('pending','accepted','rejected')", name="status_valid"),
        CheckConstraint("snapshot_revision > 0", name="snapshot_revision_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL "
            "AND accepted_values_json IS NULL AND decision_idempotency_key IS NULL) OR "
            "(status = 'accepted' AND reviewed_at IS NOT NULL "
            "AND accepted_values_json IS NOT NULL AND decision_idempotency_key IS NOT NULL) OR "
            "(status = 'rejected' AND reviewed_at IS NOT NULL "
            "AND accepted_values_json IS NULL AND decision_idempotency_key IS NOT NULL)",
            name="decision_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_semantic_import_proposals_owner_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "snapshot_id",
            "semantic_entity_id",
            name="uq_career_semantic_proposals_owner_snapshot_entity",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_semantic_proposals_owner_id"),
        Index(
            "ix_career_semantic_proposals_owner_status_created",
            "owner_user_id",
            "status",
            "created_at",
            "id",
        ),
        {"info": {"introduced_in_revision": "20260726_0011"}},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target: Mapped[str] = mapped_column(String(24), nullable=False)
    target_record_id: Mapped[UUID | None] = mapped_column(Uuid)
    document_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    snapshot_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(120), nullable=False)
    semantic_entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    semantic_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    fields_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    accepted_values_json: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    decision_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    conflict_code: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareerEntityRelationshipModel(Base):
    __tablename__ = "career_entity_relationships"
    __table_args__ = (
        CheckConstraint("kind IN ('experience_project')", name="kind_valid"),
        CheckConstraint("source_entity_id <> target_entity_id", name="different_entities"),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_entity_relationships_owner_profile",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "source_entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_relationships_owner_source",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "target_entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_relationships_owner_target",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "source_entity_id",
            "target_entity_id",
            "kind",
            name="uq_career_entity_relationships_owner_pair_kind",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_entity_relationships_owner_id"),
        {"info": {"introduced_in_revision": "20260726_0011"}},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target_entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerEntitySkillModel(Base):
    __tablename__ = "career_entity_skills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_entity_skills_owner_entity",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_career_entity_skills_owner_skill",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_entity_skills_owner_id"),
        UniqueConstraint(
            "owner_user_id", "entity_id", "skill_id", name="uq_career_entity_skills_pair"
        ),
        Index("ix_career_entity_skills_owner_entity", "owner_user_id", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    skill_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceItemModel(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint("lifecycle IN ('active','archived','deleted')", name="lifecycle_valid"),
        CheckConstraint("current_revision > 0", name="current_revision_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(lifecycle = 'active' AND archived_at IS NULL AND deleted_at IS NULL) OR "
            "(lifecycle = 'archived' AND archived_at IS NOT NULL AND deleted_at IS NULL) OR "
            "(lifecycle = 'deleted' AND deleted_at IS NOT NULL)",
            name="lifecycle_timestamps_valid",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_items_owner_id"),
        Index(
            "ix_evidence_items_owner_lifecycle_created",
            "owner_user_id",
            "lifecycle",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenceRevisionModel(Base):
    __tablename__ = "evidence_revisions"
    __table_args__ = (
        CheckConstraint("revision > 0", name="revision_positive"),
        CheckConstraint(f"evidence_type IN ({_values(_EVIDENCE_TYPES)})", name="type_valid"),
        CheckConstraint(
            "strength IN ('verified','confirmed','supported','inferred','unsupported')",
            name="strength_valid",
        ),
        CheckConstraint(
            "input_kind IN ('manual','parser','exact_source_span','achievement','material_edit')",
            name="input_kind_valid",
        ),
        CheckConstraint(
            "start_year IS NULL OR (start_year BETWEEN 1900 AND 2200)",
            name="start_year_valid",
        ),
        CheckConstraint(
            "end_year IS NULL OR (end_year BETWEEN 1900 AND 2200)",
            name="end_year_valid",
        ),
        CheckConstraint(
            "start_month IS NULL OR (start_year IS NOT NULL AND start_month BETWEEN 1 AND 12)",
            name="start_month_valid",
        ),
        CheckConstraint(
            "end_month IS NULL OR (end_year IS NOT NULL AND end_month BETWEEN 1 AND 12)",
            name="end_month_valid",
        ),
        CheckConstraint(
            "start_year IS NULL OR end_year IS NULL OR "
            "(end_year * 12 + COALESCE(end_month, 12)) >= "
            "(start_year * 12 + COALESCE(start_month, 1))",
            name="date_order_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_revisions_owner_evidence",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_revisions_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "evidence_id",
            "id",
            name="uq_evidence_revisions_owner_evidence_id",
            info={"introduced_in_revision": "20260724_0010"},
        ),
        UniqueConstraint(
            "owner_user_id", "evidence_id", "revision", name="uq_evidence_revisions_number"
        ),
        Index(
            "ix_evidence_revisions_owner_evidence_revision",
            "owner_user_id",
            "evidence_id",
            "revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(String(300))
    project: Mapped[str | None] = mapped_column(String(300))
    start_year: Mapped[int | None] = mapped_column(Integer)
    start_month: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer)
    end_month: Mapped[int | None] = mapped_column(Integer)
    strength: Mapped[str] = mapped_column(String(16), nullable=False)
    input_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAttachmentModel(Base):
    __tablename__ = "evidence_attachments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','quarantined','clean','rejected','deleting','deleted')",
            name="status_valid",
        ),
        CheckConstraint(
            "workflow_status IN "
            "('admitted','quarantined','processing','clean','rejected','deleting','deleted')",
            name="workflow_status_valid",
        ),
        CheckConstraint("size_bytes IS NULL OR size_bytes > 0", name="size_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "content_sha256 IS NULL OR octet_length(content_sha256) = 32",
            name="sha256_length",
        ),
        CheckConstraint(
            "(extraction_format_valid IS NULL AND extraction_page_count IS NULL AND "
            "extraction_extracted_characters IS NULL AND extraction_extracted_blocks IS NULL "
            "AND extraction_archive_entries IS NULL "
            "AND extraction_archive_uncompressed_bytes IS NULL "
            "AND extraction_max_archive_ratio IS NULL AND extraction_parser_version IS NULL) "
            "OR (extraction_format_valid IS NOT NULL AND extraction_page_count IS NOT NULL "
            "AND extraction_extracted_characters IS NOT NULL "
            "AND extraction_extracted_blocks IS NOT NULL "
            "AND extraction_archive_entries IS NOT NULL "
            "AND extraction_archive_uncompressed_bytes IS NOT NULL "
            "AND extraction_max_archive_ratio IS NOT NULL "
            "AND extraction_parser_version IS NOT NULL)",
            name="extraction_complete",
        ),
        CheckConstraint(
            "COALESCE(extraction_page_count, 0) >= 0 "
            "AND COALESCE(extraction_extracted_characters, 0) >= 0 "
            "AND COALESCE(extraction_extracted_blocks, 0) >= 0 "
            "AND COALESCE(extraction_archive_entries, 0) >= 0 "
            "AND COALESCE(extraction_archive_uncompressed_bytes, 0) >= 0 "
            "AND COALESCE(extraction_max_archive_ratio, 0) >= 0",
            name="extraction_counts_nonnegative",
        ),
        CheckConstraint(
            "workflow_status <> 'clean' OR "
            "(content_sha256 IS NOT NULL AND extraction_format_valid IS TRUE)",
            name="clean_has_validated_content",
        ),
        CheckConstraint(
            "workflow_status <> 'deleted' OR deleted_at IS NOT NULL",
            name="deleted_has_timestamp",
        ),
        CheckConstraint(
            "(workflow_status = 'deleted' AND display_filename IS NULL "
            "AND media_type IS NULL AND size_bytes IS NULL) OR "
            "(workflow_status <> 'deleted' AND display_filename IS NOT NULL "
            "AND media_type IS NOT NULL AND size_bytes IS NOT NULL)",
            name="tombstone_metadata_redacted",
        ),
        CheckConstraint(
            "workflow_status <> 'deleted' OR (content_sha256 IS NULL "
            "AND staging_object_key IS NULL AND quarantine_object_key IS NULL "
            "AND safe_error_code IS NULL AND extraction_format_valid IS NULL)",
            name="tombstone_sensitive_state_redacted",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_attachments_owner_evidence",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachments_owner_id"),
        Index("ix_evidence_attachments_owner_evidence", "owner_user_id", "evidence_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    display_filename: Mapped[str | None] = mapped_column(String(255))
    media_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    content_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    workflow_status: Mapped[str] = mapped_column(
        String(16), server_default=text("'admitted'"), nullable=False
    )
    staging_object_key: Mapped[str | None] = mapped_column(String(1024))
    quarantine_object_key: Mapped[str | None] = mapped_column(String(1024))
    upload_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    extraction_format_valid: Mapped[bool | None] = mapped_column(Boolean)
    extraction_page_count: Mapped[int | None] = mapped_column(Integer)
    extraction_extracted_characters: Mapped[int | None] = mapped_column(Integer)
    extraction_extracted_blocks: Mapped[int | None] = mapped_column(Integer)
    extraction_archive_entries: Mapped[int | None] = mapped_column(Integer)
    extraction_archive_uncompressed_bytes: Mapped[int | None] = mapped_column(Integer)
    extraction_max_archive_ratio: Mapped[int | None] = mapped_column(Integer)
    extraction_parser_version: Mapped[str | None] = mapped_column(String(128))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAttachmentProcessingJobModel(Base):
    __tablename__ = "evidence_attachment_processing_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','retry_wait','succeeded','rejected',"
            "'dead_lettered','cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            "stage IN ('queued','malware_scan','extraction','complete')",
            name="stage_valid",
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        CheckConstraint("fence >= 0", name="fence_nonnegative"),
        CheckConstraint(
            "execution_token_hash IS NULL OR octet_length(execution_token_hash) = 32",
            name="execution_token_hash_length",
        ),
        CheckConstraint(
            "(status = 'running' AND execution_token_hash IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'running' AND execution_token_hash IS NULL "
            "AND lease_expires_at IS NULL)",
            name="lease_state_valid",
        ),
        CheckConstraint(
            "(status IN ('succeeded','rejected','dead_lettered','cancelled') "
            "AND completed_at IS NOT NULL) OR "
            "(status IN ('queued','running','retry_wait') AND completed_at IS NULL)",
            name="completion_state_valid",
        ),
        CheckConstraint(
            "(status = 'dead_lettered' AND dead_lettered_at IS NOT NULL) OR "
            "(status <> 'dead_lettered' AND dead_lettered_at IS NULL)",
            name="dead_letter_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_jobs_owner_attachment",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_jobs_owner_id"),
        Index(
            "ix_evidence_attachment_jobs_owner_attachment_created",
            "owner_user_id",
            "attachment_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_token_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAttachmentFinalizationModel(Base):
    __tablename__ = "evidence_attachment_finalizations"
    __table_args__ = (
        CheckConstraint("octet_length(request_hash) = 32", name="request_hash_length"),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 8 AND 128",
            name="idempotency_key_length",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_finalizations_owner_attachment",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            [
                "evidence_attachment_processing_jobs.owner_user_id",
                "evidence_attachment_processing_jobs.id",
            ],
            name="fk_evidence_attachment_finalizations_owner_job",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_evidence_attachment_finalizations_owner_key",
        ),
        UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_evidence_attachment_finalizations_owner_id",
        ),
        Index(
            "ix_evidence_attachment_finalizations_owner_attachment",
            "owner_user_id",
            "attachment_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    attachment_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAttachmentOutboxModel(Base):
    __tablename__ = "evidence_attachment_outbox"
    __table_args__ = (
        CheckConstraint(
            "generation >= 0 AND attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        CheckConstraint(
            "(CASE WHEN published_at IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN dead_lettered_at IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN cancelled_at IS NULL THEN 0 ELSE 1 END) <= 1",
            name="terminal_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "job_id"],
            [
                "evidence_attachment_processing_jobs.owner_user_id",
                "evidence_attachment_processing_jobs.id",
            ],
            name="fk_evidence_attachment_outbox_owner_job",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "job_id",
            "generation",
            name="uq_evidence_attachment_outbox_job_generation",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_outbox_owner_id"),
        Index(
            "ix_evidence_attachment_outbox_due",
            "next_attempt_at",
            "id",
            postgresql_where=text(
                "published_at IS NULL AND dead_lettered_at IS NULL AND cancelled_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    task_name: Mapped[str] = mapped_column(String(160), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAttachmentObjectCleanupModel(Base):
    __tablename__ = "evidence_attachment_object_cleanups"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('rejected_staging','finalized_staging','rejected_quarantine',"
            "'owner_deletion')",
            name="purpose_valid",
        ),
        CheckConstraint(
            "status IN ('pending','retry_wait','completed','dead_lettered')",
            name="status_valid",
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="attempts_valid",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL "
            "AND dead_lettered_at IS NULL) OR "
            "(status = 'dead_lettered' AND completed_at IS NULL "
            "AND dead_lettered_at IS NOT NULL) OR "
            "(status IN ('pending','retry_wait') AND completed_at IS NULL "
            "AND dead_lettered_at IS NULL)",
            name="terminal_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_cleanups_owner_attachment",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "object_key",
            name="uq_evidence_attachment_cleanups_owner_object",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_cleanups_owner_id"),
        Index(
            "ix_evidence_attachment_cleanups_due",
            "next_attempt_at",
            "id",
            postgresql_where=text("status IN ('pending','retry_wait')"),
        ),
        Index(
            "ix_evidence_attachment_cleanups_owner_attachment",
            "owner_user_id",
            "attachment_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAttachmentAuditEventModel(Base):
    __tablename__ = "evidence_attachment_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('evidence_attachment.admission_created',"
            "'evidence_attachment.admission_rejected','evidence_attachment.finalized',"
            "'evidence_attachment.processing_retry','evidence_attachment.processing_rejected',"
            "'evidence_attachment.processing_dead_lettered','evidence_attachment.clean',"
            "'evidence_attachment.deletion_requested','evidence_attachment.deleted',"
            "'evidence_attachment.cleanup_dead_lettered')",
            name="action_valid",
        ),
        CheckConstraint("jsonb_typeof(safe_details) = 'object'", name="safe_details_object"),
        CheckConstraint(
            "safe_details - ARRAY['status','safe_error_code','job_status'] = '{}'::jsonb",
            name="safe_details_keys_allowlisted",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_attachment_audits_owner_attachment",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_attachment_audits_owner_id"),
        Index(
            "ix_evidence_attachment_audits_owner_attachment_created",
            "owner_user_id",
            "attachment_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_evidence_attachment_audits_owner_created",
            "owner_user_id",
            "created_at",
            "id",
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
    attachment_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    safe_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceStateTransitionModel(Base):
    __tablename__ = "evidence_state_transitions"
    __table_args__ = (
        CheckConstraint(
            "previous_strength IS NULL OR previous_strength IN "
            "('verified','confirmed','supported','inferred','unsupported')",
            name="previous_strength_valid",
        ),
        CheckConstraint(
            "next_strength IN ('verified','confirmed','supported','inferred','unsupported')",
            name="next_strength_valid",
        ),
        CheckConstraint(
            "authority IN ('system_source_validation','owner_confirmation','owner_rejection',"
            "'deterministic_policy','server_verification','material_edit')",
            name="authority_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_transitions_owner_evidence",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "from_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_transitions_owner_from_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "to_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_transitions_owner_to_revision",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_transitions_owner_id"),
        Index("ix_evidence_transitions_owner_evidence", "owner_user_id", "evidence_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    from_revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    to_revision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    previous_strength: Mapped[str | None] = mapped_column(String(16))
    next_strength: Mapped[str] = mapped_column(String(16), nullable=False)
    authority: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    verifier_reference: Mapped[str | None] = mapped_column(String(240))
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceSourceModel(Base):
    __tablename__ = "evidence_sources"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('user_attestation','resume','attachment','achievement','external_url',"
            "'independent_verifier')",
            name="kind_valid",
        ),
        CheckConstraint(
            "NOT exact_span_validated OR "
            "(document_id IS NOT NULL AND snapshot_id IS NOT NULL AND block_id IS NOT NULL)",
            name="exact_span_has_provenance",
        ),
        CheckConstraint(
            "kind <> 'resume' OR "
            "(document_id IS NOT NULL AND snapshot_id IS NOT NULL AND block_id IS NOT NULL "
            "AND source_sha256 IS NOT NULL)",
            name="resume_has_provenance",
        ),
        CheckConstraint(
            "kind <> 'attachment' OR attachment_id IS NOT NULL",
            name="attachment_has_reference",
        ),
        CheckConstraint(
            "kind <> 'external_url' OR (external_url LIKE 'http://%' "
            "OR external_url LIKE 'https://%')",
            name="external_url_http",
        ),
        CheckConstraint(
            "source_sha256 IS NULL OR octet_length(source_sha256) = 32",
            name="sha256_length",
        ),
        CheckConstraint(
            "(document_id IS NULL AND snapshot_id IS NULL AND snapshot_revision IS NULL "
            "AND schema_version IS NULL AND parser_version IS NULL AND block_id IS NULL "
            "AND page IS NULL AND start_offset IS NULL AND end_offset IS NULL "
            "AND source_sha256 IS NULL AND review_excerpt IS NULL) OR "
            "(document_id IS NOT NULL AND snapshot_id IS NOT NULL "
            "AND snapshot_revision > 0 AND schema_version IS NOT NULL "
            "AND parser_version IS NOT NULL AND block_id IS NOT NULL AND page > 0 "
            "AND start_offset >= 0 AND end_offset >= start_offset "
            "AND source_sha256 IS NOT NULL AND review_excerpt IS NOT NULL)",
            name="provenance_complete",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_sources_owner_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "attachment_id"],
            ["evidence_attachments.owner_user_id", "evidence_attachments.id"],
            name="fk_evidence_sources_owner_attachment",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_sources_owner_id"),
        Index("ix_evidence_sources_owner_revision", "owner_user_id", "evidence_revision_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_revision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    attachment_id: Mapped[UUID | None] = mapped_column(Uuid)
    external_url: Mapped[str | None] = mapped_column(String(2048))
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_span_validated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(Uuid)
    snapshot_id: Mapped[UUID | None] = mapped_column(Uuid)
    snapshot_revision: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str | None] = mapped_column(String(80))
    parser_version: Mapped[str | None] = mapped_column(String(120))
    block_id: Mapped[UUID | None] = mapped_column(Uuid)
    page: Mapped[int | None] = mapped_column(Integer)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    source_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    review_excerpt: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceMetricModel(Base):
    __tablename__ = "evidence_metrics"
    __table_args__ = (
        CheckConstraint("precision IN ('exact','approximate','range')", name="precision_valid"),
        CheckConstraint("precision <> 'range' OR value_max IS NOT NULL", name="range_has_maximum"),
        CheckConstraint("value_max IS NULL OR value_max >= value", name="value_range_valid"),
        CheckConstraint("currency IS NULL OR char_length(currency) = 3", name="currency_length"),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_revision_id"],
            ["evidence_revisions.owner_user_id", "evidence_revisions.id"],
            name="fk_evidence_metrics_owner_revision",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_metrics_owner_id"),
        Index("ix_evidence_metrics_owner_revision", "owner_user_id", "evidence_revision_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_revision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str | None] = mapped_column(String(160))
    value: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    value_max: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    unit: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    period: Mapped[str] = mapped_column(String(240), nullable=False)
    baseline: Mapped[str | None] = mapped_column(String(500))
    comparator: Mapped[str | None] = mapped_column(String(500))
    comparison_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    precision: Mapped[str] = mapped_column(String(16), nullable=False)
    attribution: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceEntityLinkModel(Base):
    __tablename__ = "evidence_entity_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_entity_links_owner_evidence",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_evidence_entity_links_owner_entity",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_entity_links_owner_id"),
        UniqueConstraint(
            "owner_user_id", "evidence_id", "entity_id", name="uq_evidence_entity_links_pair"
        ),
        Index("ix_evidence_entity_links_owner_evidence", "owner_user_id", "evidence_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceSkillLinkModel(Base):
    __tablename__ = "evidence_skill_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_skill_links_owner_evidence",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "skill_id"],
            ["career_skills.owner_user_id", "career_skills.id"],
            name="fk_evidence_skill_links_owner_skill",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_skill_links_owner_id"),
        UniqueConstraint(
            "owner_user_id", "evidence_id", "skill_id", name="uq_evidence_skill_links_pair"
        ),
        Index("ix_evidence_skill_links_owner_evidence", "owner_user_id", "evidence_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    skill_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceUsageModel(Base):
    __tablename__ = "evidence_usage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_usage_owner_evidence",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_usage_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "evidence_id",
            "consumer_kind",
            "consumer_id",
            "purpose",
            name="uq_evidence_usage_target",
        ),
        Index("ix_evidence_usage_owner_evidence", "owner_user_id", "evidence_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    consumer_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    consumer_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceConflictModel(Base):
    __tablename__ = "evidence_conflicts"
    __table_args__ = (
        CheckConstraint("kind IN ('date','title','metric','entity','source')", name="kind_valid"),
        CheckConstraint("status IN ('open','resolved','dismissed')", name="status_valid"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN "
            "('keep_current','accept_incoming','keep_both','not_a_conflict')",
            name="resolution_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'open' AND resolution IS NULL AND resolved_at IS NULL) OR "
            "(status IN ('resolved','dismissed') AND resolution IS NOT NULL "
            "AND resolved_at IS NOT NULL)",
            name="resolution_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_conflicts_owner_evidence",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "conflicting_evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_evidence_conflicts_owner_conflicting_evidence",
            ondelete="CASCADE",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_evidence_conflicts_owner_id"),
        Index(
            "ix_evidence_conflicts_owner_evidence_status",
            "owner_user_id",
            "evidence_id",
            "status",
        ),
        Index(
            "ix_evidence_conflicts_owner_other_status",
            "owner_user_id",
            "conflicting_evidence_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    conflicting_evidence_id: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(24))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareerImportProposalModel(Base):
    __tablename__ = "career_import_proposals"
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','rejected')", name="status_valid"),
        CheckConstraint(f"proposed_kind IN ({_values(_ENTITY_KINDS)})", name="kind_valid"),
        CheckConstraint("snapshot_revision > 0", name="snapshot_revision_positive"),
        CheckConstraint(
            "page > 0 AND start_offset >= 0 AND end_offset >= start_offset",
            name="span_valid",
        ),
        CheckConstraint("octet_length(source_sha256) = 32", name="sha256_length"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR "
            "(status IN ('accepted','rejected') AND reviewed_at IS NOT NULL)",
            name="review_state_valid",
        ),
        CheckConstraint(
            "proposed_start_year IS NULL OR (proposed_start_year BETWEEN 1900 AND 2200)",
            name="start_year_valid",
        ),
        CheckConstraint(
            "proposed_end_year IS NULL OR (proposed_end_year BETWEEN 1900 AND 2200)",
            name="end_year_valid",
        ),
        CheckConstraint(
            "proposed_start_month IS NULL OR (proposed_start_year IS NOT NULL "
            "AND proposed_start_month BETWEEN 1 AND 12)",
            name="start_month_valid",
        ),
        CheckConstraint(
            "proposed_end_month IS NULL OR (proposed_end_year IS NOT NULL "
            "AND proposed_end_month BETWEEN 1 AND 12)",
            name="end_month_valid",
        ),
        CheckConstraint(
            "proposed_start_year IS NULL OR proposed_end_year IS NULL OR "
            "(proposed_end_year * 12 + COALESCE(proposed_end_month, 12)) >= "
            "(proposed_start_year * 12 + COALESCE(proposed_start_month, 1))",
            name="date_order_valid",
        ),
        CheckConstraint(
            "NOT proposed_is_current OR proposed_end_year IS NULL",
            name="current_has_no_end",
        ),
        CheckConstraint(
            f"proposed_employment_type IS NULL OR proposed_employment_type IN "
            f"({_values(_EMPLOYMENT_TYPES)})",
            name="employment_type_valid",
        ),
        CheckConstraint(
            "proposed_kind = 'experience' OR proposed_employment_type IS NULL",
            name="employment_type_experience_only",
        ),
        CheckConstraint(
            "proposed_external_url IS NULL OR proposed_external_url LIKE 'http://%' "
            "OR proposed_external_url LIKE 'https://%'",
            name="external_url_http",
        ),
        CheckConstraint("proposed_sort_order >= 0", name="sort_order_nonnegative"),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_career_import_proposals_owner_profile",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "target_entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_career_import_proposals_owner_target",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_career_import_proposals_owner_id"),
        Index(
            "ix_career_import_proposals_owner_status_created",
            "owner_user_id",
            "status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target_entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    proposed_entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    proposed_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    proposed_title: Mapped[str] = mapped_column(String(300), nullable=False)
    proposed_organization: Mapped[str | None] = mapped_column(String(300))
    proposed_description: Mapped[str | None] = mapped_column(Text)
    proposed_official_title: Mapped[str | None] = mapped_column(String(300))
    proposed_display_title: Mapped[str | None] = mapped_column(String(300))
    proposed_employment_type: Mapped[str | None] = mapped_column(String(24))
    proposed_location: Mapped[str | None] = mapped_column(String(240))
    proposed_external_url: Mapped[str | None] = mapped_column(String(2048))
    proposed_start_year: Mapped[int | None] = mapped_column(Integer)
    proposed_start_month: Mapped[int | None] = mapped_column(Integer)
    proposed_end_year: Mapped[int | None] = mapped_column(Integer)
    proposed_end_month: Mapped[int | None] = mapped_column(Integer)
    proposed_is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    proposed_sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_group_id: Mapped[UUID | None] = mapped_column(Uuid)
    document_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    snapshot_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(120), nullable=False)
    block_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    review_excerpt: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    conflict_code: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AchievementDraftModel(Base):
    __tablename__ = "achievement_drafts"
    __table_args__ = (
        CheckConstraint("status IN ('draft','converted','archived')", name="status_valid"),
        CheckConstraint(
            "reminder_cadence IN ('none','monthly','quarterly','custom')",
            name="reminder_cadence_valid",
        ),
        CheckConstraint(
            "reminder_cadence <> 'custom' OR remind_at IS NOT NULL",
            name="custom_reminder_has_time",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "metric_precision IS NULL OR metric_precision IN ('exact','approximate','range')",
            name="metric_precision_valid",
        ),
        CheckConstraint(
            "(metric_value IS NULL AND metric_name IS NULL AND metric_value_max IS NULL "
            "AND metric_unit IS NULL AND metric_currency IS NULL AND metric_period IS NULL "
            "AND metric_baseline IS NULL AND metric_comparator IS NULL "
            "AND metric_comparison_applicable IS NULL AND metric_precision IS NULL "
            "AND metric_attribution IS NULL) OR "
            "(metric_value IS NOT NULL AND metric_unit IS NOT NULL "
            "AND metric_period IS NOT NULL AND metric_comparison_applicable IS NOT NULL "
            "AND metric_precision IS NOT NULL AND metric_attribution IS NOT NULL)",
            name="metric_complete",
        ),
        CheckConstraint(
            "metric_precision <> 'range' OR metric_value_max IS NOT NULL",
            name="metric_range_has_maximum",
        ),
        CheckConstraint(
            "metric_value_max IS NULL OR metric_value_max >= metric_value",
            name="metric_value_range_valid",
        ),
        CheckConstraint(
            "metric_currency IS NULL OR char_length(metric_currency) = 3",
            name="metric_currency_length",
        ),
        CheckConstraint(
            "(status = 'converted' AND converted_evidence_id IS NOT NULL "
            "AND conversion_idempotency_key IS NOT NULL) OR "
            "(status <> 'converted' AND converted_evidence_id IS NULL "
            "AND conversion_idempotency_key IS NULL)",
            name="conversion_state_valid",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "profile_id"],
            ["career_profiles.owner_user_id", "career_profiles.id"],
            name="fk_achievement_drafts_owner_profile",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "entity_id"],
            ["career_entities.owner_user_id", "career_entities.id"],
            name="fk_achievement_drafts_owner_entity",
        ),
        ForeignKeyConstraint(
            ["owner_user_id", "converted_evidence_id"],
            ["evidence_items.owner_user_id", "evidence_items.id"],
            name="fk_achievement_drafts_owner_evidence",
        ),
        UniqueConstraint("owner_user_id", "id", name="uq_achievement_drafts_owner_id"),
        UniqueConstraint(
            "owner_user_id",
            "conversion_idempotency_key",
            name="uq_achievement_drafts_owner_conversion_key",
        ),
        Index(
            "ix_achievement_drafts_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    delivered: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    measurement: Mapped[str | None] = mapped_column(Text)
    effect: Mapped[str | None] = mapped_column(Text)
    collaboration: Mapped[str | None] = mapped_column(Text)
    methods: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    metric_name: Mapped[str | None] = mapped_column(String(160))
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    metric_value_max: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    metric_unit: Mapped[str | None] = mapped_column(String(80))
    metric_currency: Mapped[str | None] = mapped_column(String(3))
    metric_period: Mapped[str | None] = mapped_column(String(240))
    metric_baseline: Mapped[str | None] = mapped_column(String(500))
    metric_comparator: Mapped[str | None] = mapped_column(String(500))
    metric_comparison_applicable: Mapped[bool | None] = mapped_column(Boolean)
    metric_precision: Mapped[str | None] = mapped_column(String(16))
    metric_attribution: Mapped[str | None] = mapped_column(String(500))
    reminder_cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    converted_evidence_id: Mapped[UUID | None] = mapped_column(Uuid)
    conversion_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReminderPreferencesModel(Base):
    __tablename__ = "career_reminder_preferences"
    __table_args__ = (
        CheckConstraint(
            "(enabled AND day_of_month BETWEEN 1 AND 28) OR (NOT enabled AND day_of_month IS NULL)",
            name="enabled_day_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("owner_user_id", name="uq_career_reminder_preferences_owner_user_id"),
        UniqueConstraint("owner_user_id", "id", name="uq_career_reminder_preferences_owner_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CareerAuditEventModel(Base):
    __tablename__ = "career_audit_events"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "id", name="uq_career_audit_events_owner_id"),
        Index(
            "ix_career_audit_events_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_career_audit_events_owner_target",
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
