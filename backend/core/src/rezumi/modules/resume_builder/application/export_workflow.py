"""Durable, fenced resume export rendering and fidelity verification."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from rezumi.modules.resume_builder.domain import (
    ResumeAuditAction,
    ResumeBuilderAuditEvent,
    ResumeBuilderValidationError,
    ResumeExport,
    ResumeExportObjectCleanup,
    ResumeExportOperation,
    ResumeExportOutboxMessage,
    ResumeExportStatus,
    ResumeFidelityManifest,
    ResumeFormat,
    ResumeVerificationReport,
    ResumeVerificationStatus,
    ResumeVersion,
    build_fidelity_manifest,
    fidelity_manifest_payload,
    fidelity_manifest_sha256,
    manifest_grounding_failures,
    normalize_fidelity_match_text,
    normalize_text,
)

from .models import (
    ExportObjectCleanupResult,
    ExportOutboxDispatchResult,
    ExportProcessingOutcome,
    ExportReconciliationResult,
    ExtractedDocumentText,
    RenderedResume,
)
from .ports import (
    Clock,
    IdentifierFactory,
    ResumeBuilderUnitOfWork,
    ResumeBuilderUnitOfWorkFactory,
    ResumeDocumentExtractor,
    ResumeExportJobPublisher,
    ResumeObjectStorage,
    ResumeRenderer,
)
from .service import validate_resume_version, version_provenance_failures


@dataclass(frozen=True, slots=True)
class ResumeExportWorkerPolicy:
    max_export_bytes: int = 8 * 1024 * 1024
    execution_lease_seconds: int = 330
    retry_delay_seconds: int = 30
    outbox_lease_seconds: int = 30
    outbox_max_attempts: int = 5
    reconciliation_stale_seconds: int = 300
    orphan_cleanup_grace_seconds: int = 300
    temp_root: Path | None = None

    def __post_init__(self) -> None:
        if self.max_export_bytes < 1:
            raise ValueError("resume export byte limit must be positive")
        if self.execution_lease_seconds < 1:
            raise ValueError("resume export lease must be positive")
        if self.retry_delay_seconds < 1 or self.outbox_lease_seconds < 1:
            raise ValueError("resume export retry and outbox leases must be positive")
        if self.outbox_max_attempts < 1:
            raise ValueError("resume export outbox attempts must be positive")
        if self.reconciliation_stale_seconds < 1:
            raise ValueError("resume export stale interval must be positive")
        if self.orphan_cleanup_grace_seconds < 1:
            raise ValueError("resume export orphan cleanup grace must be positive")
        if self.temp_root is not None and not self.temp_root.is_absolute():
            raise ValueError("resume export temporary root must be absolute")


@dataclass(frozen=True, slots=True)
class _ExecutionLease:
    export: ResumeExport
    version: ResumeVersion
    token_hash: str


@dataclass(frozen=True, slots=True)
class _CleanupLease:
    export: ResumeExport
    token_hash: str


class ResumeExportProcessor:
    """Claim, render, independently verify, and durably transition one export."""

    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        renderer: ResumeRenderer,
        extractor: ResumeDocumentExtractor,
        storage: ResumeObjectStorage,
        policy: ResumeExportWorkerPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._renderer = renderer
        self._extractor = extractor
        self._storage = storage
        self._policy = policy or ResumeExportWorkerPolicy()

    async def process(self, export_id: UUID, execution_token: str) -> ExportProcessingOutcome:
        token_hash = hashlib.sha256(execution_token.encode("utf-8")).hexdigest()
        lease = await self._claim(export_id, token_hash)
        if isinstance(lease, ExportProcessingOutcome):
            return lease
        object_key = _object_key(lease.export)
        write_attempted = False
        candidate_cleaned = True
        stored = False
        transition_started = False
        try:
            manifest = build_fidelity_manifest(lease.version)
            try:
                validate_resume_version(lease.version)
            except ResumeBuilderValidationError:
                transition_started = True
                return await self._block_invalid(
                    lease,
                    tuple(
                        dict.fromkeys(
                            (
                                "unsupported_version_content",
                                *manifest_grounding_failures(manifest),
                            )
                        )
                    ),
                    candidate_cleaned=True,
                )
            pin_failures = _pin_failures(lease.export, manifest)
            rendered = self._renderer.render(
                lease.version,
                fmt=lease.export.format.value,
            )
            if len(rendered.content) > self._policy.max_export_bytes:
                raise ResumeBuilderValidationError("rendered export exceeds maximum size")
            digest = hashlib.sha256(rendered.content).hexdigest()
            write_attempted = True
            candidate_cleaned = False
            await self._storage.put_bytes(object_key, rendered.content, rendered.media_type)
            stored = True
            verification = await self._verify(
                lease.version,
                lease.export,
                manifest,
                rendered,
                digest,
                pin_failures=pin_failures,
            )
            if verification.status is ResumeVerificationStatus.FAILED:
                candidate_cleaned = await self._try_delete_candidate(object_key)
                stored = False
            transition_started = True
            return await self._complete(
                lease,
                rendered,
                verification,
                object_key if stored else None,
                candidate_cleaned=candidate_cleaned,
            )
        except ResumeBuilderValidationError:
            if transition_started:
                return await self._fail(
                    lease,
                    "export_state_transition_failed",
                    candidate_cleaned=candidate_cleaned,
                )
            if write_attempted:
                candidate_cleaned = await self._try_delete_candidate(object_key)
            transition_started = True
            return await self._block_invalid(
                lease,
                ("unsupported_rendered_output",),
                candidate_cleaned=candidate_cleaned,
            )
        except Exception as exc:
            safe_error_code = _safe_error_code(exc)
            if not transition_started and write_attempted:
                candidate_cleaned = await self._try_delete_candidate(object_key)
                if not candidate_cleaned:
                    safe_error_code = "partial_object_cleanup_scheduled"
            return await self._fail(
                lease,
                safe_error_code,
                candidate_cleaned=candidate_cleaned,
            )

    async def _try_delete_candidate(self, object_key: str) -> bool:
        try:
            await self._storage.delete(object_key)
        except Exception:
            return False
        return True

    async def _block_invalid(
        self,
        lease: _ExecutionLease,
        critical_failures: tuple[str, ...],
        *,
        candidate_cleaned: bool,
    ) -> ExportProcessingOutcome:
        """Persist deterministic content failures as blocked, never as retries."""

        now = self._clock.now()
        grounding_codes = ["unsupported_content_blocked"]
        if any(value.startswith("numeric_grounding_missing:") for value in critical_failures):
            grounding_codes.append("numeric_grounding_failed")
        report = ResumeVerificationReport(
            id=self._ids.new(),
            owner_user_id=lease.version.owner_user_id,
            export_id=lease.export.id,
            version_id=lease.version.id,
            status=ResumeVerificationStatus.FAILED,
            critical_failures=critical_failures,
            warnings=(),
            detected_lines=(),
            missing_lines=(),
            duplicate_lines=(),
            reading_order=(),
            grounding_codes=tuple(grounding_codes),
            file_sha256=hashlib.sha256(b"").hexdigest(),
            parser_version="resume-export-preflight-v1",
            created_at=now,
            occurrence_mismatches=(),
            reading_order_failures=(),
            manifest_sha256=lease.export.fidelity_manifest_sha256,
            version_content_sha256=lease.export.version_content_sha256,
            page_count=0,
        )
        async with self._uow() as uow:
            current = await uow.get_export_system(lease.export.id, for_update=True)
            if current is None or not _lease_matches(current, lease, now):
                return ExportProcessingOutcome(
                    lease.export.id,
                    ResumeExportStatus.FAILED,
                    False,
                    "execution_lease_lost",
                )
            blocked = replace(
                current,
                status=ResumeExportStatus.BLOCKED,
                object_key=None,
                size_bytes=0,
                sha256_digest=None,
                verification_status=ResumeVerificationStatus.FAILED,
                verification_codes=report.grounding_codes,
                critical_failures=critical_failures,
                warnings=(),
                parser_version=report.parser_version,
                execution_token_hash=None,
                lease_expires_at=None,
                retry_at=None,
                completed_at=now,
                last_error="unsupported_content",
            )
            await _retire_candidate_cleanup(
                uow,
                lease,
                now,
                retained=False,
                cleaned=candidate_cleaned,
            )
            await uow.save_export(blocked, report)
            await uow.add_audit(self._audit(blocked, ResumeAuditAction.EXPORT_BLOCKED, now))
            await uow.commit()
            return _outcome(blocked)

    async def _claim(
        self, export_id: UUID, token_hash: str
    ) -> _ExecutionLease | ExportProcessingOutcome:
        async with self._uow() as uow:
            export = await uow.get_export_system(export_id, for_update=True)
            if export is None:
                return ExportProcessingOutcome(
                    export_id,
                    ResumeExportStatus.FAILED,
                    False,
                    "export_not_found",
                )
            if export.status in {
                ResumeExportStatus.VERIFIED,
                ResumeExportStatus.BLOCKED,
                ResumeExportStatus.DEAD_LETTERED,
                ResumeExportStatus.DELETION_PENDING,
                ResumeExportStatus.DELETING,
                ResumeExportStatus.DELETION_RETRY_WAIT,
                ResumeExportStatus.DELETION_DEAD_LETTERED,
                ResumeExportStatus.DELETED,
            }:
                return _outcome(export)
            now = self._clock.now()
            if (
                export.status is ResumeExportStatus.RENDERING
                and export.lease_expires_at is not None
                and export.lease_expires_at > now
            ):
                return ExportProcessingOutcome(
                    export.id,
                    export.status,
                    False,
                    "execution_lease_active",
                )
            if (
                export.status is ResumeExportStatus.RETRY_WAIT
                and export.retry_at is not None
                and export.retry_at > now
            ):
                return _outcome(export)
            if export.attempts >= export.max_attempts:
                dead = _dead_letter(export, now, "attempts_exhausted")
                await uow.save_export(dead)
                await uow.add_audit(self._audit(dead, ResumeAuditAction.EXPORT_DEAD_LETTERED, now))
                await uow.commit()
                return _outcome(dead)
            version = await uow.get_version(export.owner_user_id, export.version_id)
            if version is None:
                dead = _dead_letter(export, now, "version_unavailable")
                await uow.save_export(dead)
                await uow.add_audit(self._audit(dead, ResumeAuditAction.EXPORT_DEAD_LETTERED, now))
                await uow.commit()
                return _outcome(dead)
            claimed = replace(
                export,
                status=ResumeExportStatus.RENDERING,
                attempts=export.attempts + 1,
                fence=export.fence + 1,
                execution_token_hash=token_hash,
                lease_expires_at=now + timedelta(seconds=self._policy.execution_lease_seconds),
                retry_at=None,
                completed_at=None,
                last_error=None,
            )
            await uow.save_export(claimed)
            await uow.add_export_object_cleanup(
                ResumeExportObjectCleanup(
                    id=self._ids.new(),
                    owner_user_id=claimed.owner_user_id,
                    export_id=claimed.id,
                    attempt_fence=claimed.fence,
                    object_key=_object_key(claimed),
                    trace_id=claimed.trace_id,
                    not_before=(
                        now
                        + timedelta(
                            seconds=(
                                self._policy.execution_lease_seconds
                                + self._policy.orphan_cleanup_grace_seconds
                            )
                        )
                    ),
                    attempts=0,
                    max_attempts=claimed.cleanup_max_attempts,
                    last_error=None,
                    completed_at=None,
                    cancelled_at=None,
                    dead_lettered_at=None,
                    created_at=now,
                )
            )
            await uow.commit()
            return _ExecutionLease(claimed, version, token_hash)

    async def _verify(
        self,
        version: ResumeVersion,
        export: ResumeExport,
        manifest: ResumeFidelityManifest,
        rendered: RenderedResume,
        digest: str,
        *,
        pin_failures: tuple[str, ...],
    ) -> ResumeVerificationReport:
        extracted = await self._extract(rendered, export.format)
        normalized_text = normalize_fidelity_match_text(extracted.plain_text)
        expected_counts = Counter(entry.normalized_text for entry in manifest.entries)
        actual_counts = _manifest_occurrence_counts(normalized_text, expected_counts)
        occurrence_mismatches = tuple(
            f"occurrence:{value[:80]}:expected={expected}:actual={actual_counts[value]}"
            for value, expected in expected_counts.items()
            if actual_counts[value] != expected
        )
        missing = tuple(
            entry.text for entry in manifest.entries if actual_counts[entry.normalized_text] == 0
        )
        duplicates = tuple(
            next(entry.text for entry in manifest.entries if entry.normalized_text == value)
            for value, expected in expected_counts.items()
            if actual_counts[value] > expected
        )
        detected = tuple(
            entry.text for entry in manifest.entries if actual_counts[entry.normalized_text] > 0
        )
        reading_order_failures = _reading_order_failures(normalized_text, manifest)
        grounding_failures = (
            *version_provenance_failures(version),
            *manifest_grounding_failures(manifest),
        )
        page_failures = (
            (f"page_limit_exceeded:{extracted.page_count}>{version.layout.page_limit}",)
            if extracted.page_count > version.layout.page_limit
            else ()
        )
        searchability_failures = (
            ("searchability_failed",) if manifest.entries and len(normalized_text) < 20 else ()
        )
        critical = tuple(
            dict.fromkeys(
                (
                    *pin_failures,
                    *occurrence_mismatches,
                    *reading_order_failures,
                    *grounding_failures,
                    *page_failures,
                    *searchability_failures,
                )
            )
        )
        status = (
            ResumeVerificationStatus.FAILED
            if critical
            else ResumeVerificationStatus.WARNING
            if extracted.warnings
            else ResumeVerificationStatus.PASSED
        )
        codes = [
            "manifest_version_pinned" if not pin_failures else "manifest_version_mismatch",
            "all_claims_grounded" if not grounding_failures else "grounding_validation_failed",
            "numeric_claims_grounded"
            if not any(
                entry.numeric and entry.factual and not entry.source_ids
                for entry in manifest.entries
            )
            else "numeric_grounding_failed",
            "exact_occurrences_verified"
            if not occurrence_mismatches
            else "occurrence_validation_failed",
            "reading_order_verified"
            if not reading_order_failures
            else "reading_order_validation_failed",
            "page_limit_verified" if not page_failures else "page_limit_failed",
            "searchable_output" if not searchability_failures else "searchability_failed",
        ]
        return ResumeVerificationReport(
            id=self._ids.new(),
            owner_user_id=version.owner_user_id,
            export_id=export.id,
            version_id=version.id,
            status=status,
            critical_failures=critical,
            warnings=extracted.warnings,
            detected_lines=tuple(dict.fromkeys(detected)),
            missing_lines=tuple(dict.fromkeys(missing)),
            duplicate_lines=tuple(dict.fromkeys(duplicates)),
            reading_order=extracted.reading_order,
            grounding_codes=tuple(codes),
            file_sha256=digest,
            parser_version=extracted.parser_version,
            created_at=self._clock.now(),
            occurrence_mismatches=occurrence_mismatches,
            reading_order_failures=reading_order_failures,
            manifest_sha256=fidelity_manifest_sha256(manifest),
            version_content_sha256=manifest.version_content_sha256,
            page_count=extracted.page_count,
        )

    async def _extract(self, rendered: RenderedResume, fmt: ResumeFormat) -> ExtractedDocumentText:
        if fmt in {ResumeFormat.PDF, ResumeFormat.DOCX}:
            suffix = f".{fmt.value}"
            root = self._policy.temp_root
            if root is not None:
                root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=root) as directory:
                path = Path(directory) / f"resume{suffix}"
                path.write_bytes(rendered.content)
                extracted = await self._extractor.extract(path, rendered.media_type)
            page_count = (
                extracted.page_count
                if fmt is ResumeFormat.PDF
                else max(extracted.page_count, rendered.page_count)
            )
            return replace(extracted, page_count=page_count)
        if fmt is ResumeFormat.JSON:
            plain_text, reading_order = _extract_json(rendered.content)
        else:
            plain_text = rendered.content.decode("utf-8", errors="strict")
            reading_order = tuple(
                line for line in (normalize_text(item) for item in plain_text.splitlines()) if line
            )
        return ExtractedDocumentText(
            plain_text=plain_text,
            reading_order=reading_order,
            parser_version="structured-export-verifier-v1",
            page_count=rendered.page_count,
        )

    async def _complete(
        self,
        lease: _ExecutionLease,
        rendered: RenderedResume,
        verification: ResumeVerificationReport,
        object_key: str | None,
        *,
        candidate_cleaned: bool,
    ) -> ExportProcessingOutcome:
        async with self._uow() as uow:
            current = await uow.get_export_system(lease.export.id, for_update=True)
            now = self._clock.now()
            if current is None or not _lease_matches(current, lease, now):
                if object_key is not None and not candidate_cleaned:
                    candidate_cleaned = await self._try_delete_candidate(object_key)
                if candidate_cleaned:
                    await _retire_candidate_cleanup(
                        uow,
                        lease,
                        now,
                        retained=False,
                        cleaned=True,
                    )
                    await uow.commit()
                return ExportProcessingOutcome(
                    lease.export.id,
                    ResumeExportStatus.FAILED,
                    False,
                    "execution_lease_lost",
                )
            status = (
                ResumeExportStatus.BLOCKED
                if verification.status is ResumeVerificationStatus.FAILED
                else ResumeExportStatus.VERIFIED
            )
            completed = replace(
                current,
                status=status,
                object_key=object_key,
                media_type=rendered.media_type,
                size_bytes=len(rendered.content),
                sha256_digest=verification.file_sha256,
                verification_status=verification.status,
                verification_codes=verification.grounding_codes,
                critical_failures=verification.critical_failures,
                warnings=verification.warnings,
                renderer_version=rendered.renderer_version,
                parser_version=verification.parser_version,
                execution_token_hash=None,
                lease_expires_at=None,
                completed_at=now,
                last_error=None,
            )
            await _retire_candidate_cleanup(
                uow,
                lease,
                now,
                retained=object_key is not None,
                cleaned=candidate_cleaned,
            )
            await uow.save_export(completed, verification)
            await uow.add_audit(
                self._audit(
                    completed,
                    (
                        ResumeAuditAction.EXPORT_BLOCKED
                        if status is ResumeExportStatus.BLOCKED
                        else ResumeAuditAction.EXPORT_VERIFIED
                    ),
                    now,
                )
            )
            await uow.commit()
            return _outcome(completed)

    async def _fail(
        self,
        lease: _ExecutionLease,
        safe_error_code: str,
        *,
        candidate_cleaned: bool,
    ) -> ExportProcessingOutcome:
        async with self._uow() as uow:
            current = await uow.get_export_system(lease.export.id, for_update=True)
            now = self._clock.now()
            if current is None or not _lease_matches(current, lease, now, allow_expired=True):
                return ExportProcessingOutcome(
                    lease.export.id,
                    ResumeExportStatus.FAILED,
                    False,
                    "execution_lease_lost",
                )
            if current.attempts >= current.max_attempts:
                failed = _dead_letter(current, now, safe_error_code)
                action = ResumeAuditAction.EXPORT_DEAD_LETTERED
            else:
                available_at = now + timedelta(
                    seconds=self._policy.retry_delay_seconds * current.attempts
                )
                failed = replace(
                    current,
                    status=ResumeExportStatus.RETRY_WAIT,
                    execution_token_hash=None,
                    lease_expires_at=None,
                    retry_at=available_at,
                    completed_at=None,
                    last_error=safe_error_code,
                )
                await uow.add_export_outbox(
                    _new_outbox(
                        self._ids.new(),
                        failed,
                        available_at,
                        max_attempts=self._policy.outbox_max_attempts,
                    )
                )
                action = ResumeAuditAction.EXPORT_RETRY_SCHEDULED
            await _retire_candidate_cleanup(
                uow,
                lease,
                now,
                retained=False,
                cleaned=candidate_cleaned,
            )
            await uow.save_export(failed)
            await uow.add_audit(self._audit(failed, action, now))
            await uow.commit()
            return _outcome(failed)

    def _audit(
        self,
        export: ResumeExport,
        action: ResumeAuditAction,
        now: datetime,
    ) -> ResumeBuilderAuditEvent:
        return _background_audit(
            self._ids,
            export,
            action,
            now,
            stage="processor",
        )


class ResumeExportCleanupProcessor:
    """Delete one private export object with fenced, durable retry semantics."""

    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        storage: ResumeObjectStorage,
        policy: ResumeExportWorkerPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._storage = storage
        self._policy = policy or ResumeExportWorkerPolicy()

    async def process(self, export_id: UUID, execution_token: str) -> ExportProcessingOutcome:
        token_hash = hashlib.sha256(execution_token.encode("utf-8")).hexdigest()
        lease = await self._claim(export_id, token_hash)
        if isinstance(lease, ExportProcessingOutcome):
            return lease
        try:
            if lease.export.object_key is not None:
                await self._storage.delete(lease.export.object_key)
        except Exception:
            return await self._fail(lease)
        return await self._complete(lease)

    async def _claim(
        self,
        export_id: UUID,
        token_hash: str,
    ) -> _CleanupLease | ExportProcessingOutcome:
        async with self._uow() as uow:
            export = await uow.get_export_system(export_id, for_update=True)
            if export is None:
                return ExportProcessingOutcome(
                    export_id,
                    ResumeExportStatus.FAILED,
                    False,
                    "export_not_found",
                )
            if export.status in {
                ResumeExportStatus.DELETED,
                ResumeExportStatus.DELETION_DEAD_LETTERED,
            }:
                return _outcome(export)
            if export.status not in {
                ResumeExportStatus.DELETION_PENDING,
                ResumeExportStatus.DELETING,
                ResumeExportStatus.DELETION_RETRY_WAIT,
            }:
                return _outcome(export)
            now = self._clock.now()
            if (
                export.status is ResumeExportStatus.DELETING
                and export.lease_expires_at is not None
                and export.lease_expires_at > now
            ):
                return ExportProcessingOutcome(
                    export.id,
                    export.status,
                    False,
                    "execution_lease_active",
                )
            if (
                export.status is ResumeExportStatus.DELETION_RETRY_WAIT
                and export.retry_at is not None
                and export.retry_at > now
            ):
                return _outcome(export)
            if export.cleanup_attempts >= export.cleanup_max_attempts:
                dead = _cleanup_dead_letter(export, now, "cleanup_attempts_exhausted")
                await uow.save_export(dead)
                await uow.add_audit(
                    _background_audit(
                        self._ids,
                        dead,
                        ResumeAuditAction.EXPORT_DELETION_DEAD_LETTERED,
                        now,
                        stage="cleanup",
                    )
                )
                await uow.commit()
                return _outcome(dead)
            claimed = replace(
                export,
                status=ResumeExportStatus.DELETING,
                cleanup_attempts=export.cleanup_attempts + 1,
                fence=export.fence + 1,
                execution_token_hash=token_hash,
                lease_expires_at=now + timedelta(seconds=self._policy.execution_lease_seconds),
                retry_at=None,
                dead_lettered_at=None,
                last_error=None,
            )
            await uow.save_export(claimed)
            await uow.commit()
            return _CleanupLease(claimed, token_hash)

    async def _complete(self, lease: _CleanupLease) -> ExportProcessingOutcome:
        async with self._uow() as uow:
            current = await uow.get_export_system(lease.export.id, for_update=True)
            now = self._clock.now()
            if current is None or not _cleanup_lease_matches(current, lease, now):
                return ExportProcessingOutcome(
                    lease.export.id,
                    ResumeExportStatus.FAILED,
                    False,
                    "execution_lease_lost",
                )
            deleted = replace(
                current,
                status=ResumeExportStatus.DELETED,
                object_key=None,
                execution_token_hash=None,
                lease_expires_at=None,
                retry_at=None,
                dead_lettered_at=None,
                deleted_at=now,
                last_error=None,
            )
            await uow.save_export(deleted)
            await uow.add_audit(
                _background_audit(
                    self._ids,
                    deleted,
                    ResumeAuditAction.EXPORT_DELETED,
                    now,
                    stage="cleanup",
                )
            )
            await uow.commit()
            return _outcome(deleted)

    async def _fail(self, lease: _CleanupLease) -> ExportProcessingOutcome:
        async with self._uow() as uow:
            current = await uow.get_export_system(lease.export.id, for_update=True)
            now = self._clock.now()
            if current is None or not _cleanup_lease_matches(
                current,
                lease,
                now,
                allow_expired=True,
            ):
                return ExportProcessingOutcome(
                    lease.export.id,
                    ResumeExportStatus.FAILED,
                    False,
                    "execution_lease_lost",
                )
            if current.cleanup_attempts >= current.cleanup_max_attempts:
                failed = _cleanup_dead_letter(current, now, "object_cleanup_failed")
                action = ResumeAuditAction.EXPORT_DELETION_DEAD_LETTERED
            else:
                available_at = now + timedelta(
                    seconds=self._policy.retry_delay_seconds * current.cleanup_attempts
                )
                failed = replace(
                    current,
                    status=ResumeExportStatus.DELETION_RETRY_WAIT,
                    execution_token_hash=None,
                    lease_expires_at=None,
                    retry_at=available_at,
                    dead_lettered_at=None,
                    last_error="object_cleanup_failed",
                )
                await uow.add_export_outbox(
                    _new_outbox(
                        self._ids.new(),
                        failed,
                        available_at,
                        operation=ResumeExportOperation.DELETE,
                        max_attempts=self._policy.outbox_max_attempts,
                    )
                )
                action = ResumeAuditAction.EXPORT_DELETION_RETRY_SCHEDULED
            await uow.save_export(failed)
            await uow.add_audit(
                _background_audit(
                    self._ids,
                    failed,
                    action,
                    now,
                    stage="cleanup",
                )
            )
            await uow.commit()
            return _outcome(failed)


class ResumeExportObjectCleanupProcessor:
    """Reconcile attempt objects that were never committed as verified exports."""

    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        storage: ResumeObjectStorage,
        policy: ResumeExportWorkerPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._storage = storage
        self._policy = policy or ResumeExportWorkerPolicy()

    async def cleanup_due(self, limit: int) -> ExportObjectCleanupResult:
        if not 1 <= limit <= 100:
            raise ValueError("resume export object cleanup limit must be 1-100")
        now = self._clock.now()
        completed = failed = dead_lettered = 0
        async with self._uow() as uow:
            cleanups = await uow.list_due_export_object_cleanups(now, limit)
            for cleanup in cleanups:
                export = await uow.get_export_system(cleanup.export_id)
                if export is not None and export.object_key == cleanup.object_key:
                    await uow.save_export_object_cleanup(
                        replace(cleanup, cancelled_at=now, last_error=None)
                    )
                    continue
                try:
                    await self._storage.delete(cleanup.object_key)
                except Exception:
                    attempts = cleanup.attempts + 1
                    terminal = attempts >= cleanup.max_attempts
                    updated = replace(
                        cleanup,
                        attempts=attempts,
                        not_before=(
                            cleanup.not_before
                            if terminal
                            else now
                            + timedelta(seconds=self._policy.retry_delay_seconds * attempts)
                        ),
                        last_error="orphan_object_cleanup_failed",
                        dead_lettered_at=now if terminal else None,
                    )
                    action = (
                        ResumeAuditAction.EXPORT_ORPHAN_CLEANUP_DEAD_LETTERED
                        if terminal
                        else ResumeAuditAction.EXPORT_ORPHAN_CLEANUP_RETRY_SCHEDULED
                    )
                    dead_lettered += int(terminal)
                    failed += int(not terminal)
                else:
                    updated = replace(
                        cleanup,
                        attempts=cleanup.attempts + 1,
                        last_error=None,
                        completed_at=now,
                    )
                    action = ResumeAuditAction.EXPORT_ORPHAN_CLEANUP_COMPLETED
                    completed += 1
                await uow.save_export_object_cleanup(updated)
                await uow.add_audit(
                    ResumeBuilderAuditEvent(
                        id=self._ids.new(),
                        owner_user_id=updated.owner_user_id,
                        actor_user_id=updated.owner_user_id,
                        action=action,
                        target_kind="resume_export_object_cleanup",
                        target_id=updated.id,
                        request_id=f"background:resume-export-cleanup:{updated.id}",
                        trace_id=updated.trace_id,
                        created_at=now,
                        metadata={
                            "attempt": updated.attempts,
                            "attemptFence": updated.attempt_fence,
                            "exportId": str(updated.export_id),
                            "stage": "orphan_cleanup",
                        },
                    )
                )
            await uow.commit()
        return ExportObjectCleanupResult(completed, failed, dead_lettered)


class ResumeExportOutboxDispatcher:
    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        publisher: ResumeExportJobPublisher,
        clock: Clock,
        identifiers: IdentifierFactory,
        policy: ResumeExportWorkerPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._publisher = publisher
        self._clock = clock
        self._ids = identifiers
        self._policy = policy or ResumeExportWorkerPolicy()

    async def dispatch_pending(self, limit: int) -> ExportOutboxDispatchResult:
        if not 1 <= limit <= 100:
            raise ValueError("resume export outbox limit must be 1-100")
        now = self._clock.now()
        async with self._uow() as uow:
            messages = await uow.claim_export_outbox(
                now,
                now + timedelta(seconds=self._policy.outbox_lease_seconds),
                limit,
            )
            await uow.commit()
        published = failed = dead_lettered = 0
        for message in messages:
            lease_token = message.lease_token
            if lease_token is None:
                continue
            try:
                await self._publisher.publish(
                    message.export_id,
                    message.trace_id,
                    message.operation,
                )
                updated = replace(
                    message,
                    published_at=self._clock.now(),
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    last_error=None,
                )
                outcome = "published"
            except Exception:
                attempts = message.attempts + 1
                terminal = attempts >= message.max_attempts
                updated = replace(
                    message,
                    attempts=attempts,
                    available_at=self._clock.now()
                    + timedelta(seconds=self._policy.retry_delay_seconds * attempts),
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    dead_lettered_at=self._clock.now() if terminal else None,
                    last_error="publish_failed",
                )
                outcome = "dead_lettered" if terminal else "failed"
            async with self._uow() as uow:
                saved = await uow.save_export_outbox(
                    updated,
                    expected_lease_token=lease_token,
                )
                if saved:
                    audit_now = self._clock.now()
                    export = await uow.get_export_system(updated.export_id, for_update=True)
                    if export is not None:
                        if updated.dead_lettered_at is not None:
                            if (
                                message.operation is ResumeExportOperation.RENDER
                                and export.status
                                in {
                                    ResumeExportStatus.PENDING,
                                    ResumeExportStatus.RETRY_WAIT,
                                }
                            ):
                                export = _dead_letter(
                                    export,
                                    audit_now,
                                    "publish_dead_lettered",
                                )
                                await uow.save_export(export)
                            elif (
                                message.operation is ResumeExportOperation.DELETE
                                and export.status
                                in {
                                    ResumeExportStatus.DELETION_PENDING,
                                    ResumeExportStatus.DELETION_RETRY_WAIT,
                                }
                            ):
                                export = _cleanup_dead_letter(
                                    export,
                                    audit_now,
                                    "cleanup_publish_dead_lettered",
                                )
                                await uow.save_export(export)
                        action = (
                            ResumeAuditAction.EXPORT_DISPATCHED
                            if outcome == "published"
                            else ResumeAuditAction.EXPORT_DISPATCH_DEAD_LETTERED
                            if outcome == "dead_lettered"
                            else ResumeAuditAction.EXPORT_DISPATCH_RETRY_SCHEDULED
                        )
                        await uow.add_audit(
                            _background_audit(
                                self._ids,
                                export,
                                action,
                                audit_now,
                                stage="outbox_dispatch",
                            )
                        )
                await uow.commit()
            if not saved:
                continue
            if outcome == "published":
                published += 1
            elif outcome == "dead_lettered":
                dead_lettered += 1
            else:
                failed += 1
        return ExportOutboxDispatchResult(published, failed, dead_lettered)


class ResumeExportReconciler:
    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        policy: ResumeExportWorkerPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._policy = policy or ResumeExportWorkerPolicy()

    async def reconcile(self, limit: int) -> ExportReconciliationResult:
        if not 1 <= limit <= 100:
            raise ValueError("resume export reconciliation limit must be 1-100")
        now = self._clock.now()
        requeued = dead_lettered = 0
        async with self._uow() as uow:
            exports = await uow.list_recoverable_exports(now, limit)
            for export in exports:
                cleanup = export.status in {
                    ResumeExportStatus.DELETION_PENDING,
                    ResumeExportStatus.DELETING,
                    ResumeExportStatus.DELETION_RETRY_WAIT,
                }
                if (
                    not cleanup
                    and export.status is ResumeExportStatus.PENDING
                    and export.requested_at
                    > now - timedelta(seconds=self._policy.reconciliation_stale_seconds)
                ):
                    continue
                attempts = export.cleanup_attempts if cleanup else export.attempts
                max_attempts = export.cleanup_max_attempts if cleanup else export.max_attempts
                if attempts >= max_attempts:
                    dead = (
                        _cleanup_dead_letter(
                            export,
                            now,
                            "cleanup_recovery_attempts_exhausted",
                        )
                        if cleanup
                        else _dead_letter(export, now, "recovery_attempts_exhausted")
                    )
                    await uow.save_export(dead)
                    await uow.add_audit(
                        _background_audit(
                            self._ids,
                            dead,
                            (
                                ResumeAuditAction.EXPORT_DELETION_DEAD_LETTERED
                                if cleanup
                                else ResumeAuditAction.EXPORT_DEAD_LETTERED
                            ),
                            now,
                            stage="reconciliation",
                        )
                    )
                    dead_lettered += 1
                    continue
                operation = (
                    ResumeExportOperation.DELETE if cleanup else ResumeExportOperation.RENDER
                )
                if await uow.has_active_export_outbox(export.id, operation):
                    continue
                recovered = replace(
                    export,
                    status=(
                        ResumeExportStatus.DELETION_PENDING
                        if cleanup
                        else ResumeExportStatus.PENDING
                    ),
                    execution_token_hash=None,
                    lease_expires_at=None,
                    retry_at=None,
                    last_error=(
                        "cleanup_lease_expired"
                        if export.status is ResumeExportStatus.DELETING
                        else "execution_lease_expired"
                        if export.status is ResumeExportStatus.RENDERING
                        else export.last_error
                    ),
                )
                await uow.save_export(recovered)
                await uow.add_export_outbox(
                    _new_outbox(
                        self._ids.new(),
                        recovered,
                        now,
                        operation=operation,
                        max_attempts=self._policy.outbox_max_attempts,
                    )
                )
                await uow.add_audit(
                    _background_audit(
                        self._ids,
                        recovered,
                        (
                            ResumeAuditAction.EXPORT_DELETION_RECOVERY_SCHEDULED
                            if cleanup
                            else ResumeAuditAction.EXPORT_RECOVERY_SCHEDULED
                        ),
                        now,
                        stage="reconciliation",
                    )
                )
                requeued += 1
            await uow.commit()
        return ExportReconciliationResult(requeued, dead_lettered)


async def _retire_candidate_cleanup(
    uow: ResumeBuilderUnitOfWork,
    lease: _ExecutionLease,
    now: datetime,
    *,
    retained: bool,
    cleaned: bool,
) -> None:
    cleanup = await uow.get_export_object_cleanup(
        lease.export.owner_user_id,
        lease.export.id,
        lease.export.fence,
        for_update=True,
    )
    if cleanup is None:
        raise RuntimeError("resume export candidate cleanup is missing")
    if cleanup.terminal:
        if retained and cleanup.cancelled_at is None:
            raise RuntimeError("resume export candidate was already cleaned")
        return
    if retained:
        await uow.save_export_object_cleanup(replace(cleanup, cancelled_at=now, last_error=None))
    elif cleaned:
        await uow.save_export_object_cleanup(replace(cleanup, completed_at=now, last_error=None))


def _pin_failures(export: ResumeExport, manifest: ResumeFidelityManifest) -> tuple[str, ...]:
    failures: list[str] = []
    if export.version_id != manifest.version_id:
        failures.append("version_id_mismatch")
    if export.version_content_sha256 != manifest.version_content_sha256:
        failures.append("version_content_hash_mismatch")
    if export.fidelity_manifest != fidelity_manifest_payload(manifest):
        failures.append("fidelity_manifest_mismatch")
    if export.fidelity_manifest_sha256 != fidelity_manifest_sha256(manifest):
        failures.append("fidelity_manifest_hash_mismatch")
    return tuple(failures)


def _background_audit(
    identifiers: IdentifierFactory,
    export: ResumeExport,
    action: ResumeAuditAction,
    now: datetime,
    *,
    stage: str,
) -> ResumeBuilderAuditEvent:
    return ResumeBuilderAuditEvent(
        id=identifiers.new(),
        owner_user_id=export.owner_user_id,
        actor_user_id=export.owner_user_id,
        action=action,
        target_kind="resume_export",
        target_id=export.id,
        request_id=f"background:resume-export:{export.id}",
        trace_id=export.trace_id,
        created_at=now,
        metadata={
            "attempt": export.attempts,
            "cleanupAttempt": export.cleanup_attempts,
            "stage": stage,
            "status": export.status.value,
        },
    )


def _manifest_occurrence_counts(text: str, expected: Counter[str]) -> dict[str, int]:
    occupied: list[tuple[int, int]] = []
    counts: dict[str, int] = {}
    for value in sorted(expected, key=lambda item: (-len(item), item)):
        start = 0
        available: list[tuple[int, int]] = []
        while start <= len(text) - len(value):
            index = text.find(value, start)
            if index < 0:
                break
            match = (index, index + len(value))
            if not any(
                match[0] < occupied_end and match[1] > occupied_start
                for occupied_start, occupied_end in occupied
            ):
                available.append(match)
            start = index + 1
        counts[value] = len(available)
        occupied.extend(available)
    return counts


def _reading_order_failures(
    normalized_text: str, manifest: ResumeFidelityManifest
) -> tuple[str, ...]:
    cursor = 0
    failures: list[str] = []
    for entry in manifest.entries:
        index = normalized_text.find(entry.normalized_text, cursor)
        if index < 0:
            if entry.normalized_text in normalized_text:
                failures.append(f"reading_order:{entry.key}")
            continue
        cursor = index + len(entry.normalized_text)
    return tuple(failures)


def _extract_json(content: bytes) -> tuple[str, tuple[str, ...]]:
    try:
        payload = json.loads(content.decode("utf-8", errors="strict"))
        if not isinstance(payload, dict):
            raise ValueError
        lines: list[str] = []
        personal = payload.get("personalFacts", [])
        if not isinstance(personal, list):
            raise ValueError
        for fact in personal:
            if not isinstance(fact, dict) or not isinstance(fact.get("value"), str):
                raise ValueError
            lines.append(fact["value"])
        target_role = payload.get("targetRole")
        if target_role is not None:
            if not isinstance(target_role, str):
                raise ValueError
            lines.append(target_role)
        entities_raw = payload.get("entities", [])
        if not isinstance(entities_raw, list):
            raise ValueError
        entities = {
            str(entity["id"]): entity
            for entity in entities_raw
            if isinstance(entity, dict) and entity.get("id") is not None
        }
        emitted: set[str] = set()
        sections = payload.get("sections", [])
        if not isinstance(sections, list):
            raise ValueError
        for section in sections:
            if not isinstance(section, dict) or not isinstance(section.get("title"), str):
                raise ValueError
            lines.append(section["title"])
            items = section.get("items", [])
            if not isinstance(items, list):
                raise ValueError
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                    raise ValueError
                entity_id = item.get("entityId")
                if isinstance(entity_id, str) and entity_id not in emitted:
                    entity = entities.get(entity_id)
                    if entity is None:
                        raise ValueError
                    lines.extend(_json_entity_lines(entity))
                    emitted.add(entity_id)
                lines.append(item["text"])
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ResumeBuilderValidationError("structured JSON export is invalid") from exc
    return "\n".join(lines), tuple(lines)


def _json_entity_lines(entity: dict[str, object]) -> tuple[str, ...]:
    title = entity.get("displayTitle") or entity.get("officialTitle") or entity.get("title")
    if not isinstance(title, str):
        raise ValueError
    lines = [title]
    for key in ("organization", "location"):
        value = entity.get(key)
        if isinstance(value, str) and value:
            lines.append(value)
    start = _json_date(entity.get("startDate"))
    end = "Present" if entity.get("isCurrent") is True else _json_date(entity.get("endDate"))
    if start and end:
        lines.append(f"{start} - {end}")
    elif start or end:
        lines.append(start or end or "")
    return tuple(lines)


def _json_date(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    year = value.get("year")
    month = value.get("month")
    if not isinstance(year, int):
        raise ValueError
    if month is None:
        return str(year)
    if not isinstance(month, int):
        raise ValueError
    return f"{month:02d}/{year}"


def _lease_matches(
    current: ResumeExport | None,
    lease: _ExecutionLease,
    now: datetime,
    *,
    allow_expired: bool = False,
) -> bool:
    return (
        current is not None
        and current.status is ResumeExportStatus.RENDERING
        and current.fence == lease.export.fence
        and current.execution_token_hash == lease.token_hash
        and current.lease_expires_at is not None
        and (allow_expired or current.lease_expires_at > now)
    )


def _cleanup_lease_matches(
    current: ResumeExport | None,
    lease: _CleanupLease,
    now: datetime,
    *,
    allow_expired: bool = False,
) -> bool:
    return (
        current is not None
        and current.status is ResumeExportStatus.DELETING
        and current.fence == lease.export.fence
        and current.execution_token_hash == lease.token_hash
        and current.lease_expires_at is not None
        and (allow_expired or current.lease_expires_at > now)
    )


def _dead_letter(export: ResumeExport, now: datetime, code: str) -> ResumeExport:
    return replace(
        export,
        status=ResumeExportStatus.DEAD_LETTERED,
        execution_token_hash=None,
        lease_expires_at=None,
        retry_at=None,
        dead_lettered_at=now,
        completed_at=now,
        last_error=code,
    )


def _cleanup_dead_letter(export: ResumeExport, now: datetime, code: str) -> ResumeExport:
    return replace(
        export,
        status=ResumeExportStatus.DELETION_DEAD_LETTERED,
        execution_token_hash=None,
        lease_expires_at=None,
        retry_at=None,
        dead_lettered_at=now,
        last_error=code,
    )


def _new_outbox(
    message_id: UUID,
    export: ResumeExport,
    available_at: datetime,
    *,
    operation: ResumeExportOperation = ResumeExportOperation.RENDER,
    max_attempts: int,
) -> ResumeExportOutboxMessage:
    return ResumeExportOutboxMessage(
        id=message_id,
        owner_user_id=export.owner_user_id,
        export_id=export.id,
        operation=operation,
        trace_id=export.trace_id,
        available_at=available_at,
        attempts=0,
        max_attempts=max_attempts,
        lease_token=None,
        leased_at=None,
        lease_expires_at=None,
        published_at=None,
        dead_lettered_at=None,
        last_error=None,
        created_at=available_at,
    )


def _object_key(export: ResumeExport) -> str:
    return (
        f"resume-exports/{export.owner_user_id.hex}/{export.version_id.hex}/"
        f"{export.id.hex}/attempt-{export.fence}/resume.{export.format.value}"
    )


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ResumeBuilderValidationError):
        return "rendered_output_invalid"
    return "export_processing_failed"


def _outcome(export: ResumeExport) -> ExportProcessingOutcome:
    return ExportProcessingOutcome(
        export.id,
        export.status,
        export.status
        in {
            ResumeExportStatus.RETRY_WAIT,
            ResumeExportStatus.DELETION_RETRY_WAIT,
        },
        export.last_error,
    )
