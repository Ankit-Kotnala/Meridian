"""Pydantic schemas for the admin system module."""

from datetime import datetime

from pydantic import BaseModel


class SystemMetricsResponse(BaseModel):
    environment: str
    service_version: str
    status: str
    active_users_count: int
    total_resumes_count: int
    total_applications_count: int
    subscriptions_by_tier: dict[str, int]
    system_health: dict[str, str]


class DeadLetterJobResponse(BaseModel):
    id: str
    job_type: str
    user_id: str
    attempts: int
    max_attempts: int
    last_error: str | None
    failed_at: datetime


class DeadLetterJobListResponse(BaseModel):
    jobs: list[DeadLetterJobResponse]


class JobRetryResponse(BaseModel):
    job_id: str
    status: str
    message: str
