"""Infrastructure adapters for Phase 8 application workspace."""

from .identifiers import SystemClock, UuidIdentifierFactory
from .repository import (
    SqlAlchemyApplicationWorkspaceUnitOfWork,
    SqlAlchemyApplicationWorkspaceUnitOfWorkFactory,
)
from .sources import (
    CareerRecordApplicationEvidenceSnapshotProvider,
    JobMatchApplicationSnapshotProvider,
    ResumeBuilderVersionSnapshotProvider,
)

__all__ = [
    "CareerRecordApplicationEvidenceSnapshotProvider",
    "JobMatchApplicationSnapshotProvider",
    "ResumeBuilderVersionSnapshotProvider",
    "SqlAlchemyApplicationWorkspaceUnitOfWork",
    "SqlAlchemyApplicationWorkspaceUnitOfWorkFactory",
    "SystemClock",
    "UuidIdentifierFactory",
]
