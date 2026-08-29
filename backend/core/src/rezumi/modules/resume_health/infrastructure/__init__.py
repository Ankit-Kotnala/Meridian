"""Resume Health infrastructure adapters."""

from .extractors import LocalDocumentExtractor, LocalDocumentTextExtractor
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
from .isolated_extractor import IsolatedDocumentExtractor
from .layout import LocalLayoutAnalyzer
from .malware import ClamAvOptions, ClamAvScanner
from .mongodb_store import DisabledParsedResumeDocumentStore, MongoParsedResumeDocumentStore
from .queue import CeleryJobPublisher, CeleryPublisherOptions
from .repository import SqlAlchemyResumeUnitOfWorkFactory
from .security import HmacGuestCapabilityManager, SystemClock
from .semantic_parser import LocalResumeParserProvider
from .storage import S3ObjectStorage, S3Options

__all__ = [
    "CeleryJobPublisher",
    "CeleryPublisherOptions",
    "ClamAvOptions",
    "ClamAvScanner",
    "DisabledOcrProvider",
    "DisabledParsedResumeDocumentStore",
    "FakeDocumentExtractor",
    "FakeJobPublisher",
    "FakeMalwareScanner",
    "FixedClock",
    "HmacGuestCapabilityManager",
    "InMemoryObjectStorage",
    "InMemoryResumeState",
    "InMemoryResumeUnitOfWorkFactory",
    "IsolatedDocumentExtractor",
    "LocalDocumentExtractor",
    "LocalDocumentTextExtractor",
    "LocalLayoutAnalyzer",
    "LocalResumeParserProvider",
    "MongoParsedResumeDocumentStore",
    "S3ObjectStorage",
    "S3Options",
    "SqlAlchemyResumeUnitOfWorkFactory",
    "SystemClock",
]
