"""Public Role Readiness application contract."""

from ..domain import (
    RoleReadinessError,
    RoleReadinessUnavailable,
    RoleReadinessValidationError,
)
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
    RoleReadinessAnalyticsPoint,
    RoleReadinessAnalyticsSourceState,
    RoleReadinessAnalyticsWatermark,
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
    "RoleReadinessAnalyticsPoint",
    "RoleReadinessAnalyticsSourceState",
    "RoleReadinessAnalyticsWatermark",
    "RoleReadinessError",
    "RoleReadinessPolicy",
    "RoleReadinessService",
    "RoleReadinessUnavailable",
    "RoleReadinessUnitOfWork",
    "RoleReadinessUnitOfWorkFactory",
    "RoleReadinessValidationError",
    "RoleReadinessView",
    "SaveRole",
    "SavedRoleView",
    "UpdateSavedRole",
]
