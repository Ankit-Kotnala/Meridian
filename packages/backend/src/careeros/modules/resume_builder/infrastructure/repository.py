"""Async SQLAlchemy unit of work for Phase 7 resume builder."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.resume_builder.application.models import ResumeRecord
from careeros.modules.resume_builder.domain import (
    ResumeBuilderAuditEvent,
    ResumeBuilderConflict,
    ResumeBuilderIdempotencyRecord,
    ResumeBuilderUnavailable,
    ResumeBullet,
    ResumeDocument,
    ResumeDownloadIntent,
    ResumeExport,
    ResumeExportStatus,
    ResumeFormat,
    ResumeSection,
    ResumeTemplate,
    ResumeVerificationReport,
    ResumeVerificationStatus,
    ResumeVersion,
)

from .models import (
    ResumeBuilderAuditEventModel,
    ResumeBuilderIdempotencyModel,
    ResumeDownloadIntentModel,
    ResumeExportModel,
    ResumeModel,
    ResumeVerificationReportModel,
    ResumeVersionModel,
)


class SqlAlchemyResumeBuilderUnitOfWork:
    """Owner-scoped persistence boundary for resume builder use cases."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyResumeBuilderUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("resume builder unit of work is not active")
        return self._session

    async def list_resumes(self, owner_user_id: UUID) -> tuple[ResumeRecord, ...]:
        models = (
            await self.session.scalars(
                select(ResumeModel)
                .where(ResumeModel.owner_user_id == owner_user_id)
                .order_by(ResumeModel.updated_at.desc(), ResumeModel.id)
            )
        ).all()
        records: list[ResumeRecord] = []
        for model in models:
            record = await self._record_from_model(model)
            if record is not None:
                records.append(record)
        return tuple(records)

    async def add_resume(self, record: ResumeRecord) -> None:
        _validate_record_ownership(record)
        self.session.add(_resume_model(record.resume))
        await self._flush()
        self.session.add(_version_model(record.current_version))
        await self._flush()

    async def save_resume(self, record: ResumeRecord) -> None:
        _validate_record_ownership(record)
        await self._execute(
            update(ResumeModel)
            .where(
                ResumeModel.owner_user_id == record.resume.owner_user_id,
                ResumeModel.id == record.resume.id,
            )
            .values(**_resume_values(record.resume, include_identity=False))
        )

    async def get_resume(
        self, owner_user_id: UUID, resume_id: UUID, *, for_update: bool = False
    ) -> ResumeRecord | None:
        statement = select(ResumeModel).where(
            ResumeModel.owner_user_id == owner_user_id,
            ResumeModel.id == resume_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        if model is None:
            return None
        return await self._record_from_model(model)

    async def list_versions(
        self, owner_user_id: UUID, resume_id: UUID
    ) -> tuple[ResumeVersion, ...]:
        models = (
            await self.session.scalars(
                select(ResumeVersionModel)
                .where(
                    ResumeVersionModel.owner_user_id == owner_user_id,
                    ResumeVersionModel.resume_id == resume_id,
                )
                .order_by(ResumeVersionModel.version_number, ResumeVersionModel.id)
            )
        ).all()
        return tuple(_version(model) for model in models)

    async def get_version(self, owner_user_id: UUID, version_id: UUID) -> ResumeVersion | None:
        model = await self.session.scalar(
            select(ResumeVersionModel).where(
                ResumeVersionModel.owner_user_id == owner_user_id,
                ResumeVersionModel.id == version_id,
            )
        )
        return _version(model) if model is not None else None

    async def add_version(self, version: ResumeVersion) -> None:
        self.session.add(_version_model(version))
        await self._flush()

    async def set_current_version(
        self, owner_user_id: UUID, resume_id: UUID, version_id: UUID, *, now: datetime
    ) -> ResumeRecord | None:
        resume = await self.get_resume(owner_user_id, resume_id, for_update=True)
        if resume is None:
            return None
        version = await self.get_version(owner_user_id, version_id)
        if version is None or version.resume_id != resume_id:
            return None
        updated_resume = ResumeDocument(
            id=resume.resume.id,
            owner_user_id=owner_user_id,
            title=version.title,
            target_role=version.target_role,
            template=version.template,
            current_version_id=version.id,
            source_change_set_id=resume.resume.source_change_set_id,
            source_change_set_version_id=resume.resume.source_change_set_version_id,
            version=resume.resume.version + 1,
            created_at=resume.resume.created_at,
            updated_at=now,
        )
        updated = ResumeRecord(resume=updated_resume, current_version=version)
        await self.save_resume(updated)
        return updated

    async def find_export_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeExport | None:
        model = await self.session.scalar(
            select(ResumeExportModel).where(
                ResumeExportModel.owner_user_id == owner_user_id,
                ResumeExportModel.idempotency_key == idempotency_key,
            )
        )
        return _export(model) if model is not None else None

    async def add_export(
        self, export: ResumeExport, verification: ResumeVerificationReport | None = None
    ) -> None:
        self.session.add(_export_model(export))
        if verification is not None:
            self.session.add(_verification_model(verification))
        await self._flush()

    async def save_export(
        self, export: ResumeExport, verification: ResumeVerificationReport | None = None
    ) -> None:
        await self._execute(
            update(ResumeExportModel)
            .where(
                ResumeExportModel.owner_user_id == export.owner_user_id,
                ResumeExportModel.id == export.id,
            )
            .values(**_export_values(export, include_identity=False))
        )
        if verification is not None:
            existing = await self.get_verification(export.owner_user_id, export.id)
            if existing is None:
                self.session.add(_verification_model(verification))
            else:
                await self._execute(
                    update(ResumeVerificationReportModel)
                    .where(
                        ResumeVerificationReportModel.owner_user_id == verification.owner_user_id,
                        ResumeVerificationReportModel.export_id == verification.export_id,
                    )
                    .values(**_verification_values(verification, include_identity=False))
                )
        await self._flush()

    async def get_export(self, owner_user_id: UUID, export_id: UUID) -> ResumeExport | None:
        model = await self.session.scalar(
            select(ResumeExportModel).where(
                ResumeExportModel.owner_user_id == owner_user_id,
                ResumeExportModel.id == export_id,
            )
        )
        return _export(model) if model is not None else None

    async def get_verification(
        self, owner_user_id: UUID, export_id: UUID
    ) -> ResumeVerificationReport | None:
        model = await self.session.scalar(
            select(ResumeVerificationReportModel).where(
                ResumeVerificationReportModel.owner_user_id == owner_user_id,
                ResumeVerificationReportModel.export_id == export_id,
            )
        )
        return _verification(model) if model is not None else None

    async def find_download_intent_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeDownloadIntent | None:
        model = await self.session.scalar(
            select(ResumeDownloadIntentModel).where(
                ResumeDownloadIntentModel.owner_user_id == owner_user_id,
                ResumeDownloadIntentModel.idempotency_key == idempotency_key,
            )
        )
        return _download_intent(model) if model is not None else None

    async def add_download_intent(self, intent: ResumeDownloadIntent) -> None:
        self.session.add(_download_intent_model(intent))
        await self._flush()

    async def add_idempotency(self, record: ResumeBuilderIdempotencyRecord) -> None:
        self.session.add(_idempotency_model(record))
        await self._flush()

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeBuilderIdempotencyRecord | None:
        model = await self.session.scalar(
            select(ResumeBuilderIdempotencyModel).where(
                ResumeBuilderIdempotencyModel.owner_user_id == owner_user_id,
                ResumeBuilderIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_audit(self, event: ResumeBuilderAuditEvent) -> None:
        self.session.add(_audit_model(event))
        await self._flush()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _record_from_model(self, model: ResumeModel) -> ResumeRecord | None:
        if model.current_version_id is None:
            return None
        current = await self.get_version(model.owner_user_id, model.current_version_id)
        if current is None:
            return None
        return ResumeRecord(resume=_resume(model), current_version=current)

    async def _execute(self, statement: Any) -> None:
        try:
            await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)


class SqlAlchemyResumeBuilderUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> SqlAlchemyResumeBuilderUnitOfWork:
        return SqlAlchemyResumeBuilderUnitOfWork(self._database)


def _raise_integrity(exc: IntegrityError) -> None:
    raise ResumeBuilderConflict("resume builder persistence constraint failed") from exc


def _validate_record_ownership(record: ResumeRecord) -> None:
    owner_user_id = record.resume.owner_user_id
    if record.current_version.owner_user_id != owner_user_id:
        raise ResumeBuilderUnavailable("resume record ownership is inconsistent")
    if record.current_version.resume_id != record.resume.id:
        raise ResumeBuilderUnavailable("resume version does not belong to resume")


def _resume_values(resume: ResumeDocument, *, include_identity: bool) -> dict[str, object]:
    values: dict[str, object] = {
        "title": resume.title,
        "target_role": resume.target_role,
        "template": resume.template.value,
        "current_version_id": resume.current_version_id,
        "source_change_set_id": resume.source_change_set_id,
        "source_change_set_version_id": resume.source_change_set_version_id,
        "version": resume.version,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
    }
    if include_identity:
        values.update({"id": resume.id, "owner_user_id": resume.owner_user_id})
    return values


def _resume_model(resume: ResumeDocument) -> ResumeModel:
    return ResumeModel(**_resume_values(resume, include_identity=True))


def _resume(model: ResumeModel) -> ResumeDocument:
    return ResumeDocument(
        id=model.id,
        owner_user_id=model.owner_user_id,
        title=model.title,
        target_role=model.target_role,
        template=ResumeTemplate(model.template),
        current_version_id=model.current_version_id,
        source_change_set_id=model.source_change_set_id,
        source_change_set_version_id=model.source_change_set_version_id,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _version_values(version: ResumeVersion, *, include_identity: bool) -> dict[str, object]:
    values: dict[str, object] = {
        "resume_id": version.resume_id,
        "version_number": version.version_number,
        "parent_version_id": version.parent_version_id,
        "title": version.title,
        "target_role": version.target_role,
        "template": version.template.value,
        "sections": _sections_payload(version.sections),
        "plain_text": version.plain_text,
        "source_evidence_ids": [str(value) for value in version.source_evidence_ids],
        "source_change_set_id": version.source_change_set_id,
        "source_change_set_version_id": version.source_change_set_version_id,
        "created_at": version.created_at,
    }
    if include_identity:
        values.update({"id": version.id, "owner_user_id": version.owner_user_id})
    return values


def _version_model(version: ResumeVersion) -> ResumeVersionModel:
    return ResumeVersionModel(**_version_values(version, include_identity=True))


def _version(model: ResumeVersionModel) -> ResumeVersion:
    return ResumeVersion(
        id=model.id,
        owner_user_id=model.owner_user_id,
        resume_id=model.resume_id,
        version_number=model.version_number,
        parent_version_id=model.parent_version_id,
        title=model.title,
        target_role=model.target_role,
        template=ResumeTemplate(model.template),
        sections=_sections(model.sections),
        plain_text=model.plain_text,
        source_evidence_ids=tuple(UUID(value) for value in model.source_evidence_ids),
        source_change_set_id=model.source_change_set_id,
        source_change_set_version_id=model.source_change_set_version_id,
        created_at=model.created_at,
    )


def _sections_payload(sections: tuple[ResumeSection, ...]) -> list[dict[str, object]]:
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


def _sections(values: list[dict[str, object]]) -> tuple[ResumeSection, ...]:
    sections: list[ResumeSection] = []
    for raw_section in values:
        raw_items = cast(list[dict[str, object]], raw_section.get("items", []))
        items = tuple(
            ResumeBullet(
                id=UUID(str(raw_item["id"])),
                text=str(raw_item["text"]),
                evidence_ids=tuple(
                    UUID(str(value))
                    for value in cast(list[object], raw_item.get("evidenceIds", []))
                ),
                source=str(raw_item.get("source", "career_record")),
            )
            for raw_item in raw_items
        )
        sections.append(
            ResumeSection(
                id=UUID(str(raw_section["id"])),
                title=str(raw_section["title"]),
                kind=str(raw_section["kind"]),
                items=items,
            )
        )
    return tuple(sections)


def _export_values(export: ResumeExport, *, include_identity: bool) -> dict[str, object]:
    values: dict[str, object] = {
        "resume_id": export.resume_id,
        "version_id": export.version_id,
        "format": export.format.value,
        "status": export.status.value,
        "object_key": export.object_key,
        "media_type": export.media_type,
        "size_bytes": export.size_bytes,
        "sha256_digest": export.sha256_digest,
        "verification_status": (
            export.verification_status.value if export.verification_status is not None else None
        ),
        "verification_codes": list(export.verification_codes),
        "critical_failures": list(export.critical_failures),
        "warnings": list(export.warnings),
        "renderer_version": export.renderer_version,
        "parser_version": export.parser_version,
        "idempotency_key": export.idempotency_key,
        "idempotency_fingerprint": export.idempotency_fingerprint,
        "attempts": export.attempts,
        "requested_at": export.requested_at,
        "completed_at": export.completed_at,
        "deleted_at": export.deleted_at,
        "last_error": export.last_error,
    }
    if include_identity:
        values.update({"id": export.id, "owner_user_id": export.owner_user_id})
    return values


def _export_model(export: ResumeExport) -> ResumeExportModel:
    return ResumeExportModel(**_export_values(export, include_identity=True))


def _export(model: ResumeExportModel) -> ResumeExport:
    return ResumeExport(
        id=model.id,
        owner_user_id=model.owner_user_id,
        resume_id=model.resume_id,
        version_id=model.version_id,
        format=ResumeFormat(model.format),
        status=ResumeExportStatus(model.status),
        object_key=model.object_key,
        media_type=model.media_type,
        size_bytes=model.size_bytes,
        sha256_digest=model.sha256_digest,
        verification_status=(
            ResumeVerificationStatus(model.verification_status)
            if model.verification_status is not None
            else None
        ),
        verification_codes=tuple(model.verification_codes),
        critical_failures=tuple(model.critical_failures),
        warnings=tuple(model.warnings),
        renderer_version=model.renderer_version,
        parser_version=model.parser_version,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        attempts=model.attempts,
        requested_at=model.requested_at,
        completed_at=model.completed_at,
        deleted_at=model.deleted_at,
        last_error=model.last_error,
    )


def _verification_values(
    verification: ResumeVerificationReport, *, include_identity: bool
) -> dict[str, object]:
    values: dict[str, object] = {
        "export_id": verification.export_id,
        "version_id": verification.version_id,
        "status": verification.status.value,
        "critical_failures": list(verification.critical_failures),
        "warnings": list(verification.warnings),
        "detected_lines": list(verification.detected_lines),
        "missing_lines": list(verification.missing_lines),
        "duplicate_lines": list(verification.duplicate_lines),
        "reading_order": list(verification.reading_order),
        "grounding_codes": list(verification.grounding_codes),
        "file_sha256": verification.file_sha256,
        "parser_version": verification.parser_version,
        "created_at": verification.created_at,
    }
    if include_identity:
        values.update({"id": verification.id, "owner_user_id": verification.owner_user_id})
    return values


def _verification_model(verification: ResumeVerificationReport) -> ResumeVerificationReportModel:
    return ResumeVerificationReportModel(
        **_verification_values(verification, include_identity=True)
    )


def _verification(model: ResumeVerificationReportModel) -> ResumeVerificationReport:
    return ResumeVerificationReport(
        id=model.id,
        owner_user_id=model.owner_user_id,
        export_id=model.export_id,
        version_id=model.version_id,
        status=ResumeVerificationStatus(model.status),
        critical_failures=tuple(model.critical_failures),
        warnings=tuple(model.warnings),
        detected_lines=tuple(model.detected_lines),
        missing_lines=tuple(model.missing_lines),
        duplicate_lines=tuple(model.duplicate_lines),
        reading_order=tuple(model.reading_order),
        grounding_codes=tuple(model.grounding_codes),
        file_sha256=model.file_sha256,
        parser_version=model.parser_version,
        created_at=model.created_at,
    )


def _download_intent_model(intent: ResumeDownloadIntent) -> ResumeDownloadIntentModel:
    return ResumeDownloadIntentModel(
        id=intent.id,
        owner_user_id=intent.owner_user_id,
        export_id=intent.export_id,
        object_key=intent.object_key,
        url=intent.url,
        expires_at=intent.expires_at,
        idempotency_key=intent.idempotency_key,
        idempotency_fingerprint=intent.idempotency_fingerprint,
        created_at=intent.created_at,
    )


def _download_intent(model: ResumeDownloadIntentModel) -> ResumeDownloadIntent:
    return ResumeDownloadIntent(
        id=model.id,
        owner_user_id=model.owner_user_id,
        export_id=model.export_id,
        object_key=model.object_key,
        url=model.url,
        expires_at=model.expires_at,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        created_at=model.created_at,
    )


def _idempotency_model(record: ResumeBuilderIdempotencyRecord) -> ResumeBuilderIdempotencyModel:
    return ResumeBuilderIdempotencyModel(
        id=record.id,
        owner_user_id=record.owner_user_id,
        idempotency_key=record.idempotency_key,
        request_fingerprint=record.request_fingerprint,
        target_kind=record.target_kind,
        target_id=record.target_id,
        response_kind=record.response_kind,
        response_id=record.response_id,
        created_at=record.created_at,
    )


def _idempotency(model: ResumeBuilderIdempotencyModel) -> ResumeBuilderIdempotencyRecord:
    return ResumeBuilderIdempotencyRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint,
        target_kind=model.target_kind,
        target_id=model.target_id,
        response_kind=model.response_kind,
        response_id=model.response_id,
        created_at=model.created_at,
    )


def _audit_model(event: ResumeBuilderAuditEvent) -> ResumeBuilderAuditEventModel:
    return ResumeBuilderAuditEventModel(
        id=event.id,
        owner_user_id=event.owner_user_id,
        actor_user_id=event.actor_user_id,
        action=event.action.value,
        target_kind=event.target_kind,
        target_id=event.target_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        metadata_=event.metadata,
        created_at=event.created_at,
    )
