"""SQLAlchemy mappings for organization tenancy and delegated grants."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careeros.foundation.database import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')", name="status_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("id", "created_by_user_id", name="uq_organizations_id_creator"),
        Index("ix_organizations_created_by_user_id", "created_by_user_id"),
        Index("ix_organizations_status_updated", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'active'"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationMembershipModel(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','coach','member')",
            name="role_valid",
        ),
        CheckConstraint(
            "status IN ('active','invited','suspended','left')",
            name="status_valid",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status <> 'active' OR accepted_at IS NOT NULL)"
            " AND (status <> 'suspended' OR suspended_at IS NOT NULL)"
            " AND (status <> 'left' OR left_at IS NOT NULL)",
            name="state_timestamps_valid",
        ),
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_organization_id",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_organization_memberships_organization_id_id",
        ),
        Index(
            "ix_organization_memberships_organization_id",
            "organization_id",
        ),
        Index("ix_organization_memberships_user_id", "user_id"),
        Index("ix_organization_memberships_user_status", "user_id", "status"),
        Index(
            "ix_organization_memberships_org_status_role",
            "organization_id",
            "status",
            "role",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationInvitationModel(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','coach','member')",
            name="role_valid",
        ),
        CheckConstraint(
            "status IN ('pending_delivery','pending','accepted','revoked','expired',"
            "'delivery_dead_lettered')",
            name="status_valid",
        ),
        CheckConstraint(
            "octet_length(invited_email_digest) = 32",
            name="email_digest_length",
        ),
        CheckConstraint(
            "token_hash IS NULL OR octet_length(token_hash) = 32",
            name="token_hash_length",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("created_at < expires_at", name="expiry_valid"),
        CheckConstraint(
            "(status <> 'pending' OR token_hash IS NOT NULL)"
            " AND (status = 'accepted') ="
            " (accepted_by_user_id IS NOT NULL AND accepted_at IS NOT NULL)"
            " AND (status = 'revoked') = (revoked_at IS NOT NULL)",
            name="state_links_valid",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_organization_invitations_organization_id",
        ),
        Index(
            "ix_organization_invitations_org_status_expiry",
            "organization_id",
            "status",
            "expires_at",
        ),
        Index(
            "ix_organization_invitations_email_status",
            "organization_id",
            "invited_email_digest",
            "status",
        ),
        Index(
            "uq_organization_invitations_open_email",
            "organization_id",
            "invited_email_digest",
            unique=True,
            postgresql_where=text(
                "status IN ('pending_delivery','pending','delivery_dead_lettered')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    invited_email_normalized: Mapped[str] = mapped_column(String(254), nullable=False)
    invited_email_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    invited_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationAccessGrantModel(Base):
    __tablename__ = "organization_access_grants"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('coaching','career_services','program_support')",
            name="purpose_valid",
        ),
        CheckConstraint(
            "scope IN ('career_profile_summary','resume_health_summary',"
            "'role_readiness_summary','application_status','career_growth_summary',"
            "'collaboration_comment')",
            name="scope_valid",
        ),
        CheckConstraint(
            "status IN ('active','revoked','expired')",
            name="status_valid",
        ),
        CheckConstraint("subject_user_id <> grantee_user_id", name="distinct_users"),
        CheckConstraint(
            "granted_by_user_id = subject_user_id",
            name="subject_is_grantor",
        ),
        CheckConstraint("created_at < expires_at", name="expiry_valid"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)",
            name="revocation_state_valid",
        ),
        ForeignKeyConstraint(
            ["organization_id", "subject_user_id"],
            [
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_organization_access_grants_subject_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "grantee_user_id"],
            [
                "organization_memberships.organization_id",
                "organization_memberships.user_id",
            ],
            name="fk_organization_access_grants_grantee_membership",
            ondelete="CASCADE",
        ),
        Index(
            "ix_organization_access_grants_subject_status",
            "organization_id",
            "subject_user_id",
            "status",
        ),
        Index(
            "ix_organization_access_grants_grantee_status",
            "organization_id",
            "grantee_user_id",
            "status",
        ),
        Index(
            "uq_organization_access_grants_active_scope",
            "organization_id",
            "subject_user_id",
            "grantee_user_id",
            "scope",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    subject_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    grantee_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    granted_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationInvitationOutboxModel(Base):
    __tablename__ = "organization_invitation_outbox"
    __table_args__ = (
        CheckConstraint(
            "attempts BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 20",
            name="attempts_valid",
        ),
        CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="lease_pair_valid",
        ),
        CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="terminal_state_valid",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invitation_id"],
            [
                "organization_invitations.organization_id",
                "organization_invitations.id",
            ],
            name="fk_organization_invitation_outbox_invitation",
            ondelete="CASCADE",
        ),
        UniqueConstraint("invitation_id", name="uq_organization_invitation_outbox_invitation"),
        Index(
            "ix_organization_invitation_outbox_pending",
            "published_at",
            "dead_lettered_at",
            "next_attempt_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationIdempotencyModel(Base):
    __tablename__ = "organization_idempotency_records"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('create_organization','invite_member','accept_invitation',"
            "'create_grant','revoke_grant')",
            name="operation_valid",
        ),
        CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name="request_fingerprint_length",
        ),
        UniqueConstraint(
            "actor_user_id",
            "operation",
            "idempotency_key",
            name="uq_organization_idempotency_actor_operation_key",
        ),
        Index(
            "ix_organization_idempotency_actor_created",
            "actor_user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrganizationAuditEventModel(Base):
    __tablename__ = "organization_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('organization_created','organization_updated',"
            "'invitation_created','invitation_delivered','invitation_delivery_failed',"
            "'invitation_accepted','invitation_revoked','member_suspended',"
            "'grant_created','grant_revoked')",
            name="action_valid",
        ),
        Index(
            "ix_organization_audit_events_org_occurred",
            "organization_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_organization_audit_events_actor_occurred",
            "actor_user_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    subject_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
