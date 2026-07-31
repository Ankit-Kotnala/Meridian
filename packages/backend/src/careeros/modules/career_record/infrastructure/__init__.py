"""Persistence adapters for the Career Record bounded context."""

from .attachment_admission import AttachmentAdmissionBridge
from .attachment_extractor import ATTACHMENT_PARSER_VERSION, BoundedAttachmentExtractor
from .attachment_repository import SqlAlchemyAttachmentUnitOfWorkFactory, SystemClock
from .attachment_scanner import AttachmentClamAvOptions, AttachmentClamAvScanner
from .attachment_storage import (
    AttachmentS3ObjectStorage,
    AttachmentS3Options,
)
from .identifiers import UuidIdentifierFactory
from .isolated_attachment_extractor import IsolatedAttachmentExtractor
from .repository import SqlAlchemyCareerRecordUnitOfWorkFactory
from .resume_health_source import ResumeHealthSourceQuery

__all__ = [
    "ATTACHMENT_PARSER_VERSION",
    "AttachmentAdmissionBridge",
    "AttachmentClamAvOptions",
    "AttachmentClamAvScanner",
    "AttachmentS3ObjectStorage",
    "AttachmentS3Options",
    "BoundedAttachmentExtractor",
    "IsolatedAttachmentExtractor",
    "ResumeHealthSourceQuery",
    "SqlAlchemyAttachmentUnitOfWorkFactory",
    "SqlAlchemyCareerRecordUnitOfWorkFactory",
    "SystemClock",
    "UuidIdentifierFactory",
]
