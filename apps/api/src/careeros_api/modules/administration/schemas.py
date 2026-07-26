"""Strict wire schemas for protected platform administration."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class AdminSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


class AdminSystemTotalsResponse(AdminSchema):
    users_active: Annotated[int, Field(ge=0)]
    users_disabled: Annotated[int, Field(ge=0)]
    organizations_active: Annotated[int, Field(ge=0)]
    subscriptions_active: Annotated[int, Field(ge=0)]
    queued_jobs: Annotated[int, Field(ge=0)]
    retry_wait_jobs: Annotated[int, Field(ge=0)]
    running_jobs: Annotated[int, Field(ge=0)]
    dead_letter_jobs: Annotated[int, Field(ge=0)]


class AdminSystemResponse(AdminSchema):
    generated_at: datetime
    totals: AdminSystemTotalsResponse
    audit_chain_valid: bool


class AdminCatalogResponse(AdminSchema):
    generated_at: datetime
    configured_plans: Annotated[int, Field(ge=0, le=4)]
    owner_decision_required_plans: Annotated[int, Field(ge=0, le=4)]
    enabled_feature_flags: list[str] = Field(max_length=100)
    role_taxonomy_versions: Annotated[int, Field(ge=0)]
    active_role_definitions: Annotated[int, Field(ge=0)]
    resume_template_keys: list[str] = Field(max_length=5)


class AdminDeadLetterResponse(AdminSchema):
    kind: str
    id: UUID
    status: str
    safe_error_code: str | None
    attempts: Annotated[int, Field(ge=0)]
    max_attempts: Annotated[int, Field(ge=1)]
    occurred_at: datetime
    retry_supported: bool


class AdminDeadLetterPageResponse(AdminSchema):
    items: list[AdminDeadLetterResponse] = Field(max_length=100)
    next_cursor: str | None


class AdminRetryRequest(AdminSchema):
    reason: Annotated[str, Field(min_length=12, max_length=500)]


class AdminRetryResponse(AdminSchema):
    kind: str
    id: UUID
    status: str
    replayed: bool


AdminRole = Literal[
    "operations_viewer",
    "job_operator",
    "catalog_auditor",
    "security_auditor",
]
AdminCapability = Literal[
    "system.read",
    "jobs.read",
    "jobs.retry",
    "catalog.read",
    "audit.read",
    "audit.verify",
]


class AdminAuditEventResponse(AdminSchema):
    id: UUID
    sequence: Annotated[int, Field(ge=1)]
    actor_reference: Annotated[str, Field(min_length=64, max_length=64)]
    actor_role: AdminRole | None
    capability: AdminCapability
    action: str
    outcome: Literal["accepted", "success", "denied", "failed"]
    reason: str
    target_kind: str | None
    target_id: UUID | None
    request_id: str
    trace_id: str
    previous_hash: Annotated[str, Field(min_length=64, max_length=64)]
    event_hash: Annotated[str, Field(min_length=64, max_length=64)]
    occurred_at: datetime


class AdminAuditPageResponse(AdminSchema):
    items: list[AdminAuditEventResponse] = Field(max_length=100)
    next_cursor: str | None


class AdminAuditIntegrityResponse(AdminSchema):
    valid: bool
