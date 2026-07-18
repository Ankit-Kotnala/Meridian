"""Add Phase 4 Role Explorer and Role Readiness snapshots.

Revision ID: 20260719_0005
Revises: 20260715_0004
Create Date: 2026-07-19 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0005"
down_revision: str | None = "20260715_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TAXONOMY_ID = UUID("00000000-0000-4000-8000-000000000401")
PRODUCT_MANAGER_ID = UUID("00000000-0000-4000-8000-000000000411")
SOFTWARE_ENGINEER_ID = UUID("00000000-0000-4000-8000-000000000412")
DATA_ANALYST_ID = UUID("00000000-0000-4000-8000-000000000413")
CREATED_AT = datetime(2026, 7, 19, tzinfo=UTC)


def upgrade() -> None:
    op.create_table(
        "role_taxonomy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_license", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_role_taxonomy_versions"),
        sa.UniqueConstraint("version", name="uq_role_taxonomy_versions_version"),
    )
    op.create_index(
        "ix_role_taxonomy_versions_active_published",
        "role_taxonomy_versions",
        ["active", "published_at"],
    )
    op.create_table(
        "role_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("seniority", sa.String(length=16), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=120), nullable=False),
        sa.Column("location_scope", sa.String(length=120), nullable=False),
        sa.Column("company_type", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "seniority IN ('entry','mid','senior','lead','executive')",
            name="ck_role_definitions_seniority_valid",
        ),
        sa.CheckConstraint("version > 0", name="ck_role_definitions_version_positive"),
        sa.ForeignKeyConstraint(
            ["taxonomy_version_id"],
            ["role_taxonomy_versions.id"],
            name="fk_role_definitions_taxonomy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_definitions"),
        sa.UniqueConstraint(
            "taxonomy_version_id", "slug", name="uq_role_definitions_taxonomy_slug"
        ),
    )
    op.create_index(
        "ix_role_definitions_filter",
        "role_definitions",
        ["seniority", "industry", "domain", "title"],
    )
    op.create_index(
        "ix_role_definitions_taxonomy_title",
        "role_definitions",
        ["taxonomy_version_id", "title", "id"],
    )
    op.create_table(
        "role_competencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("skill_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("transferable_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("adjacent_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "dimension IN ('core_competency','responsibility_alignment',"
            "'seniority_alignment','leadership_evidence','domain_knowledge',"
            "'technical_skills','business_impact','education_certification',"
            "'evidence_strength')",
            name="ck_role_competencies_dimension_valid",
        ),
        sa.CheckConstraint(
            "importance IN ('required','helpful')",
            name="ck_role_competencies_importance_valid",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_role_competencies_sort_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role_definitions.id"],
            name="fk_role_competencies_role",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_competencies"),
        sa.UniqueConstraint("role_id", "label", name="uq_role_competencies_role_label"),
    )
    op.create_index(
        "ix_role_competencies_role_order",
        "role_competencies",
        ["role_id", "sort_order", "id"],
    )
    op.create_table(
        "saved_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_saved_roles_version_positive"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_saved_roles_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role_definitions.id"],
            name="fk_saved_roles_role",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_saved_roles"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_saved_roles_owner_id"),
        sa.UniqueConstraint("owner_user_id", "role_id", name="uq_saved_roles_owner_role"),
    )
    op.create_index(
        "ix_saved_roles_owner_updated",
        "saved_roles",
        ["owner_user_id", "updated_at", "id"],
    )
    op.create_table(
        "role_readiness_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("saved_role_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("engine_version", sa.String(length=120), nullable=False),
        sa.Column("configuration_version", sa.String(length=120), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=120), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=80), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("feature_set_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("raw_score_basis_points", sa.Integer(), nullable=True),
        sa.Column("display_score", sa.Integer(), nullable=True),
        sa.Column("readiness_label", sa.String(length=32), nullable=False),
        sa.Column("insufficient_reason", sa.String(length=160), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_score IS NULL OR display_score BETWEEN 0 AND 100",
            name="ck_role_readiness_analyses_display_score_valid",
        ),
        sa.CheckConstraint(
            "octet_length(feature_set_hash) = 32",
            name="ck_role_readiness_analyses_feature_hash_length",
        ),
        sa.CheckConstraint(
            "raw_score_basis_points IS NULL OR raw_score_basis_points BETWEEN 0 AND 10000",
            name="ck_role_readiness_analyses_raw_score_valid",
        ),
        sa.CheckConstraint(
            "readiness_label IN ('strong','developing','needs_evidence','insufficient_data')",
            name="ck_role_readiness_analyses_readiness_label_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_role_readiness_analyses_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role_definitions.id"],
            name="fk_role_readiness_analyses_role",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_readiness_analyses"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_role_readiness_analyses_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_role_readiness_analyses_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_role_readiness_analyses_owner_role_created",
        "role_readiness_analyses",
        ["owner_user_id", "role_id", "created_at", "id"],
    )
    op.create_table(
        "role_readiness_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=40), nullable=False),
        sa.Column("weight_basis_points", sa.Integer(), nullable=False),
        sa.Column("score_basis_points", sa.Integer(), nullable=False),
        sa.Column("contribution_basis_points", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "contribution_basis_points BETWEEN 0 AND 10000",
            name="ck_role_readiness_components_contribution_valid",
        ),
        sa.CheckConstraint(
            "dimension IN ('core_competency','responsibility_alignment',"
            "'seniority_alignment','leadership_evidence','domain_knowledge',"
            "'technical_skills','business_impact','education_certification',"
            "'evidence_strength')",
            name="ck_role_readiness_components_dimension_valid",
        ),
        sa.CheckConstraint(
            "score_basis_points BETWEEN 0 AND 10000",
            name="ck_role_readiness_components_score_valid",
        ),
        sa.CheckConstraint(
            "weight_basis_points BETWEEN 0 AND 10000",
            name="ck_role_readiness_components_weight_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["role_readiness_analyses.owner_user_id", "role_readiness_analyses.id"],
            name="fk_role_readiness_components_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_role_readiness_components_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_readiness_components"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_role_readiness_components_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "dimension",
            name="uq_role_readiness_components_dimension",
        ),
    )
    op.create_index(
        "ix_role_readiness_components_analysis",
        "role_readiness_components",
        ["owner_user_id", "analysis_id"],
    )
    op.create_table(
        "role_competency_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("match_state", sa.String(length=24), nullable=False),
        sa.Column("score_basis_points", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("gap_kind", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "dimension IN ('core_competency','responsibility_alignment',"
            "'seniority_alignment','leadership_evidence','domain_knowledge',"
            "'technical_skills','business_impact','education_certification',"
            "'evidence_strength')",
            name="ck_role_competency_results_dimension_valid",
        ),
        sa.CheckConstraint(
            "importance IN ('required','helpful')",
            name="ck_role_competency_results_importance_valid",
        ),
        sa.CheckConstraint(
            "match_state IN ('demonstrated','listed','transferable','adjacent',"
            "'missing','unknown')",
            name="ck_role_competency_results_match_state_valid",
        ),
        sa.CheckConstraint(
            "score_basis_points BETWEEN 0 AND 10000",
            name="ck_role_competency_results_score_valid",
        ),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["role_competencies.id"],
            name="fk_role_competency_results_competency",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["role_readiness_analyses.owner_user_id", "role_readiness_analyses.id"],
            name="fk_role_competency_results_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_role_competency_results_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_competency_results"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_role_competency_results_owner_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "analysis_id",
            "competency_id",
            name="uq_role_competency_results_competency",
        ),
    )
    op.create_index(
        "ix_role_competency_results_analysis",
        "role_competency_results",
        ["owner_user_id", "analysis_id"],
    )
    op.create_table(
        "role_competency_evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("competency_result_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_title", sa.String(length=300), nullable=False),
        sa.Column("evidence_strength", sa.String(length=40), nullable=False),
        sa.Column("relevance_basis_points", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "relevance_basis_points BETWEEN 0 AND 10000",
            name="ck_role_competency_evidence_links_relevance_valid",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "analysis_id"],
            ["role_readiness_analyses.owner_user_id", "role_readiness_analyses.id"],
            name="fk_role_competency_evidence_links_owner_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id", "competency_result_id"],
            ["role_competency_results.owner_user_id", "role_competency_results.id"],
            name="fk_role_competency_evidence_links_owner_result",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_role_competency_evidence_links_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_competency_evidence_links"),
        sa.UniqueConstraint(
            "owner_user_id",
            "id",
            name="uq_role_competency_evidence_links_owner_id",
        ),
    )
    op.create_index(
        "ix_role_competency_evidence_links_evidence",
        "role_competency_evidence_links",
        ["owner_user_id", "evidence_id"],
    )
    op.create_index(
        "ix_role_competency_evidence_links_result",
        "role_competency_evidence_links",
        ["owner_user_id", "competency_result_id"],
    )
    op.create_table(
        "role_readiness_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('saved_role_created','saved_role_updated',"
            "'saved_role_deleted','readiness_analyzed')",
            name="ck_role_readiness_audit_events_action_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_role_readiness_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_role_readiness_audit_events_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_readiness_audit_events"),
        sa.UniqueConstraint("owner_user_id", "id", name="uq_role_readiness_audit_events_owner_id"),
    )
    op.create_index(
        "ix_role_readiness_audit_events_owner_created",
        "role_readiness_audit_events",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_role_readiness_audit_events_owner_target",
        "role_readiness_audit_events",
        ["owner_user_id", "target_kind", "target_id"],
    )
    _seed_taxonomy()


def downgrade() -> None:
    op.drop_index(
        "ix_role_readiness_audit_events_owner_target",
        table_name="role_readiness_audit_events",
    )
    op.drop_index(
        "ix_role_readiness_audit_events_owner_created",
        table_name="role_readiness_audit_events",
    )
    op.drop_table("role_readiness_audit_events")
    op.drop_index(
        "ix_role_competency_evidence_links_result",
        table_name="role_competency_evidence_links",
    )
    op.drop_index(
        "ix_role_competency_evidence_links_evidence",
        table_name="role_competency_evidence_links",
    )
    op.drop_table("role_competency_evidence_links")
    op.drop_index("ix_role_competency_results_analysis", table_name="role_competency_results")
    op.drop_table("role_competency_results")
    op.drop_index("ix_role_readiness_components_analysis", table_name="role_readiness_components")
    op.drop_table("role_readiness_components")
    op.drop_index(
        "ix_role_readiness_analyses_owner_role_created",
        table_name="role_readiness_analyses",
    )
    op.drop_table("role_readiness_analyses")
    op.drop_index("ix_saved_roles_owner_updated", table_name="saved_roles")
    op.drop_table("saved_roles")
    op.drop_index("ix_role_competencies_role_order", table_name="role_competencies")
    op.drop_table("role_competencies")
    op.drop_index("ix_role_definitions_taxonomy_title", table_name="role_definitions")
    op.drop_index("ix_role_definitions_filter", table_name="role_definitions")
    op.drop_table("role_definitions")
    op.drop_index(
        "ix_role_taxonomy_versions_active_published",
        table_name="role_taxonomy_versions",
    )
    op.drop_table("role_taxonomy_versions")


def _seed_taxonomy() -> None:
    taxonomy = sa.table(
        "role_taxonomy_versions",
        sa.column("id", sa.Uuid()),
        sa.column("version", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_license", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("active", sa.Boolean()),
        sa.column("published_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    roles = sa.table(
        "role_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("taxonomy_version_id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("title", sa.String()),
        sa.column("seniority", sa.String()),
        sa.column("industry", sa.String()),
        sa.column("domain", sa.String()),
        sa.column("location_scope", sa.String()),
        sa.column("company_type", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    competencies = sa.table(
        "role_competencies",
        sa.column("id", sa.Uuid()),
        sa.column("role_id", sa.Uuid()),
        sa.column("dimension", sa.String()),
        sa.column("label", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("importance", sa.String()),
        sa.column("skill_keywords", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("evidence_keywords", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("transferable_keywords", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("adjacent_keywords", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(
        taxonomy,
        [
            {
                "id": TAXONOMY_ID,
                "version": "careeros-seed-roles/2026-07-19",
                "source_name": "CareerOS authored seed taxonomy",
                "source_license": "CareerOS internal product taxonomy",
                "description": (
                    "Initial deterministic role taxonomy for Role Explorer readiness matching."
                ),
                "active": True,
                "published_at": CREATED_AT,
                "created_at": CREATED_AT,
            }
        ],
    )
    op.bulk_insert(
        roles,
        [
            _role(
                PRODUCT_MANAGER_ID,
                "product-manager",
                "Product Manager",
                "senior",
                "Technology",
                "Product",
                "global",
                "software",
                "Owns product discovery, prioritization, delivery, and measurable outcomes.",
            ),
            _role(
                SOFTWARE_ENGINEER_ID,
                "software-engineer",
                "Software Engineer",
                "mid",
                "Technology",
                "Engineering",
                "global",
                "software",
                "Builds reliable software systems with testing, collaboration, and delivery rigor.",
            ),
            _role(
                DATA_ANALYST_ID,
                "data-analyst",
                "Data Analyst",
                "mid",
                "Technology",
                "Analytics",
                "global",
                "software",
                (
                    "Turns data into decision support through analysis, reporting, "
                    "and stakeholder context."
                ),
            ),
        ],
    )
    op.bulk_insert(competencies, _competencies())


def _role(
    role_id: UUID,
    slug: str,
    title: str,
    seniority: str,
    industry: str,
    domain: str,
    location_scope: str,
    company_type: str,
    description: str,
) -> dict[str, object]:
    return {
        "id": role_id,
        "taxonomy_version_id": TAXONOMY_ID,
        "slug": slug,
        "title": title,
        "seniority": seniority,
        "industry": industry,
        "domain": domain,
        "location_scope": location_scope,
        "company_type": company_type,
        "description": description,
        "version": 1,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def _competencies() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def add(
        offset: int,
        role_id: UUID,
        dimension: str,
        label: str,
        description: str,
        importance: str,
        skill_keywords: list[str],
        evidence_keywords: list[str],
        transferable_keywords: list[str],
        adjacent_keywords: list[str],
    ) -> None:
        rows.append(
            {
                "id": UUID(f"00000000-0000-4000-8000-{500 + len(rows) + 1:012d}"),
                "role_id": role_id,
                "dimension": dimension,
                "label": label,
                "description": description,
                "importance": importance,
                "skill_keywords": skill_keywords,
                "evidence_keywords": evidence_keywords,
                "transferable_keywords": transferable_keywords,
                "adjacent_keywords": adjacent_keywords,
                "sort_order": offset,
            }
        )

    add(
        10,
        PRODUCT_MANAGER_ID,
        "core_competency",
        "Customer discovery",
        "Evidence of user research, problem discovery, or customer interviews.",
        "required",
        ["user research", "customer discovery", "interviews"],
        ["discovery", "research", "customer"],
        ["stakeholder research", "support analysis"],
        ["requirements gathering"],
    )
    add(
        20,
        PRODUCT_MANAGER_ID,
        "responsibility_alignment",
        "Roadmap prioritization",
        "Evidence of prioritizing a backlog or roadmap with trade-off reasoning.",
        "required",
        ["roadmap", "prioritization", "backlog"],
        ["prioritized", "roadmap", "backlog"],
        ["planning", "delivery"],
        ["project sequencing"],
    )
    add(
        30,
        PRODUCT_MANAGER_ID,
        "seniority_alignment",
        "Cross-functional ownership",
        "Evidence of owning decisions across design, engineering, and business partners.",
        "required",
        ["cross-functional", "ownership", "product strategy"],
        ["owned", "led", "aligned"],
        ["program management", "stakeholder management"],
        ["team coordination"],
    )
    add(
        40,
        PRODUCT_MANAGER_ID,
        "leadership_evidence",
        "Influence without authority",
        "Evidence of aligning stakeholders or leading through influence.",
        "helpful",
        ["stakeholder management", "leadership", "influence"],
        ["aligned", "influenced", "facilitated"],
        ["mentoring", "workshop"],
        ["communication"],
    )
    add(
        50,
        PRODUCT_MANAGER_ID,
        "business_impact",
        "Measured product outcome",
        "Evidence of a shipped outcome tied to adoption, revenue, retention, or efficiency.",
        "required",
        ["product metrics", "business impact", "analytics"],
        ["revenue", "adoption", "retention", "conversion", "reduced"],
        ["reporting", "operations"],
        ["launch"],
    )
    add(
        60,
        PRODUCT_MANAGER_ID,
        "technical_skills",
        "Technical collaboration",
        "Evidence of partnering with engineering on APIs, data, or technical constraints.",
        "helpful",
        ["api", "data", "technical collaboration"],
        ["engineering", "api", "technical"],
        ["systems thinking", "analytics"],
        ["implementation"],
    )
    add(
        70,
        PRODUCT_MANAGER_ID,
        "domain_knowledge",
        "Product domain context",
        "Evidence of software product, platform, or SaaS domain knowledge.",
        "helpful",
        ["saas", "platform", "product"],
        ["platform", "software", "saas"],
        ["customer operations"],
        ["digital product"],
    )
    add(
        80,
        PRODUCT_MANAGER_ID,
        "education_certification",
        "Product learning signal",
        "Evidence of relevant product, analytics, design, or business education.",
        "helpful",
        ["product management", "analytics", "design"],
        ["certification", "course", "degree"],
        ["business analysis"],
        ["training"],
    )

    add(
        10,
        SOFTWARE_ENGINEER_ID,
        "core_competency",
        "Production programming",
        "Evidence of building maintained software in a programming language or framework.",
        "required",
        ["python", "typescript", "javascript", "software engineering"],
        ["built", "implemented", "developed", "shipped"],
        ["automation", "scripting"],
        ["technical support"],
    )
    add(
        20,
        SOFTWARE_ENGINEER_ID,
        "technical_skills",
        "Testing and quality",
        "Evidence of unit, integration, end-to-end, or automated quality checks.",
        "required",
        ["testing", "pytest", "vitest", "playwright", "quality"],
        ["tested", "coverage", "regression"],
        ["validation", "qa"],
        ["review"],
    )
    add(
        30,
        SOFTWARE_ENGINEER_ID,
        "responsibility_alignment",
        "Delivery collaboration",
        "Evidence of working with product, design, or peers to deliver software.",
        "required",
        ["collaboration", "delivery", "agile"],
        ["collaborated", "delivered", "released"],
        ["project management"],
        ["handoff"],
    )
    add(
        40,
        SOFTWARE_ENGINEER_ID,
        "seniority_alignment",
        "Independent implementation",
        "Evidence of owning implementation choices for a bounded feature or service.",
        "required",
        ["architecture", "ownership", "design"],
        ["owned", "designed", "refactored"],
        ["technical planning"],
        ["debugging"],
    )
    add(
        50,
        SOFTWARE_ENGINEER_ID,
        "business_impact",
        "Operational impact",
        "Evidence of reliability, performance, cost, or workflow improvement.",
        "helpful",
        ["performance", "reliability", "automation"],
        ["improved", "reduced", "increased", "scaled"],
        ["operations", "analytics"],
        ["support"],
    )
    add(
        60,
        SOFTWARE_ENGINEER_ID,
        "domain_knowledge",
        "Product context",
        "Evidence of understanding product requirements and user context.",
        "helpful",
        ["requirements", "product", "user"],
        ["requirements", "user", "customer"],
        ["stakeholder"],
        ["business"],
    )
    add(
        70,
        SOFTWARE_ENGINEER_ID,
        "leadership_evidence",
        "Peer enablement",
        "Evidence of mentoring, review, documentation, or team enablement.",
        "helpful",
        ["mentoring", "code review", "documentation"],
        ["reviewed", "documented", "mentored"],
        ["training"],
        ["communication"],
    )
    add(
        80,
        SOFTWARE_ENGINEER_ID,
        "education_certification",
        "Computer science foundation",
        "Evidence of software, computer science, or engineering education.",
        "helpful",
        ["computer science", "software engineering"],
        ["degree", "certification", "course"],
        ["technical training"],
        ["bootcamp"],
    )

    add(
        10,
        DATA_ANALYST_ID,
        "core_competency",
        "Data analysis",
        "Evidence of extracting insight from datasets with clear questions and methods.",
        "required",
        ["data analysis", "analytics", "sql"],
        ["analyzed", "insight", "dataset"],
        ["research", "reporting"],
        ["spreadsheet"],
    )
    add(
        20,
        DATA_ANALYST_ID,
        "technical_skills",
        "Querying and reporting",
        "Evidence of SQL, dashboards, metrics, or recurring reports.",
        "required",
        ["sql", "dashboard", "reporting", "tableau", "power bi"],
        ["dashboard", "sql", "report", "metric"],
        ["excel", "spreadsheet"],
        ["visualization"],
    )
    add(
        30,
        DATA_ANALYST_ID,
        "responsibility_alignment",
        "Stakeholder decision support",
        "Evidence of translating analytical findings for decisions.",
        "required",
        ["stakeholder", "decision support", "communication"],
        ["recommended", "presented", "decision"],
        ["user research"],
        ["summary"],
    )
    add(
        40,
        DATA_ANALYST_ID,
        "business_impact",
        "Measured analytical impact",
        "Evidence that analysis improved revenue, cost, conversion, or process decisions.",
        "required",
        ["business impact", "metrics", "measurement"],
        ["increased", "reduced", "saved", "conversion"],
        ["operations", "experiment"],
        ["tracking"],
    )
    add(
        50,
        DATA_ANALYST_ID,
        "seniority_alignment",
        "Analytical ownership",
        "Evidence of independently defining analysis scope or owning a reporting area.",
        "helpful",
        ["ownership", "analytics strategy", "requirements"],
        ["owned", "defined", "designed"],
        ["project management"],
        ["coordination"],
    )
    add(
        60,
        DATA_ANALYST_ID,
        "domain_knowledge",
        "Business domain fluency",
        "Evidence of relevant product, operations, finance, or go-to-market context.",
        "helpful",
        ["product analytics", "operations", "finance", "growth"],
        ["product", "operations", "finance", "growth"],
        ["customer"],
        ["process"],
    )
    add(
        70,
        DATA_ANALYST_ID,
        "leadership_evidence",
        "Analytical enablement",
        "Evidence of teaching, documentation, or improving how others use data.",
        "helpful",
        ["enablement", "documentation", "training"],
        ["documented", "trained", "enabled"],
        ["mentoring"],
        ["communication"],
    )
    add(
        80,
        DATA_ANALYST_ID,
        "education_certification",
        "Analytics foundation",
        "Evidence of statistics, analytics, economics, data, or business education.",
        "helpful",
        ["statistics", "analytics", "economics", "data"],
        ["degree", "certification", "course"],
        ["quantitative"],
        ["training"],
    )
    return rows
