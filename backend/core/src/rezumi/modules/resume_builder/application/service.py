"""Resume builder application service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID

from rezumi.modules.resume_builder.domain import (
    MAX_ITEMS_PER_SECTION,
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
    ResumeEntityFact,
    ResumeEvidenceReference,
    ResumeExport,
    ResumeExportBlocked,
    ResumeExportOperation,
    ResumeExportOutboxMessage,
    ResumeExportStatus,
    ResumeFormat,
    ResumeLayout,
    ResumePersonalFact,
    ResumeSection,
    ResumeTemplate,
    ResumeVerificationReport,
    ResumeVersion,
    build_fidelity_manifest,
    entity_display_lines,
    fidelity_manifest_payload,
    fidelity_manifest_sha256,
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
    ResumeSourceBullet,
    ResumeSourceSnapshot,
    ResumeVersionList,
    UpdateResume,
)
from .ports import (
    Clock,
    IdentifierFactory,
    ResumeBuilderUnitOfWorkFactory,
    ResumeObjectStorage,
    ResumeSourceProvider,
)


class ResumeBuilderPolicy:
    download_ttl_seconds: int = 120
    max_export_bytes: int = 8 * 1024 * 1024
    export_max_attempts: int = 3
    export_cleanup_max_attempts: int = 3
    outbox_max_attempts: int = 5


class ResumeBuilderService:
    """Owner-scoped Phase 7 resume builder, versioning, export, and verification."""

    def __init__(
        self,
        *,
        unit_of_work: ResumeBuilderUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        sources: ResumeSourceProvider,
        storage: ResumeObjectStorage,
        policy: ResumeBuilderPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._sources = sources
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
                "layout": _layout_payload(command.layout),
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
            command.layout,
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
            layout=command.layout,
        )
        record = ResumeRecord(resume=resume, current_version=version)
        try:
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
        except ResumeBuilderIdempotencyConflict:
            replay = await self._resume_replay(
                owner_user_id,
                idempotency_key,
                fingerprint,
            )
            if replay is not None:
                return replay
            raise
        except ResumeBuilderConflict as exc:
            replay = await self._resume_replay(
                owner_user_id,
                idempotency_key,
                fingerprint,
            )
            if replay is not None:
                return replay
            raise exc
        return record

    async def get_resume(self, owner_user_id: UUID, resume_id: UUID) -> ResumeRecord:
        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id)
        if record is None:
            raise ResumeBuilderNotFound
        return record

    async def get_source_options(
        self,
        owner_user_id: UUID,
        resume_id: UUID,
    ) -> ResumeSourceSnapshot:
        """Return the current eligible, owner-scoped facts available to the editor."""

        record = await self.get_resume(owner_user_id, resume_id)
        return await self._sources.snapshot(
            owner_user_id,
            change_set_id=record.resume.source_change_set_id,
            change_set_version_id=record.resume.source_change_set_version_id,
        )

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
                "targetRoleProvided": command.target_role_provided,
                "template": command.template.value if command.template else None,
                "sections": _sections_payload(command.sections)
                if command.sections is not None
                else None,
                "personalFactIds": (
                    [str(value) for value in command.personal_fact_ids]
                    if command.personal_fact_ids is not None
                    else None
                ),
                "layout": (_layout_payload(command.layout) if command.layout is not None else None),
            },
        )
        replay = await self._resume_replay(owner_user_id, idempotency_key, fingerprint)
        if replay is not None:
            return replay

        source_record = await self.get_resume(owner_user_id, resume_id)
        source = await self._sources.snapshot(
            owner_user_id,
            change_set_id=source_record.resume.source_change_set_id,
            change_set_version_id=source_record.resume.source_change_set_version_id,
        )
        async with self._uow() as uow:
            record = await uow.get_resume(owner_user_id, resume_id, for_update=True)
            if record is None:
                raise ResumeBuilderNotFound
            if record.resume.version != expected_version:
                raise ResumeBuilderVersionConflict
            if (
                record.resume.source_change_set_id != source_record.resume.source_change_set_id
                or record.resume.source_change_set_version_id
                != source_record.resume.source_change_set_version_id
            ):
                raise ResumeBuilderVersionConflict
            title = (
                validate_title(command.title) if command.title is not None else record.resume.title
            )
            target_role = (
                validate_optional_target_role(command.target_role)
                if command.target_role_provided or command.target_role is not None
                else record.resume.target_role
            )
            template = command.template or record.resume.template
            layout = command.layout or record.resume.layout
            sections = (
                self._sections_with_authoritative_references(
                    command.sections,
                    current=record.current_version.sections,
                    source=source,
                )
                if command.sections is not None
                else self._validated_version_sections(record.current_version)
            )
            personal_facts = self._selected_personal_facts(
                command.personal_fact_ids,
                current=record.current_version.personal_facts,
                source=source.personal_facts,
            )
            entities = self._entities_for_sections(
                sections,
                current=record.current_version.entities,
                source=source.entities,
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
                plain_text=_plain_text(
                    title,
                    target_role,
                    sections,
                    personal_facts=personal_facts,
                    entities=entities,
                ),
                source_evidence_ids=_section_evidence_ids(sections),
                personal_facts=personal_facts,
                entities=entities,
                layout=layout,
                created_at=now,
            )
            resume = replace(
                record.resume,
                title=title,
                target_role=target_role,
                template=template,
                layout=layout,
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
            sections = self._validated_version_sections(record.current_version)
            versions = await uow.list_versions(owner_user_id, resume_id)
            next_number = max((item.version_number for item in versions), default=0) + 1
            now = self._clock.now()
            version = replace(
                record.current_version,
                id=self._ids.new(),
                version_number=next_number,
                parent_version_id=record.current_version.id,
                sections=sections,
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
            self._validated_version_sections(version)
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
            self._validated_version_sections(version)
            manifest = build_fidelity_manifest(version)
            manifest_payload = fidelity_manifest_payload(manifest)
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
                version_content_sha256=manifest.version_content_sha256,
                fidelity_manifest=manifest_payload,
                fidelity_manifest_sha256=fidelity_manifest_sha256(manifest),
                trace_id=context.trace_id,
                max_attempts=self._policy.export_max_attempts,
            )
            await uow.add_export(export)
            await uow.add_export_outbox(
                ResumeExportOutboxMessage(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    export_id=export_id,
                    operation=ResumeExportOperation.RENDER,
                    trace_id=context.trace_id,
                    available_at=now,
                    attempts=0,
                    max_attempts=self._policy.outbox_max_attempts,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    published_at=None,
                    dead_lettered_at=None,
                    last_error=None,
                    created_at=now,
                )
            )
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

        return ResumeExportRecord(export=export, verification=None)

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
            if export.status in {
                ResumeExportStatus.DELETION_PENDING,
                ResumeExportStatus.DELETING,
                ResumeExportStatus.DELETION_RETRY_WAIT,
                ResumeExportStatus.DELETION_DEAD_LETTERED,
            }:
                verification = await uow.get_verification(owner_user_id, export_id)
                return ResumeExportRecord(export=export, verification=verification)
            now = self._clock.now()
            pending = replace(
                export,
                status=ResumeExportStatus.DELETION_PENDING,
                fence=export.fence + 1,
                execution_token_hash=None,
                lease_expires_at=None,
                retry_at=None,
                dead_lettered_at=None,
                cleanup_attempts=0,
                cleanup_max_attempts=self._policy.export_cleanup_max_attempts,
                deleted_at=None,
                last_error=None,
            )
            await uow.save_export(pending)
            await uow.add_export_outbox(
                ResumeExportOutboxMessage(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    export_id=export_id,
                    operation=ResumeExportOperation.DELETE,
                    trace_id=context.trace_id,
                    available_at=now,
                    attempts=0,
                    max_attempts=self._policy.outbox_max_attempts,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    published_at=None,
                    dead_lettered_at=None,
                    last_error=None,
                    created_at=now,
                )
            )
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
                    ResumeAuditAction.EXPORT_DELETION_REQUESTED,
                    "resume_export",
                    export_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return await self.get_export(owner_user_id, export_id)

    def _new_version(
        self,
        owner_user_id: UUID,
        resume_id: UUID,
        version_number: int,
        parent_version_id: UUID | None,
        title: str,
        target_role: str | None,
        template: ResumeTemplate,
        layout: ResumeLayout,
        source: ResumeSourceSnapshot,
        change_set_id: UUID | None,
        change_set_version_id: UUID | None,
        now: datetime,
    ) -> ResumeVersion:
        if not hasattr(now, "isoformat"):
            raise TypeError("clock returned invalid timestamp")
        sections = self._sections_from_source(source)
        personal_facts = _initial_personal_facts(source.personal_facts)
        entities = self._entities_for_sections(
            sections,
            current=(),
            source=source.entities,
        )
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
            plain_text=_plain_text(
                title,
                target_role,
                sections,
                personal_facts=personal_facts,
                entities=entities,
            ),
            source_evidence_ids=_section_evidence_ids(sections),
            source_change_set_id=change_set_id,
            source_change_set_version_id=change_set_version_id,
            created_at=now,
            personal_facts=personal_facts,
            entities=entities,
            layout=layout,
        )

    def _sections_from_source(self, source: ResumeSourceSnapshot) -> tuple[ResumeSection, ...]:
        eligible = set(source.source_evidence_ids)
        if not eligible:
            raise ResumeBuilderValidationError(
                "eligible career evidence is required before building a resume"
            )
        grouped: dict[str, list[ResumeSourceBullet]] = {}
        for item in source.bullets:
            kind = normalize_text(item.section_kind).casefold()
            if kind not in {
                "awards",
                "credentials",
                "education",
                "experience",
                "projects",
                "publications",
                "skills",
                "summary",
                "volunteering",
            }:
                raise ResumeBuilderValidationError("resume source section kind is invalid")
            grouped.setdefault(kind, []).append(item)
        sections: list[ResumeSection] = []
        titles = {
            "awards": "Awards",
            "credentials": "Credentials",
            "education": "Education",
            "experience": "Experience",
            "projects": "Projects",
            "publications": "Publications",
            "skills": "Skills",
            "summary": "Professional Summary",
            "volunteering": "Volunteering",
        }
        for kind, source_items in grouped.items():
            for offset in range(0, len(source_items), MAX_ITEMS_PER_SECTION):
                items = tuple(
                    ResumeBullet(
                        id=self._ids.new(),
                        text=item.text,
                        evidence_ids=item.evidence_ids,
                        source=item.source,
                        evidence_references=item.evidence_references,
                        entity_id=item.entity_id,
                    )
                    for item in source_items[offset : offset + MAX_ITEMS_PER_SECTION]
                )
                sections.append(
                    ResumeSection(
                        id=self._ids.new(),
                        title=titles[kind],
                        kind=kind,
                        items=items,
                    )
                )
        if not sections:
            raise ResumeBuilderValidationError(
                "eligible career evidence is required before building a resume"
            )
        return validate_sections(
            tuple(sections),
            eligible_evidence_ids=eligible,
            eligible_entity_ids={entity.id for entity in source.entities},
        )

    def _validated_version_sections(
        self,
        version: ResumeVersion,
    ) -> tuple[ResumeSection, ...]:
        return validate_resume_version(version)

    def _sections_with_authoritative_references(
        self,
        sections: tuple[ResumeSection, ...],
        *,
        current: tuple[ResumeSection, ...],
        source: ResumeSourceSnapshot,
    ) -> tuple[ResumeSection, ...]:
        current_by_id = {
            item.id: item
            for section in current
            for item in section.items
            if _bullet_references_match(item)
        }
        source_by_key: dict[
            tuple[str, tuple[UUID, ...], str, UUID | None],
            tuple[ResumeEvidenceReference, ...] | None,
        ] = {}
        for source_item in source.bullets:
            key = _bullet_key(
                source_item.text,
                source_item.evidence_ids,
                source_item.source,
                source_item.entity_id,
            )
            source_references = source_item.evidence_references
            existing = source_by_key.get(key)
            if existing is not None and existing != source_references:
                source_by_key[key] = None
            elif key not in source_by_key:
                source_by_key[key] = source_references

        attached: list[ResumeSection] = []
        for section in sections:
            items: list[ResumeBullet] = []
            for bullet in section.items:
                key = _bullet_key(
                    bullet.text,
                    bullet.evidence_ids,
                    bullet.source,
                    bullet.entity_id,
                )
                current_item = current_by_id.get(bullet.id)
                authoritative_references: tuple[ResumeEvidenceReference, ...] | None
                if (
                    current_item is not None
                    and _bullet_key(
                        current_item.text,
                        current_item.evidence_ids,
                        current_item.source,
                        current_item.entity_id,
                    )
                    == key
                ):
                    authoritative_references = current_item.evidence_references
                else:
                    authoritative_references = source_by_key.get(key)
                if not authoritative_references:
                    raise ResumeBuilderValidationError(
                        "new or changed resume bullets must exactly match an "
                        "eligible evidence-backed source fact"
                    )
                items.append(
                    ResumeBullet(
                        id=bullet.id,
                        text=bullet.text,
                        evidence_ids=bullet.evidence_ids,
                        source=bullet.source,
                        evidence_references=authoritative_references,
                        entity_id=bullet.entity_id,
                    )
                )
            attached.append(
                ResumeSection(
                    id=section.id,
                    title=section.title,
                    kind=section.kind,
                    items=tuple(items),
                )
            )
        return validate_sections(
            tuple(attached),
            eligible_evidence_ids=set(source.source_evidence_ids),
            eligible_entity_ids={
                *(entity.id for entity in source.entities),
                *(
                    item.entity_id
                    for section in current
                    for item in section.items
                    if item.entity_id is not None
                ),
            },
        )

    def _selected_personal_facts(
        self,
        selected_ids: tuple[UUID, ...] | None,
        *,
        current: tuple[ResumePersonalFact, ...],
        source: tuple[ResumePersonalFact, ...],
    ) -> tuple[ResumePersonalFact, ...]:
        if selected_ids is None:
            return current
        if len(set(selected_ids)) != len(selected_ids) or len(selected_ids) > 20:
            raise ResumeBuilderValidationError("resume personal fact selection is invalid")
        current_by_id = {fact.id: fact for fact in current}
        source_by_id = {fact.id: fact for fact in source}
        selected: list[ResumePersonalFact] = []
        for fact_id in selected_ids:
            fact = current_by_id.get(fact_id) or source_by_id.get(fact_id)
            if fact is None:
                raise ResumeBuilderValidationError(
                    "resume personal facts must come from the confirmed Career Record"
                )
            selected.append(fact)
        if len([fact for fact in selected if fact.kind == "name"]) > 1:
            raise ResumeBuilderValidationError("a resume may include only one confirmed name")
        return tuple(selected)

    def _entities_for_sections(
        self,
        sections: tuple[ResumeSection, ...],
        *,
        current: tuple[ResumeEntityFact, ...],
        source: tuple[ResumeEntityFact, ...],
    ) -> tuple[ResumeEntityFact, ...]:
        required = tuple(
            dict.fromkeys(
                item.entity_id
                for section in sections
                for item in section.items
                if item.entity_id is not None
            )
        )
        current_by_id = {entity.id: entity for entity in current}
        source_by_id = {entity.id: entity for entity in source}
        entities: list[ResumeEntityFact] = []
        for entity_id in required:
            entity = current_by_id.get(entity_id) or source_by_id.get(entity_id)
            if entity is None or not entity.evidence_ids:
                raise ResumeBuilderValidationError(
                    "resume entities must come from evidence-linked confirmed Career Record facts"
                )
            entities.append(entity)
        return tuple(entities)

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


def validate_resume_version(version: ResumeVersion) -> tuple[ResumeSection, ...]:
    sections = validate_sections(
        version.sections,
        eligible_evidence_ids=set(version.source_evidence_ids),
        eligible_entity_ids={entity.id for entity in version.entities},
    )
    if _section_evidence_ids(sections) != version.source_evidence_ids:
        raise ResumeBuilderValidationError(
            "resume version provenance ledger is incomplete or legacy"
        )
    entities = {entity.id: entity for entity in version.entities}
    for section in sections:
        for item in section.items:
            if item.entity_id is None:
                continue
            entity = entities[item.entity_id]
            if not set(item.evidence_ids).intersection(entity.evidence_ids):
                raise ResumeBuilderValidationError(
                    "resume entity display facts require linked bullet evidence"
                )
    if len({fact.id for fact in version.personal_facts}) != len(version.personal_facts):
        raise ResumeBuilderValidationError("resume personal fact ids must be unique")
    if len([fact for fact in version.personal_facts if fact.kind == "name"]) > 1:
        raise ResumeBuilderValidationError("a resume may include only one confirmed name")
    return sections


def _plain_text(
    _title: str,
    target_role: str | None,
    sections: tuple[ResumeSection, ...],
    *,
    personal_facts: tuple[ResumePersonalFact, ...],
    entities: tuple[ResumeEntityFact, ...],
) -> str:
    names = [fact.value for fact in personal_facts if fact.kind == "name"]
    contacts = [fact.value for fact in personal_facts if fact.kind != "name"]
    lines = [*names]
    if contacts:
        lines.append(" | ".join(contacts))
    if target_role:
        lines.append(target_role)
    entity_by_id = {entity.id: entity for entity in entities}
    emitted_entities: set[UUID] = set()
    for section in sections:
        lines.append(section.title)
        for item in section.items:
            entity = entity_by_id.get(item.entity_id) if item.entity_id is not None else None
            if entity is not None and entity.id not in emitted_entities:
                lines.extend(entity_display_lines(entity))
                emitted_entities.add(entity.id)
            lines.append(item.text)
    return "\n".join(lines)


def _section_evidence_ids(sections: tuple[ResumeSection, ...]) -> tuple[UUID, ...]:
    return tuple(
        dict.fromkeys(
            evidence_id
            for section in sections
            for item in section.items
            for evidence_id in item.evidence_ids
        )
    )


def _initial_personal_facts(
    facts: tuple[ResumePersonalFact, ...],
) -> tuple[ResumePersonalFact, ...]:
    by_kind: dict[str, list[ResumePersonalFact]] = {}
    for fact in facts:
        by_kind.setdefault(fact.kind, []).append(fact)
    selected: list[ResumePersonalFact] = []
    for kind in ("name", "email", "phone", "location", "link"):
        candidates = by_kind.get(kind, [])
        if not candidates:
            continue
        selected.append(next((fact for fact in candidates if fact.is_primary), candidates[0]))
    return tuple(selected)


def _bullet_key(
    text: str,
    evidence_ids: tuple[UUID, ...],
    source: str,
    entity_id: UUID | None,
) -> tuple[str, tuple[UUID, ...], str, UUID | None]:
    return (
        normalize_text(text),
        tuple(dict.fromkeys(evidence_ids)),
        normalize_text(source) or "career_record",
        entity_id,
    )


def _bullet_references_match(item: ResumeBullet) -> bool:
    references_by_id = {reference.evidence_id: reference for reference in item.evidence_references}
    return (
        len(references_by_id) == len(item.evidence_references)
        and set(references_by_id) == set(item.evidence_ids)
        and all(
            reference.claim_sha256
            == hashlib.sha256(normalize_text(item.text).encode("utf-8")).hexdigest()
            for reference in item.evidence_references
        )
    )


def version_provenance_failures(version: ResumeVersion) -> tuple[str, ...]:
    failures: list[str] = []
    seen_item_ids: set[UUID] = set()
    revisions_by_evidence: dict[UUID, tuple[UUID, int, str]] = {}
    for section in version.sections:
        for item in section.items:
            if item.id in seen_item_ids:
                failures.append(f"duplicate_bullet_id:{item.id}")
            seen_item_ids.add(item.id)
            if not _bullet_references_match(item):
                failures.append(f"invalid_provenance:{item.id}")
            for reference in item.evidence_references:
                revision_key = (
                    reference.evidence_revision_id,
                    reference.revision_number,
                    reference.statement_sha256,
                )
                previous = revisions_by_evidence.setdefault(
                    reference.evidence_id,
                    revision_key,
                )
                if previous != revision_key:
                    failures.append(f"conflicting_evidence_revision:{reference.evidence_id}")
    if (
        len(set(version.source_evidence_ids)) != len(version.source_evidence_ids)
        or _section_evidence_ids(version.sections) != version.source_evidence_ids
    ):
        failures.append("incomplete_version_evidence_ledger")
    return tuple(dict.fromkeys(failures))


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
                    "entityId": str(item.entity_id) if item.entity_id is not None else None,
                }
                for item in section.items
            ],
        }
        for section in sections
    ]


def _layout_payload(layout: ResumeLayout) -> dict[str, object]:
    return {
        "fontFamily": layout.font_family.value,
        "fontSizePt": layout.font_size_pt,
        "lineSpacing": layout.line_spacing.value,
        "margins": layout.margins.value,
        "pageLimit": layout.page_limit,
        "pageSize": layout.page_size.value,
    }


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
