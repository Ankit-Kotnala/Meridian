"""Resume Health infrastructure adapters."""

from .extractors import LocalDocumentExtractor
from .fakes import (
    DisabledOcrProvider,
    FakeDocumentExtractor,
    FakeJobPublisher,
    FakeMalwareScanner,
    FixedClock,
    InMemoryObjectStorage,
    InMemoryResumeState,
    InMemoryResumeUnitOfWorkFactory,
)
from .malware import ClamAvOptions, ClamAvScanner
from .queue import CeleryJobPublisher, CeleryPublisherOptions
from .repository import SqlAlchemyResumeUnitOfWorkFactory
from .security import HmacGuestCapabilityManager, SystemClock
from .storage import S3ObjectStorage, S3Options

__all__ = [
    "CeleryJobPublisher",
    "CeleryPublisherOptions",
    "ClamAvOptions",
    "ClamAvScanner",
    "DisabledOcrProvider",
    "FakeDocumentExtractor",
    "FakeJobPublisher",
    "FakeMalwareScanner",
    "FixedClock",
    "HmacGuestCapabilityManager",
    "InMemoryObjectStorage",
    "InMemoryResumeState",
    "InMemoryResumeUnitOfWorkFactory",
    "LocalDocumentExtractor",
    "S3ObjectStorage",
    "S3Options",
    "SqlAlchemyResumeUnitOfWorkFactory",
    "SystemClock",
]
