"""Persistence and runtime adapters for the Job Match bounded context."""

from .career_record_provider import CareerRecordJobMatchSnapshotProvider
from .identifiers import SystemClock, UuidIdentifierFactory
from .repository import SqlAlchemyJobMatchUnitOfWorkFactory
from .role_context_provider import RoleReadinessRoleContextProvider
from .url_importer import SafeUrlJobImportProvider, UrlImportOptions

__all__ = [
    "CareerRecordJobMatchSnapshotProvider",
    "RoleReadinessRoleContextProvider",
    "SafeUrlJobImportProvider",
    "SqlAlchemyJobMatchUnitOfWorkFactory",
    "SystemClock",
    "UrlImportOptions",
    "UuidIdentifierFactory",
]
