"""Career Analytics infrastructure adapters."""

from .identifiers import SystemClock, Uuid4IdentifierFactory
from .repository import (
    SqlAlchemyCareerAnalyticsUnitOfWork,
    SqlAlchemyCareerAnalyticsUnitOfWorkFactory,
)
from .sources import (
    ApplicationWorkspaceAnalyticsSource,
    CareerRecordAnalyticsProvider,
    CompositeSupplementalAnalyticsSource,
    RoleReadinessAnalyticsProvider,
)

__all__ = [
    "ApplicationWorkspaceAnalyticsSource",
    "CareerRecordAnalyticsProvider",
    "CompositeSupplementalAnalyticsSource",
    "RoleReadinessAnalyticsProvider",
    "SqlAlchemyCareerAnalyticsUnitOfWork",
    "SqlAlchemyCareerAnalyticsUnitOfWorkFactory",
    "SystemClock",
    "Uuid4IdentifierFactory",
]
