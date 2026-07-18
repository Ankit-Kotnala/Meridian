"""Public Role Readiness application contract."""

from .models import (
    AnalysisRecord,
    AnalyzeRoleReadiness,
    Page,
    PagedResult,
    RequestContext,
    RoleComparisonEntry,
    RoleComparisonView,
    RoleDetail,
    RoleFilter,
    RoleReadinessView,
    SavedRoleView,
    SaveRole,
    UpdateSavedRole,
)
from .ports import (
    CareerSnapshotProvider,
    Clock,
    IdentifierFactory,
    RoleReadinessUnitOfWork,
    RoleReadinessUnitOfWorkFactory,
)
from .service import RoleReadinessPolicy, RoleReadinessService

__all__ = [
    "AnalysisRecord",
    "AnalyzeRoleReadiness",
    "CareerSnapshotProvider",
    "Clock",
    "IdentifierFactory",
    "Page",
    "PagedResult",
    "RequestContext",
    "RoleComparisonEntry",
    "RoleComparisonView",
    "RoleDetail",
    "RoleFilter",
    "RoleReadinessPolicy",
    "RoleReadinessService",
    "RoleReadinessUnitOfWork",
    "RoleReadinessUnitOfWorkFactory",
    "RoleReadinessView",
    "SaveRole",
    "SavedRoleView",
    "UpdateSavedRole",
]
