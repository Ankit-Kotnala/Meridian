"""Async SQLAlchemy unit of work for Phase 7 resume builder."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.resume_builder.application.models import ResumeRecord
from rezumi.modules.resume_builder.domain import (
    ResumeBuilderAuditEvent,
    ResumeBuilderConflict,
    ResumeBuilderIdempotencyConflict,
    ResumeBuilderIdempotencyRecord,
    ResumeBuilderUnavailable,
    ResumeBullet,
    ResumeDocument,
    ResumeDownloadIntent,
    ResumeEntityFact,
    ResumeEvidenceLinkBasis,
    ResumeEvidenceReference,
    ResumeExport,
    ResumeExportObjectCleanup,
    ResumeExportOperation,
    ResumeExportOutboxMessage,
    ResumeExportStatus,
    ResumeFontFamily,
    ResumeFormat,
    ResumeLayout,
    ResumeLineSpacing,
    ResumeMarginSize,
    ResumePageSize,
    ResumePartialDate,
    ResumePersonalFact,
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
    ResumeExportObjectCleanupModel,
    ResumeExportOutboxModel,
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
        versions: list[ResumeVersion] = []
        for model in models:
            try:
                versions.append(_version(model))
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(versions)

    async def get_version(self, owner_user_id: UUID, version_id: UUID) -> ResumeVersion | None:
        model = await self.session.scalar(
            select(ResumeVersionModel).where(
                ResumeVersionModel.owner_user_id == owner_user_id,
                ResumeVersionModel.id == version_id,
            )
        )
        if model is None:
            return None
        try:
            return _version(model)
        except (KeyError, TypeError, ValueError):
            return None

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

    async def get_export_system(
        self, export_id: UUID, *, for_update: bool = False
    ) -> ResumeExport | None:
        statement = select(ResumeExportModel).where(ResumeExportModel.id == export_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _export(model) if model is not None else None

    async def list_recoverable_exports(self, now: datetime, limit: int) -> tuple[ResumeExport, ...]:
        models = (
            await self.session.scalars(
                select(ResumeExportModel)
                .where(
                    ResumeExportModel.deleted_at.is_(None),
                    or_(
                        ResumeExportModel.status == ResumeExportStatus.PENDING.value,
                        (
                            (ResumeExportModel.status == ResumeExportStatus.RETRY_WAIT.value)
                            & (ResumeExportModel.retry_at <= now)
                        ),
                        (
                            (ResumeExportModel.status == ResumeExportStatus.RENDERING.value)
                            & (ResumeExportModel.lease_expires_at <= now)
                        ),
                        ResumeExportModel.status == ResumeExportStatus.DELETION_PENDING.value,
                        (
                            (
                                ResumeExportModel.status
                                == ResumeExportStatus.DELETION_RETRY_WAIT.value
                            )
                            & (ResumeExportModel.retry_at <= now)
                        ),
                        (
                            (ResumeExportModel.status == ResumeExportStatus.DELETING.value)
                            & (ResumeExportModel.lease_expires_at <= now)
                        ),
                    ),
                )
                .order_by(ResumeExportModel.requested_at, ResumeExportModel.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return tuple(_export(model) for model in models)

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

    async def add_export_outbox(self, message: ResumeExportOutboxMessage) -> None:
        self.session.add(_export_outbox_model(message))
        await self._flush()

    async def claim_export_outbox(
        self, now: datetime, lease_expires_at: datetime, limit: int
    ) -> tuple[ResumeExportOutboxMessage, ...]:
        models = (
            await self.session.scalars(
                select(ResumeExportOutboxModel)
                .where(
                    ResumeExportOutboxModel.available_at <= now,
                    ResumeExportOutboxModel.published_at.is_(None),
                    ResumeExportOutboxModel.dead_lettered_at.is_(None),
                    or_(
                        ResumeExportOutboxModel.lease_token.is_(None),
                        ResumeExportOutboxModel.lease_expires_at <= now,
                    ),
                )
                .order_by(ResumeExportOutboxModel.available_at, ResumeExportOutboxModel.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        claimed: list[ResumeExportOutboxMessage] = []
        for model in models:
            model.lease_token = uuid4()
            model.leased_at = now
            model.lease_expires_at = lease_expires_at
            claimed.append(_export_outbox(model))
        await self._flush()
        return tuple(claimed)

    async def save_export_outbox(
        self,
        message: ResumeExportOutboxMessage,
        *,
        expected_lease_token: UUID,
    ) -> bool:
        try:
            result = cast(
                CursorResult[Any],
                await self.session.execute(
                    update(ResumeExportOutboxModel)
                    .where(
                        ResumeExportOutboxModel.id == message.id,
                        ResumeExportOutboxModel.lease_token == expected_lease_token,
                        ResumeExportOutboxModel.published_at.is_(None),
                        ResumeExportOutboxModel.dead_lettered_at.is_(None),
                    )
                    .values(**_export_outbox_values(message, include_identity=False))
                ),
            )
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        return result.rowcount == 1

    async def has_active_export_outbox(
        self,
        export_id: UUID,
        operation: ResumeExportOperation,
    ) -> bool:
        message_id = await self.session.scalar(
            select(ResumeExportOutboxModel.id)
            .where(
                ResumeExportOutboxModel.export_id == export_id,
                ResumeExportOutboxModel.operation == operation.value,
                ResumeExportOutboxModel.published_at.is_(None),
                ResumeExportOutboxModel.dead_lettered_at.is_(None),
            )
            .limit(1)
        )
        return message_id is not None

    async def add_export_object_cleanup(self, cleanup: ResumeExportObjectCleanup) -> None:
        self.session.add(_export_object_cleanup_model(cleanup))
        await self._flush()

    async def get_export_object_cleanup(
        self,
        owner_user_id: UUID,
        export_id: UUID,
        attempt_fence: int,
        *,
        for_update: bool = False,
    ) -> ResumeExportObjectCleanup | None:
        statement = select(ResumeExportObjectCleanupModel).where(
            ResumeExportObjectCleanupModel.owner_user_id == owner_user_id,
            ResumeExportObjectCleanupModel.export_id == export_id,
            ResumeExportObjectCleanupModel.attempt_fence == attempt_fence,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _export_object_cleanup(model) if model is not None else None

    async def list_due_export_object_cleanups(
        self, now: datetime, limit: int
    ) -> tuple[ResumeExportObjectCleanup, ...]:
        models = (
            await self.session.scalars(
                select(ResumeExportObjectCleanupModel)
                .where(
                    ResumeExportObjectCleanupModel.completed_at.is_(None),
                    ResumeExportObjectCleanupModel.cancelled_at.is_(None),
                    ResumeExportObjectCleanupModel.dead_lettered_at.is_(None),
                    ResumeExportObjectCleanupModel.not_before <= now,
                )
                .order_by(
                    ResumeExportObjectCleanupModel.not_before,
                    ResumeExportObjectCleanupModel.created_at,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return tuple(_export_object_cleanup(model) for model in models)

    async def save_export_object_cleanup(self, cleanup: ResumeExportObjectCleanup) -> None:
        await self._execute(
            update(ResumeExportObjectCleanupModel)
            .where(
                ResumeExportObjectCleanupModel.owner_user_id == cleanup.owner_user_id,
                ResumeExportObjectCleanupModel.id == cleanup.id,
            )
            .values(**_export_object_cleanup_values(cleanup, include_identity=False))
        )
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
        try:
            current = await self.get_version(model.owner_user_id, model.current_version_id)
            if current is None:
                return None
            return ResumeRecord(resume=_resume(model), current_version=current)
        except (KeyError, TypeError, ValueError):
            return None

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
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name in {
        "uq_resume_builder_idempotency_owner_key",
        "uq_resume_exports_owner_idempotency",
        "uq_resume_download_intents_owner_idempotency",
    }:
        raise ResumeBuilderIdempotencyConflict from exc
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
        "layout": _layout_payload(resume.layout),
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
        layout=_layout(model.layout),
    )


def _layout_payload(layout: ResumeLayout) -> dict[str, object]:
    return {
        "fontFamily": layout.font_family.value,
        "fontSizePt": layout.font_size_pt,
        "lineSpacing": layout.line_spacing.value,
        "margins": layout.margins.value,
        "pageLimit": layout.page_limit,
        "pageSize": layout.page_size.value,
    }


def _layout(value: dict[str, object]) -> ResumeLayout:
    return ResumeLayout(
        page_size=ResumePageSize(str(value["pageSize"])),
        page_limit=int(str(value["pageLimit"])),
        font_family=ResumeFontFamily(str(value["fontFamily"])),
        font_size_pt=int(str(value["fontSizePt"])),
        line_spacing=ResumeLineSpacing(str(value["lineSpacing"])),
        margins=ResumeMarginSize(str(value["margins"])),
    )


def _personal_facts_payload(
    facts: tuple[ResumePersonalFact, ...],
) -> list[dict[str, object]]:
    return [
        {
            "id": str(fact.id),
            "kind": fact.kind,
            "value": fact.value,
            "label": fact.label,
            "isPrimary": fact.is_primary,
        }
        for fact in facts
    ]


def _personal_facts(values: list[dict[str, object]]) -> tuple[ResumePersonalFact, ...]:
    return tuple(
        ResumePersonalFact(
            id=UUID(str(value["id"])),
            kind=str(value["kind"]),
            value=str(value["value"]),
            label=str(value["label"]) if value.get("label") is not None else None,
            is_primary=bool(value["isPrimary"]),
        )
        for value in values
    )


def _entities_payload(entities: tuple[ResumeEntityFact, ...]) -> list[dict[str, object]]:
    return [
        {
            "id": str(entity.id),
            "kind": entity.kind,
            "title": entity.title,
            "organization": entity.organization,
            "officialTitle": entity.official_title,
            "displayTitle": entity.display_title,
            "location": entity.location,
            "startDate": _partial_date_payload(entity.start_date),
            "endDate": _partial_date_payload(entity.end_date),
            "isCurrent": entity.is_current,
            "evidenceIds": [str(value) for value in entity.evidence_ids],
        }
        for entity in entities
    ]


def _entities(values: list[dict[str, object]]) -> tuple[ResumeEntityFact, ...]:
    return tuple(
        ResumeEntityFact(
            id=UUID(str(value["id"])),
            kind=str(value["kind"]),
            title=str(value["title"]),
            organization=(
                str(value["organization"]) if value.get("organization") is not None else None
            ),
            official_title=(
                str(value["officialTitle"]) if value.get("officialTitle") is not None else None
            ),
            display_title=(
                str(value["displayTitle"]) if value.get("displayTitle") is not None else None
            ),
            location=str(value["location"]) if value.get("location") is not None else None,
            start_date=_partial_date(value.get("startDate")),
            end_date=_partial_date(value.get("endDate")),
            is_current=bool(value["isCurrent"]),
            evidence_ids=tuple(
                UUID(str(item)) for item in cast(list[object], value.get("evidenceIds", []))
            ),
        )
        for value in values
    )


def _partial_date_payload(value: ResumePartialDate | None) -> dict[str, object] | None:
    return {"year": value.year, "month": value.month} if value is not None else None


def _partial_date(value: object) -> ResumePartialDate | None:
    if value is None:
        return None
    raw = cast(dict[str, object], value)
    return ResumePartialDate(
        year=int(str(raw["year"])),
        month=int(str(raw["month"])) if raw.get("month") is not None else None,
    )


def _version_values(version: ResumeVersion, *, include_identity: bool) -> dict[str, object]:
    values: dict[str, object] = {
        "resume_id": version.resume_id,
        "version_number": version.version_number,
        "parent_version_id": version.parent_version_id,
        "title": version.title,
        "target_role": version.target_role,
        "template": version.template.value,
        "layout": _layout_payload(version.layout),
        "personal_facts": _personal_facts_payload(version.personal_facts),
        "entities": _entities_payload(version.entities),
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
        personal_facts=_personal_facts(model.personal_facts),
        entities=_entities(model.entities),
        layout=_layout(model.layout),
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
                    "entityId": str(item.entity_id) if item.entity_id is not None else None,
                    "evidenceReferences": [
                        {
                            "evidenceId": str(reference.evidence_id),
                            "evidenceRevisionId": str(reference.evidence_revision_id),
                            "revisionNumber": reference.revision_number,
                            "statementSha256": reference.statement_sha256,
                            "claimSha256": reference.claim_sha256,
                            "linkBasis": reference.link_basis.value,
                            "sourceSkillId": (
                                str(reference.source_skill_id)
                                if reference.source_skill_id is not None
                                else None
                            ),
                        }
                        for reference in item.evidence_references
                    ],
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
                entity_id=(
                    UUID(str(raw_item["entityId"]))
                    if raw_item.get("entityId") is not None
                    else None
                ),
                evidence_references=tuple(
                    ResumeEvidenceReference(
                        evidence_id=UUID(str(reference["evidenceId"])),
                        evidence_revision_id=UUID(str(reference["evidenceRevisionId"])),
                        revision_number=int(str(reference["revisionNumber"])),
                        statement_sha256=str(reference["statementSha256"]),
                        claim_sha256=str(reference["claimSha256"]),
                        link_basis=ResumeEvidenceLinkBasis(str(reference["linkBasis"])),
                        source_skill_id=(
                            UUID(str(reference["sourceSkillId"]))
                            if reference.get("sourceSkillId") is not None
                            else None
                        ),
                    )
                    for reference in cast(
                        list[dict[str, object]],
                        raw_item.get("evidenceReferences", []),
                    )
                ),
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
        "version_content_sha256": export.version_content_sha256,
        "fidelity_manifest": export.fidelity_manifest,
        "fidelity_manifest_sha256": export.fidelity_manifest_sha256,
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
        "trace_id": export.trace_id,
        "attempts": export.attempts,
        "max_attempts": export.max_attempts,
        "cleanup_attempts": export.cleanup_attempts,
        "cleanup_max_attempts": export.cleanup_max_attempts,
        "fence": export.fence,
        "execution_token_hash": export.execution_token_hash,
        "lease_expires_at": export.lease_expires_at,
        "retry_at": export.retry_at,
        "dead_lettered_at": export.dead_lettered_at,
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
        version_content_sha256=model.version_content_sha256,
        fidelity_manifest=model.fidelity_manifest,
        fidelity_manifest_sha256=model.fidelity_manifest_sha256,
        trace_id=model.trace_id,
        max_attempts=model.max_attempts,
        fence=model.fence,
        execution_token_hash=model.execution_token_hash,
        lease_expires_at=model.lease_expires_at,
        retry_at=model.retry_at,
        dead_lettered_at=model.dead_lettered_at,
        cleanup_attempts=model.cleanup_attempts,
        cleanup_max_attempts=model.cleanup_max_attempts,
    )


def _export_outbox_values(
    message: ResumeExportOutboxMessage, *, include_identity: bool
) -> dict[str, object]:
    values: dict[str, object] = {
        "export_id": message.export_id,
        "operation": message.operation.value,
        "trace_id": message.trace_id,
        "available_at": message.available_at,
        "attempts": message.attempts,
        "max_attempts": message.max_attempts,
        "lease_token": message.lease_token,
        "leased_at": message.leased_at,
        "lease_expires_at": message.lease_expires_at,
        "published_at": message.published_at,
        "dead_lettered_at": message.dead_lettered_at,
        "last_error": message.last_error,
        "created_at": message.created_at,
    }
    if include_identity:
        values.update({"id": message.id, "owner_user_id": message.owner_user_id})
    return values


def _export_outbox_model(message: ResumeExportOutboxMessage) -> ResumeExportOutboxModel:
    return ResumeExportOutboxModel(**_export_outbox_values(message, include_identity=True))


def _export_outbox(model: ResumeExportOutboxModel) -> ResumeExportOutboxMessage:
    return ResumeExportOutboxMessage(
        id=model.id,
        owner_user_id=model.owner_user_id,
        export_id=model.export_id,
        operation=ResumeExportOperation(model.operation),
        trace_id=model.trace_id,
        available_at=model.available_at,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        lease_token=model.lease_token,
        leased_at=model.leased_at,
        lease_expires_at=model.lease_expires_at,
        published_at=model.published_at,
        dead_lettered_at=model.dead_lettered_at,
        last_error=model.last_error,
        created_at=model.created_at,
    )


def _export_object_cleanup_values(
    cleanup: ResumeExportObjectCleanup, *, include_identity: bool
) -> dict[str, object]:
    values: dict[str, object] = {
        "export_id": cleanup.export_id,
        "attempt_fence": cleanup.attempt_fence,
        "object_key": cleanup.object_key,
        "trace_id": cleanup.trace_id,
        "not_before": cleanup.not_before,
        "attempts": cleanup.attempts,
        "max_attempts": cleanup.max_attempts,
        "last_error": cleanup.last_error,
        "completed_at": cleanup.completed_at,
        "cancelled_at": cleanup.cancelled_at,
        "dead_lettered_at": cleanup.dead_lettered_at,
        "created_at": cleanup.created_at,
    }
    if include_identity:
        values.update({"id": cleanup.id, "owner_user_id": cleanup.owner_user_id})
    return values


def _export_object_cleanup_model(
    cleanup: ResumeExportObjectCleanup,
) -> ResumeExportObjectCleanupModel:
    return ResumeExportObjectCleanupModel(
        **_export_object_cleanup_values(cleanup, include_identity=True)
    )


def _export_object_cleanup(
    model: ResumeExportObjectCleanupModel,
) -> ResumeExportObjectCleanup:
    return ResumeExportObjectCleanup(
        id=model.id,
        owner_user_id=model.owner_user_id,
        export_id=model.export_id,
        attempt_fence=model.attempt_fence,
        object_key=model.object_key,
        trace_id=model.trace_id,
        not_before=model.not_before,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        last_error=model.last_error,
        completed_at=model.completed_at,
        cancelled_at=model.cancelled_at,
        dead_lettered_at=model.dead_lettered_at,
        created_at=model.created_at,
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
        "occurrence_mismatches": list(verification.occurrence_mismatches),
        "reading_order_failures": list(verification.reading_order_failures),
        "manifest_sha256": verification.manifest_sha256,
        "version_content_sha256": verification.version_content_sha256,
        "page_count": verification.page_count,
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
        occurrence_mismatches=tuple(model.occurrence_mismatches),
        reading_order_failures=tuple(model.reading_order_failures),
        manifest_sha256=model.manifest_sha256,
        version_content_sha256=model.version_content_sha256,
        page_count=model.page_count,
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
