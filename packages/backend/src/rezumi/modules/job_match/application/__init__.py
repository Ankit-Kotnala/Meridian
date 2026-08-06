"""Public Job Match application contract."""

from ..domain import JobMatchNotFound
from .models import (
    AnalysisRecord,
    CreateJob,
    ImportedJobSource,
    ImportJob,
    JobFilter,
    JobMatchView,
    JobRecord,
    OpportunityPriorityView,
    Page,
    PageCursor,
    PagedResult,
    PrioritizeOpportunity,
    RequestContext,
    UpdateJob,
)
from .ports import (
    CareerSnapshotProvider,
    Clock,
    IdentifierFactory,
    JobImportProvider,
    JobMatchUnitOfWork,
    JobMatchUnitOfWorkFactory,
    RoleContextProvider,
)
from .service import JobMatchPolicy, JobMatchService

__all__ = [
    "AnalysisRecord",
    "CareerSnapshotProvider",
    "Clock",
    "CreateJob",
    "IdentifierFactory",
    "ImportJob",
    "ImportedJobSource",
    "JobFilter",
    "JobImportProvider",
    "JobMatchNotFound",
    "JobMatchPolicy",
    "JobMatchService",
    "JobMatchUnitOfWork",
    "JobMatchUnitOfWorkFactory",
    "JobMatchView",
    "JobRecord",
    "OpportunityPriorityView",
    "Page",
    "PageCursor",
    "PagedResult",
    "PrioritizeOpportunity",
    "RequestContext",
    "RoleContextProvider",
    "UpdateJob",
]
