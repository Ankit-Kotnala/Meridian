"""Schemas for Phase 0 operational endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictResponse(BaseModel):
    """Prevent accidental API expansion through undeclared response fields."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponse):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class ComponentReadiness(StrictResponse):
    status: Literal["ok", "unavailable"]


class ReadinessResponse(StrictResponse):
    status: Literal["ready", "not_ready"]
    service: str
    version: str
    checks: dict[str, ComponentReadiness]


class MetaResponse(StrictResponse):
    service: str
    version: str
    api_version: Literal["v1"] = "v1"
    environment: str
    scoring_disclaimer: str
