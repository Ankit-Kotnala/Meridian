"""Transport-neutral commands and views for Resume Health use cases."""

import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

from rezumi.modules.resume_health.domain import (
    AnalysisStatus,
    CanonicalResume,
    DatePrecision,
    DocumentStatus,
    FindingSeverity,
    JobKind,
    JobStatus,
    MalwareStatus,
    OwnerScope,
    ProcessingStage,
    ResumeMediaType,
    SemanticEntityKind,
    SemanticFieldType,
)


@dataclass(frozen=True, slots=True)
class DocumentLimits:
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20
    max_archive_entries: int = 2_000
    max_archive_uncompressed_bytes: int = 50 * 1024 * 1024
    max_archive_ratio: int = 100
    max_extracted_characters: int = 500_000
    max_extracted_blocks: int = 5_000
    max_serialized_artifact_bytes: int = 2 * 1024 * 1024
    processing_timeout_seconds: float = 120.0
    temp_root: Path = field(
        default_factory=lambda: Path("/tmp/rezumi").resolve() / "rezumi"
    )

    def __post_init__(self) -> None:
        if self.max_upload_bytes < 1 or self.max_pdf_pages < 1:
            raise ValueError("document limits must be positive")
        if self.max_archive_entries < 1 or self.max_archive_uncompressed_bytes < 1:
            raise ValueError("archive limits must be positive")
        if (
            self.max_archive_ratio < 1
            or self.max_extracted_characters < 1
            or self.max_extracted_blocks < 1
            or self.max_serialized_artifact_bytes < 1
        ):
            raise ValueError("extraction limits must be positive")
        if self.processing_timeout_seconds <= 0:
            raise ValueError("processing timeout must be positive")
        if not self.temp_root.is_absolute():
            raise ValueError("temporary root must be absolute")


@dataclass(frozen=True, slots=True)
class CreateUploadIntent:
    display_filename: str
    media_type: ResumeMediaType
    expected_size: int


@dataclass(frozen=True, slots=True)
class StorageUploadTarget:
    method: str
    url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class UploadIntentView:
    id: UUID
    display_filename: str
    media_type: ResumeMediaType
    expected_size: int
    expires_at: datetime
    target: StorageUploadTarget


@dataclass(frozen=True, slots=True)
class IssuedGuestSession:
    session_id: UUID
    capability_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FinalizedUpload:
    document_id: UUID
    job_id: UUID
    document_status: DocumentStatus
    job_status: JobStatus


@dataclass(frozen=True, slots=True)
class DocumentView:
    id: UUID
    display_filename: str
    media_type: ResumeMediaType
    size_bytes: int
    status: DocumentStatus
    malware_status: MalwareStatus
    page_count: int | None
    safe_error_code: str | None
    retention_expires_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    current_snapshot_id: UUID | None = None
    latest_analysis_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ProcessingJobView:
    id: UUID
    document_id: UUID
    kind: JobKind
    status: JobStatus
    stage: ProcessingStage
    progress: int | None
    attempts: int
    max_attempts: int
    safe_error_code: str | None
    retryable: bool
    cancellation_requested: bool
    created_at: datetime
    updated_at: datetime
    result_id: UUID | None


@dataclass(frozen=True, slots=True)
class SourceSpanView:
    page: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    kind: str
    text: str
    confidence_basis_points: int
    spans: tuple[SourceSpanView, ...]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    plain_text: str
    reading_order: tuple[ExtractedBlock, ...]
    page_count: int
    image_only: bool
    warnings: tuple[str, ...]
    parser_version: str
    layout_signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalSnapshotView:
    id: UUID
    document_id: UUID
    revision: int
    resume: CanonicalResume
    original_resume: CanonicalResume
    parser_version: str
    corrected_by_user: bool
    created_at: datetime
    based_on_snapshot_id: UUID | None


@dataclass(frozen=True, slots=True)
class CorrectionOperation:
    block_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class ConfirmSemanticField:
    field_id: UUID


@dataclass(frozen=True, slots=True)
class CorrectSemanticField:
    field_id: UUID
    value: str
    date_precision: DatePrecision | None = None


@dataclass(frozen=True, slots=True)
class AddSemanticField:
    entity_id: UUID
    name: str
    field_type: SemanticFieldType
    value: str
    date_precision: DatePrecision | None = None


@dataclass(frozen=True, slots=True)
class RemoveSemanticField:
    field_id: UUID


@dataclass(frozen=True, slots=True)
class SemanticFieldReclassification:
    field_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class ReclassifySemanticEntity:
    entity_id: UUID
    kind: SemanticEntityKind
    fields: tuple[SemanticFieldReclassification, ...]


@dataclass(frozen=True, slots=True)
class NewSemanticField:
    name: str
    field_type: SemanticFieldType
    value: str
    date_precision: DatePrecision | None = None


@dataclass(frozen=True, slots=True)
class AddSemanticEntity:
    kind: SemanticEntityKind
    fields: tuple[NewSemanticField, ...]


@dataclass(frozen=True, slots=True)
class RemoveSemanticEntity:
    entity_id: UUID


type SemanticReviewOperation = (
    ConfirmSemanticField
    | CorrectSemanticField
    | AddSemanticField
    | RemoveSemanticField
    | ReclassifySemanticEntity
    | AddSemanticEntity
    | RemoveSemanticEntity
)


@dataclass(frozen=True, slots=True)
class ScoreComponentView:
    code: str
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str


@dataclass(frozen=True, slots=True)
class FeatureContributionView:
    component_code: str
    feature_code: str
    feature_value_basis_points: int
    weight_basis_points: int
    contribution_basis_points: int


@dataclass(frozen=True, slots=True)
class FindingView:
    code: str
    severity: FindingSeverity
    component_code: str
    message: str
    quick_win: bool
    sort_order: int


@dataclass(frozen=True, slots=True)
class AnalysisView:
    id: UUID
    document_id: UUID
    snapshot_id: UUID
    status: AnalysisStatus
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    feature_values: dict[str, int | bool]
    feature_set_hash: bytes
    raw_score_basis_points: int | None
    display_score: int | None
    components: tuple[ScoreComponentView, ...]
    feature_contributions: tuple[FeatureContributionView, ...]
    findings: tuple[FindingView, ...]
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    size_bytes: int
    media_type: str | None


@dataclass(frozen=True, slots=True)
class MalwareScanResult:
    clean: bool
    infected: bool
    signature: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    job_id: UUID
    status: JobStatus
    retryable: bool
    safe_error_code: str | None


@dataclass(frozen=True, slots=True)
class CapabilitySecret:
    id: UUID
    encoded: str
    digest: bytes


@dataclass(frozen=True, slots=True)
class DownloadedObject:
    path: Path
    sha256: bytes
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ResumeRequestContext:
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class ClaimGuestDocument:
    policy_version: str
    consent: bool


@dataclass(frozen=True, slots=True)
class OutboxDispatchResult:
    published: int
    failed: int
    dead_lettered: int = 0


@dataclass(frozen=True, slots=True)
class JobReconciliationResult:
    requeued: int
    dead_lettered: int


@dataclass(frozen=True, slots=True)
class CleanupResult:
    expired_uploads: int
    queued_guest_deletions: int
    revoked_guest_sessions: int
    object_cleanups_completed: int = 0
    object_cleanup_failures: int = 0
    object_cleanup_dead_letters: int = 0


def owner_scope(user_id: UUID | None, guest_session_id: UUID | None) -> OwnerScope:
    return OwnerScope(user_id=user_id, guest_session_id=guest_session_id)

