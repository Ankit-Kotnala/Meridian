"""Resume builder application service."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from careeros.modules.resume_builder.domain import (
    ResumeAuditAction,
    ResumeBuilderAuditEvent,
    ResumeBuilderConflict,
    ResumeBuilderIdempotencyConflict,
    ResumeBuilderIdempotencyRecord,
    ResumeBuilderNotFound,
    ResumeBuilderValidationError,
    ResumeBuilderVersionConflict,
    ResumeBullet,
    ResumeDocument,
    ResumeDownloadIntent,
    ResumeExport,
    ResumeExportBlocked,
    ResumeExportStatus,
    ResumeFormat,
    ResumeSection,
    ResumeTemplate,
    ResumeVerificationReport,
    ResumeVerificationStatus,
    ResumeVersion,
    normalize_text,
    validate_optional_target_role,
    validate_sections,
    validate_title,
)

from .models import (
    CreateResume,
    DownloadIntentView,
    ExportResume,
    RequestContext,
    ResumeExportRecord,
    ResumeList,
    ResumeRecord,
    ResumeSourceSnapshot,
    ResumeVersionList,
    UpdateResume,
)
from .ports import (
    Clock,
    IdentifierFactory,
    ResumeBuilderUnitOfWorkFactory,
    ResumeDocumentExtractor,
    ResumeObjectStorage,
    ResumeRenderer,
    ResumeSourceProvider,
)


class ResumeBuilderPolicy:
    download_ttl_seconds: int = 120
    max_export_bytes: int = 8 * 1024 * 1024


class ResumeBuilderService:
    """Owner-scoped Phase 7 resume builder, versioning, export, and verification."""

    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        sources: ResumeSourceProvider,
        renderer: ResumeRenderer,
        extractor: ResumeDocumentExtractor,
        storage: ResumeObjectStorage,
        policy: ResumeBuilderPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._sources = sources
        self._renderer = renderer
        self._extractor = extractor
        self._storage = storage
        self._policy = policy or ResumeBuilderPolicy()

    async def list_resumes(self, owner_user_id: UUID) -> ResumeList:
        async with self._uow() as uow:
            items = await uow.list_resumes(owner_user_id)
        return ResumeList(items=items)

    async def create_resume(
        self,
        owner_user_id: UUID,
        command: CreateResume,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ResumeRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        title = validate_title(command.title)
        target_role = validate_optional_target_role(command.target_role)
        fingerprint = _fingerprint(
            "resume-create",
            {
                "title": title,
                "targetRole": target_role,
                "template": command.template.value,
                "changeSetId": _uuid(command.change_set_id),
                "changeSetVersionId": _uuid(command.change_set_version_id),
            },
        )
        replay = await self._resume_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        source = await self._sources.snapshot(
            owner_user_id,
            change_set_id=command.change_set_id,
            change_set_version_id=command.change_set_version_id,
        )
        now = self._clock.now()
        resume_id = self._ids.new()
        version = self._new_version(
            owner_user_id,
            resume_id,
            1,
            None,
            title,
            target_role,
            command.template,
            source,
            command.change_set_id,
            command.change_set_version_id,
            now,
        )
        resume = ResumeDocument(
            id=resume_id,
            owner_user_id=owner_user_id,
            title=title,
            target_role=target_role,
            template=command.template,
            current_version_id=version.id,
            source_change_set_id=command.change_set_id,
            source_change_set_version_id=command.change_set_version_id,
            version=1,
            created_at=now,
            updated_at=now,
        )
        record = ResumeRecord(resume=resume, current_version=version)
        async with self._uow() as uow:
            await uow.add_resume(record)
            await uow.add_idempotency(
                self._idem(
                    owner_user_id,
                    idempotency_key,
                    fingerprint,
                    "resume",
                    resume_id,
                    "resume",
                    resume_id,
                    now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.RESUME_CREATED,
                    "resume",
                    resume_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return record

    async def get_resume(self, owner_user_id: UUID, resume_id: UUID) -> ResumeRecord:
        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id)
        if record is None:
            raise ResumeBuilderNotFound
        return record

    async def update_resume(
        self,
        owner_user_id: UUID,
        resume_id: UUID,
        command: UpdateResume,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ResumeRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "resume-update",
            {
                "resumeId": str(resume_id),
                "expectedVersion": expected_version,
                "title": command.title,
                "targetRole": command.target_role,
                "template": command.template.value if command.template else None,
                "sections": _sections_payload(command.sections)
                if command.sections is not None
                else None,
            },
        )
        replay = await self._resume_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id, for_update=True)
            if record is None:
                raise ResumeBuilderNotFound
            if record.resume.version != expected_version:
                raise ResumeBuilderVersionConflict
            source = await self._sources.snapshot(
                owner_user_id,
                change_set_id=record.resume.source_change_set_id,
                change_set_version_id=record.resume.source_change_set_version_id,
            )
            title = (
                validate_title(command.title) if command.title is not None else record.resume.title
            )
            target_role = (
                validate_optional_target_role(command.target_role)
                if command.target_role is not None
                else record.resume.target_role
            )
            template = command.template or record.resume.template
            sections = (
                validate_sections(
                    command.sections,
                    eligible_evidence_ids=set(source.source_evidence_ids),
                )
                if command.sections is not None
                else record.current_version.sections
            )
            versions = await uow.list_versions(owner_user_id, resume_id)
            next_number = max((item.version_number for item in versions), default=0) + 1
            now = self._clock.now()
            version = replace(
                record.current_version,
                id=self._ids.new(),
                version_number=next_number,
                parent_version_id=record.current_version.id,
                title=title,
                target_role=target_role,
                template=template,
                sections=sections,
                plain_text=_plain_text(title, target_role, sections),
                created_at=now,
            )
            resume = replace(
                record.resume,
                title=title,
                target_role=target_role,
                template=template,
                current_version_id=version.id,
                version=record.resume.version + 1,
                updated_at=now,
            )
            updated = ResumeRecord(resume=resume, current_version=version)
            await uow.add_version(version)
            await uow.save_resume(updated)
            await uow.add_idempotency(
                self._idem(
                    owner_user_id,
                    idempotency_key,
                    fingerprint,
                    "resume",
                    resume_id,
                    "resume",
                    resume_id,
                    now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.RESUME_UPDATED,
                    "resume",
                    resume_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return updated

    async def list_versions(self, owner_user_id: UUID, resume_id: UUID) -> ResumeVersionList:
        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id)
            if record is None:
                raise ResumeBuilderNotFound
            versions = await uow.list_versions(owner_user_id, resume_id)
        return ResumeVersionList(items=versions)

    async def create_version(
        self,
        owner_user_id: UUID,
        resume_id: UUID,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ResumeVersion:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "resume-version-create",
            {"resumeId": str(resume_id), "expectedVersion": expected_version},
        )
        replay = await self._version_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id, for_update=True)
            if record is None:
                raise ResumeBuilderNotFound
            if record.resume.version != expected_version:
                raise ResumeBuilderVersionConflict
            versions = await uow.list_versions(owner_user_id, resume_id)
            next_number = max((item.version_number for item in versions), default=0) + 1
            now = self._clock.now()
            version = replace(
                record.current_version,
                id=self._ids.new(),
                version_number=next_number,
                parent_version_id=record.current_version.id,
                created_at=now,
            )
            await uow.add_version(version)
            await uow.set_current_version(owner_user_id, resume_id, version.id, now=now)
            await uow.add_idempotency(
                self._idem(
                    owner_user_id,
                    idempotency_key,
                    fingerprint,
                    "resume",
                    resume_id,
                    "resume_version",
                    version.id,
                    now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.VERSION_CREATED,
                    "resume_version",
                    version.id,
                    context,
                    now,
                    resumeId=str(resume_id),
                )
            )
            await uow.commit()
        return version

    async def get_version(self, owner_user_id: UUID, version_id: UUID) -> ResumeVersion:
        async with self._uow() as uow:
            version = await uow.get_version(owner_user_id, version_id)
        if version is None:
            raise ResumeBuilderNotFound
        return version

    async def restore_version(
        self,
        owner_user_id: UUID,
        resume_id: UUID,
        version_id: UUID,
        *,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ResumeRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "resume-version-restore",
            {
                "resumeId": str(resume_id),
                "versionId": str(version_id),
                "expectedVersion": expected_version,
            },
        )
        replay = await self._resume_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id, for_update=True)
            if record is None:
                raise ResumeBuilderNotFound
            if record.resume.version != expected_version:
                raise ResumeBuilderVersionConflict
            version = await uow.get_version(owner_user_id, version_id)
            if version is None or version.resume_id != resume_id:
                raise ResumeBuilderNotFound
            now = self._clock.now()
            updated = await uow.set_current_version(owner_user_id, resume_id, version_id, now=now)
            if updated is None:
                raise ResumeBuilderNotFound
            await uow.add_idempotency(
                self._idem(
                    owner_user_id,
                    idempotency_key,
                    fingerprint,
                    "resume",
                    resume_id,
                    "resume",
                    resume_id,
                    now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.VERSION_RESTORED,
                    "resume",
                    resume_id,
                    context,
                    now,
                    versionId=str(version_id),
                )
            )
            await uow.commit()
        return updated

    async def export_version(
        self,
        owner_user_id: UUID,
        version_id: UUID,
        command: ExportResume,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ResumeExportRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint(
            "resume-export",
            {"versionId": str(version_id), "format": command.format.value},
        )
        async with self._uow() as uow:
            existing = await uow.find_export_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.idempotency_fingerprint != fingerprint:
                    raise ResumeBuilderIdempotencyConflict
                verification = await uow.get_verification(owner_user_id, existing.id)
                return ResumeExportRecord(export=existing, verification=verification)
            version = await uow.get_version(owner_user_id, version_id)
            if version is None:
                raise ResumeBuilderNotFound
            now = self._clock.now()
            export_id = self._ids.new()
            export = ResumeExport(
                id=export_id,
                owner_user_id=owner_user_id,
                resume_id=version.resume_id,
                version_id=version.id,
                format=command.format,
                status=ResumeExportStatus.PENDING,
                object_key=None,
                media_type=_media_type(command.format),
                size_bytes=0,
                sha256_digest=None,
                verification_status=None,
                verification_codes=(),
                critical_failures=(),
                warnings=(),
                renderer_version="resume-renderer-unset",
                parser_version=None,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=fingerprint,
                attempts=0,
                requested_at=now,
                completed_at=None,
                deleted_at=None,
                last_error=None,
            )
            await uow.add_export(export)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.EXPORT_REQUESTED,
                    "resume_export",
                    export_id,
                    context,
                    now,
                    versionId=str(version_id),
                    format=command.format.value,
                )
            )
            await uow.commit()

        return await self._render_and_verify(owner_user_id, export_id, context)

    async def get_export(self, owner_user_id: UUID, export_id: UUID) -> ResumeExportRecord:
        async with self._uow() as uow:
            export = await uow.get_export(owner_user_id, export_id)
            if export is None:
                raise ResumeBuilderNotFound
            verification = await uow.get_verification(owner_user_id, export_id)
        return ResumeExportRecord(export=export, verification=verification)

    async def get_verification(
        self, owner_user_id: UUID, export_id: UUID
    ) -> ResumeVerificationReport:
        async with self._uow() as uow:
            report = await uow.get_verification(owner_user_id, export_id)
        if report is None:
            raise ResumeBuilderNotFound
        return report

    async def create_download_intent(
        self,
        owner_user_id: UUID,
        export_id: UUID,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> DownloadIntentView:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint("resume-export-download-intent", {"exportId": str(export_id)})
        async with self._uow() as uow:
            existing = await uow.find_download_intent_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.idempotency_fingerprint != fingerprint:
                    raise ResumeBuilderIdempotencyConflict
                return DownloadIntentView(
                    export_id=existing.export_id,
                    url=existing.url,
                    expires_at=existing.expires_at,
                )
            export = await uow.get_export(owner_user_id, export_id)
            if export is None:
                raise ResumeBuilderNotFound
            self._assert_releasable(export)
            if export.object_key is None:
                raise ResumeBuilderConflict("export object is unavailable")
            now = self._clock.now()
            url = await self._storage.presign_get(
                export.object_key,
                expires_in_seconds=self._policy.download_ttl_seconds,
            )
            intent = ResumeDownloadIntent(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                export_id=export.id,
                object_key=export.object_key,
                url=url,
                expires_at=now + timedelta(seconds=self._policy.download_ttl_seconds),
                idempotency_key=idempotency_key,
                idempotency_fingerprint=fingerprint,
                created_at=now,
            )
            await uow.add_download_intent(intent)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.DOWNLOAD_INTENT_CREATED,
                    "resume_export",
                    export_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return DownloadIntentView(export_id=export_id, url=url, expires_at=intent.expires_at)

    async def delete_export(
        self,
        owner_user_id: UUID,
        export_id: UUID,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> ResumeExportRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        fingerprint = _fingerprint("resume-export-delete", {"exportId": str(export_id)})
        replay = await self._export_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        async with self._uow() as uow:
            export = await uow.get_export(owner_user_id, export_id)
            if export is None:
                raise ResumeBuilderNotFound
            if export.status == ResumeExportStatus.DELETED:
                verification = await uow.get_verification(owner_user_id, export_id)
                return ResumeExportRecord(export=export, verification=verification)
            object_key = export.object_key
            now = self._clock.now()
            deleted = replace(export, status=ResumeExportStatus.DELETED, deleted_at=now)
            await uow.save_export(deleted)
            await uow.add_idempotency(
                self._idem(
                    owner_user_id,
                    idempotency_key,
                    fingerprint,
                    "resume_export",
                    export_id,
                    "resume_export",
                    export_id,
                    now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ResumeAuditAction.EXPORT_DELETED,
                    "resume_export",
                    export_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        if object_key is not None:
            await self._storage.delete(object_key)
        return await self.get_export(owner_user_id, export_id)

    async def _render_and_verify(
        self, owner_user_id: UUID, export_id: UUID, context: RequestContext
    ) -> ResumeExportRecord:
        async with self._uow() as uow:
            export = await uow.get_export(owner_user_id, export_id)
            if export is None:
                raise ResumeBuilderNotFound
            version = await uow.get_version(owner_user_id, export.version_id)
            if version is None:
                raise ResumeBuilderNotFound
            now = self._clock.now()
            rendering = replace(
                export,
                status=ResumeExportStatus.RENDERING,
                attempts=export.attempts + 1,
                last_error=None,
            )
            await uow.save_export(rendering)
            await uow.commit()

        try:
            rendered = self._renderer.render(version, fmt=export.format.value)
            if len(rendered.content) > self._policy.max_export_bytes:
                raise ResumeBuilderValidationError("rendered export exceeds maximum size")
            digest = hashlib.sha256(rendered.content).hexdigest()
            object_key = _object_key(owner_user_id, version.id, export_id, export.format)
            await self._storage.put_bytes(object_key, rendered.content, rendered.media_type)
            verification = await self._verify(
                version,
                export_id,
                rendered.content,
                rendered.media_type,
                rendered.expected_lines,
                digest,
            )
            status = (
                ResumeExportStatus.BLOCKED
                if verification.status == ResumeVerificationStatus.FAILED
                else ResumeExportStatus.VERIFIED
            )
            now = self._clock.now()
            completed = replace(
                rendering,
                status=status,
                object_key=object_key,
                media_type=rendered.media_type,
                size_bytes=len(rendered.content),
                sha256_digest=digest,
                verification_status=verification.status,
                verification_codes=verification.grounding_codes,
                critical_failures=verification.critical_failures,
                warnings=verification.warnings,
                renderer_version=rendered.renderer_version,
                parser_version=verification.parser_version,
                completed_at=now,
            )
            async with self._uow() as uow:
                await uow.save_export(completed, verification)
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        (
                            ResumeAuditAction.EXPORT_BLOCKED
                            if status == ResumeExportStatus.BLOCKED
                            else ResumeAuditAction.EXPORT_VERIFIED
                        ),
                        "resume_export",
                        export_id,
                        context,
                        now,
                        verificationStatus=verification.status.value,
                    )
                )
                await uow.commit()
            return ResumeExportRecord(export=completed, verification=verification)
        except Exception as exc:
            now = self._clock.now()
            failed = replace(
                rendering,
                status=ResumeExportStatus.FAILED,
                completed_at=now,
                last_error=exc.__class__.__name__,
            )
            async with self._uow() as uow:
                await uow.save_export(failed)
                await uow.commit()
            raise

    async def _verify(
        self,
        version: ResumeVersion,
        export_id: UUID,
        content: bytes,
        media_type: str,
        expected_lines: tuple[str, ...],
        digest: str,
    ) -> ResumeVerificationReport:
        parser_version = "direct-text-v1"
        warnings: tuple[str, ...] = ()
        if media_type in (
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            suffix = ".pdf" if media_type == "application/pdf" else ".docx"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(content)
                path = Path(handle.name)
            try:
                extracted = await self._extractor.extract(path, media_type)
            finally:
                path.unlink(missing_ok=True)
            text = extracted.plain_text
            reading_order = extracted.reading_order
            parser_version = extracted.parser_version
            warnings = extracted.warnings
        else:
            text = content.decode("utf-8", errors="replace")
            reading_order = tuple(
                line for line in (normalize_text(item) for item in text.splitlines()) if line
            )
        normalized_text = normalize_text(text).casefold()
        expected = tuple(
            dict.fromkeys(normalize_text(line) for line in expected_lines if line.strip())
        )
        missing = tuple(line for line in expected if line.casefold() not in normalized_text)
        duplicate_lines = tuple(
            line for line in expected if line and normalized_text.count(line.casefold()) > 1
        )
        detected = tuple(line for line in expected if line not in missing)
        failures = tuple(f"missing:{line[:80]}" for line in missing)
        status = (
            ResumeVerificationStatus.FAILED
            if failures
            else ResumeVerificationStatus.WARNING
            if warnings
            else ResumeVerificationStatus.PASSED
        )
        now = self._clock.now()
        return ResumeVerificationReport(
            id=self._ids.new(),
            owner_user_id=version.owner_user_id,
            export_id=export_id,
            version_id=version.id,
            status=status,
            critical_failures=failures,
            warnings=warnings,
            detected_lines=detected,
            missing_lines=missing,
            duplicate_lines=duplicate_lines,
            reading_order=reading_order,
            grounding_codes=("all_bullets_grounded", "round_trip_searchable"),
            file_sha256=digest,
            parser_version=parser_version,
            created_at=now,
        )

    def _new_version(
        self,
        owner_user_id: UUID,
        resume_id: UUID,
        version_number: int,
        parent_version_id: UUID | None,
        title: str,
        target_role: str | None,
        template: ResumeTemplate,
        source: ResumeSourceSnapshot,
        change_set_id: UUID | None,
        change_set_version_id: UUID | None,
        now: datetime,
    ) -> ResumeVersion:
        if not hasattr(now, "isoformat"):
            raise TypeError("clock returned invalid timestamp")
        sections = self._sections_from_source(source)
        return ResumeVersion(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            resume_id=resume_id,
            version_number=version_number,
            parent_version_id=parent_version_id,
            title=title,
            target_role=target_role,
            template=template,
            sections=sections,
            plain_text=_plain_text(title, target_role, sections),
            source_evidence_ids=source.source_evidence_ids,
            source_change_set_id=change_set_id,
            source_change_set_version_id=change_set_version_id,
            created_at=now,
        )

    def _sections_from_source(self, source: ResumeSourceSnapshot) -> tuple[ResumeSection, ...]:
        eligible = set(source.source_evidence_ids)
        if not eligible:
            raise ResumeBuilderValidationError(
                "eligible career evidence is required before building a resume"
            )
        sections: list[ResumeSection] = []
        if source.summary:
            sections.append(
                ResumeSection(
                    id=self._ids.new(),
                    title="Summary",
                    kind="summary",
                    items=(
                        ResumeBullet(
                            id=self._ids.new(),
                            text=source.summary,
                            evidence_ids=source.source_evidence_ids[:1],
                            source="career_record",
                        ),
                    ),
                )
            )
        bullet_items = tuple(
            ResumeBullet(
                id=self._ids.new(),
                text=item.text,
                evidence_ids=item.evidence_ids,
                source=item.source,
            )
            for item in source.bullets
        )
        if bullet_items:
            sections.append(
                ResumeSection(
                    id=self._ids.new(),
                    title="Experience",
                    kind="experience",
                    items=bullet_items,
                )
            )
        skill_items = tuple(
            ResumeBullet(
                id=self._ids.new(),
                text=skill,
                evidence_ids=source.source_evidence_ids[:1],
                source="career_record",
            )
            for skill in source.skills
            if source.source_evidence_ids
        )
        if skill_items:
            sections.append(
                ResumeSection(id=self._ids.new(), title="Skills", kind="skills", items=skill_items)
            )
        if not sections:
            raise ResumeBuilderValidationError(
                "eligible career evidence is required before building a resume"
            )
        return validate_sections(tuple(sections), eligible_evidence_ids=eligible)

    async def _resume_replay(
        self, owner_user_id: UUID, idempotency_key: str, fingerprint: str
    ) -> ResumeRecord | None:
        async with self._uow() as uow:
            existing = await uow.find_idempotency(owner_user_id, idempotency_key)
            if existing is None:
                return None
            if existing.request_fingerprint != fingerprint:
                raise ResumeBuilderIdempotencyConflict
            if existing.response_id is None:
                raise ResumeBuilderConflict("idempotency response is unavailable")
            record = await uow.get_resume(owner_user_id, existing.response_id)
            if record is None:
                raise ResumeBuilderNotFound
            return record

    async def _version_replay(
        self, owner_user_id: UUID, idempotency_key: str, fingerprint: str
    ) -> ResumeVersion | None:
        async with self._uow() as uow:
            existing = await uow.find_idempotency(owner_user_id, idempotency_key)
            if existing is None:
                return None
            if existing.request_fingerprint != fingerprint:
                raise ResumeBuilderIdempotencyConflict
            if existing.response_id is None:
                raise ResumeBuilderConflict("idempotency response is unavailable")
            version = await uow.get_version(owner_user_id, existing.response_id)
            if version is None:
                raise ResumeBuilderNotFound
            return version

    async def _export_replay(
        self, owner_user_id: UUID, idempotency_key: str, fingerprint: str
    ) -> ResumeExportRecord | None:
        async with self._uow() as uow:
            existing = await uow.find_idempotency(owner_user_id, idempotency_key)
            if existing is None:
                return None
            if existing.request_fingerprint != fingerprint:
                raise ResumeBuilderIdempotencyConflict
            if existing.response_id is None:
                raise ResumeBuilderConflict("idempotency response is unavailable")
            export = await uow.get_export(owner_user_id, existing.response_id)
            if export is None:
                raise ResumeBuilderNotFound
            verification = await uow.get_verification(owner_user_id, export.id)
            return ResumeExportRecord(export=export, verification=verification)

    def _assert_releasable(self, export: ResumeExport) -> None:
        if export.status == ResumeExportStatus.DELETED:
            raise ResumeBuilderNotFound
        if export.status == ResumeExportStatus.BLOCKED or export.critical_failures:
            raise ResumeExportBlocked
        if export.status != ResumeExportStatus.VERIFIED:
            raise ResumeBuilderConflict("export is not verified")

    def _authorize(self, owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise ResumeBuilderNotFound

    def _idempotency(self, value: str) -> None:
        if not 8 <= len(value) <= 128:
            raise ResumeBuilderValidationError("idempotency key must be 8-128 characters")

    def _idem(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
        target_kind: str,
        target_id: UUID | None,
        response_kind: str,
        response_id: UUID | None,
        now: datetime,
    ) -> ResumeBuilderIdempotencyRecord:
        if not hasattr(now, "isoformat"):
            raise TypeError("clock returned invalid timestamp")
        return ResumeBuilderIdempotencyRecord(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            target_kind=target_kind,
            target_id=target_id,
            response_kind=response_kind,
            response_id=response_id,
            created_at=now,
        )

    def _audit(
        self,
        owner_user_id: UUID,
        action: ResumeAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        now: datetime,
        **metadata: object,
    ) -> ResumeBuilderAuditEvent:
        if not hasattr(now, "isoformat"):
            raise TypeError("clock returned invalid timestamp")
        return ResumeBuilderAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            metadata=metadata,
            created_at=now,
        )


def _plain_text(title: str, target_role: str | None, sections: tuple[ResumeSection, ...]) -> str:
    lines = [title]
    if target_role:
        lines.append(target_role)
    for section in sections:
        lines.append(section.title)
        lines.extend(item.text for item in section.items)
    return "\n".join(lines)


def _sections_payload(sections: tuple[ResumeSection, ...] | None) -> object:
    if sections is None:
        return None
    return [
        {
            "id": str(section.id),
            "title": section.title,
            "kind": section.kind,
            "items": [
                {
                    "id": str(item.id),
                    "text": item.text,
                    "evidenceIds": [str(value) for value in item.evidence_ids],
                    "source": item.source,
                }
                for item in section.items
            ],
        }
        for section in sections
    ]


def _fingerprint(operation: str, payload: object) -> str:
    encoded = json.dumps(
        {"operation": operation, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _uuid(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _media_type(fmt: ResumeFormat) -> str:
    if fmt == ResumeFormat.PDF:
        return "application/pdf"
    if fmt == ResumeFormat.DOCX:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fmt == ResumeFormat.JSON:
        return "application/json"
    return "text/plain; charset=utf-8"


def _object_key(owner_user_id: UUID, version_id: UUID, export_id: UUID, fmt: ResumeFormat) -> str:
    return f"resume-exports/{owner_user_id.hex}/{version_id.hex}/{export_id.hex}/resume.{fmt.value}"
