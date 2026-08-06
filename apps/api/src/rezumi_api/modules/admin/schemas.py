"""Pydantic schemas for the admin system module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class AdminSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


class SystemMetricsResponse(AdminSchema):
    environment: str
    service_version: str
    status: str
    active_users_count: int
    total_resumes_count: int
    total_applications_count: int
    subscriptions_by_tier: dict[str, int]
    system_health: dict[str, str]


class DeadLetterJobResponse(AdminSchema):
    id: str
    job_type: str
    user_id: str
    attempts: int
    max_attempts: int
    last_error: str | None
    failed_at: datetime


class DeadLetterJobListResponse(AdminSchema):
    jobs: list[DeadLetterJobResponse]


class JobRetryResponse(AdminSchema):
    job_id: str
    status: str
    message: str
