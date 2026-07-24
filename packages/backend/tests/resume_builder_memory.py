"""In-memory resume builder ports for unit and API tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from careeros.modules.resume_builder.application import (
    ExtractedDocumentText,
    RenderedResume,
    ResumeRecord,
    ResumeSourceBullet,
    ResumeSourceSnapshot,
)
from careeros.modules.resume_builder.domain import (
    ResumeBuilderAuditEvent,
    ResumeBuilderIdempotencyRecord,
    ResumeDocument,
    ResumeDownloadIntent,
    ResumeEvidenceLinkBasis,
    ResumeEvidenceReference,
    ResumeExport,
    ResumeFormat,
    ResumeVerificationReport,
    ResumeVersion,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000701")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000702")
EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000703")
SKILL_EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000704")
CHANGE_SET_ID = UUID("00000000-0000-4000-8000-000000000705")
CHANGE_SET_VERSION_ID = UUID("00000000-0000-4000-8000-000000000706")
EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-000000000707")
SKILL_EVIDENCE_REVISION_ID = UUID("00000000-0000-4000-8000-000000000708")


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


class UuidFactory:
    def __init__(self) -> None:
        self._values = _uuids()

    def new(self) -> UUID:
        return next(self._values)


class StaticResumeSourceProvider:
    def __init__(self, *, with_evidence: bool = True) -> None:
        self.with_evidence = with_evidence

    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        change_set_id: UUID | None = None,
        change_set_version_id: UUID | None = None,
    ) -> ResumeSourceSnapshot:
        _ = owner_user_id
        evidence_ids = (EVIDENCE_ID, SKILL_EVIDENCE_ID) if self.with_evidence else ()
        career_text = "Confirmed product discovery work across customer interviews."
        skill_text = "Product discovery"
        change_text = "Tailored launch story approved in Change Studio."
        change_bullets = (
            (
                ResumeSourceBullet(
                    text=change_text,
                    evidence_ids=(EVIDENCE_ID,),
                    source="change_studio",
                    evidence_references=(
                        _reference(
                            EVIDENCE_ID,
                            EVIDENCE_REVISION_ID,
                            statement=career_text,
                            claim=change_text,
                            basis=ResumeEvidenceLinkBasis.CHANGE_STUDIO_CLAIM,
                        ),
                    ),
                ),
            )
            if change_set_id == CHANGE_SET_ID
            and change_set_version_id in {None, CHANGE_SET_VERSION_ID}
            else ()
        )
        return ResumeSourceSnapshot(
            headline="Product systems lead",
            summary="Led product discovery using confirmed Career Record evidence.",
            skills=("Product discovery",) if self.with_evidence else (),
            bullets=(
                (
                    ResumeSourceBullet(
                        text=career_text,
                        evidence_ids=(EVIDENCE_ID,),
                        source="career_record",
                        evidence_references=(
                            _reference(
                                EVIDENCE_ID,
                                EVIDENCE_REVISION_ID,
                                statement=career_text,
                                claim=career_text,
                                basis=ResumeEvidenceLinkBasis.EVIDENCE_STATEMENT,
                            ),
                        ),
                    ),
                    ResumeSourceBullet(
                        text=skill_text,
                        evidence_ids=(SKILL_EVIDENCE_ID,),
                        source="career_record",
                        evidence_references=(
                            _reference(
                                SKILL_EVIDENCE_ID,
                                SKILL_EVIDENCE_REVISION_ID,
                                statement="Applied product discovery methods.",
                                claim=skill_text,
                                basis=ResumeEvidenceLinkBasis.EVIDENCE_SKILL,
                                source_skill_id=UUID("00000000-0000-4000-8000-000000000709"),
                            ),
                        ),
                        section_kind="skills",
                    ),
                    *change_bullets,
                )
                if self.with_evidence
                else ()
            ),
            source_evidence_ids=evidence_ids,
        )


def _reference(
    evidence_id: UUID,
    evidence_revision_id: UUID,
    *,
    statement: str,
    claim: str,
    basis: ResumeEvidenceLinkBasis,
    source_skill_id: UUID | None = None,
) -> ResumeEvidenceReference:
    return ResumeEvidenceReference(
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        revision_number=1,
        statement_sha256=hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        claim_sha256=hashlib.sha256(" ".join(claim.strip().split()).encode("utf-8")).hexdigest(),
        link_basis=basis,
        source_skill_id=source_skill_id,
    )


class MemoryResumeBuilder:
    def __init__(self) -> None:
        self.resumes: dict[UUID, ResumeDocument] = {}
        self.versions: dict[UUID, ResumeVersion] = {}
        self.exports: dict[UUID, ResumeExport] = {}
        self.verifications: dict[UUID, ResumeVerificationReport] = {}
        self.downloads: dict[tuple[UUID, str], ResumeDownloadIntent] = {}
        self.idempotency: dict[tuple[UUID, str], ResumeBuilderIdempotencyRecord] = {}
        self.audits: list[ResumeBuilderAuditEvent] = []

    def __call__(self) -> MemoryResumeBuilder:
        return self

    async def __aenter__(self) -> MemoryResumeBuilder:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def list_resumes(self, owner_user_id: UUID) -> tuple[ResumeRecord, ...]:
        return tuple(
            deepcopy(record)
            for resume in self.resumes.values()
            if resume.owner_user_id == owner_user_id
            for record in (self._record(resume),)
            if record is not None
        )

    async def add_resume(self, record: ResumeRecord) -> None:
        self.resumes[record.resume.id] = deepcopy(record.resume)
        self.versions[record.current_version.id] = deepcopy(record.current_version)

    async def save_resume(self, record: ResumeRecord) -> None:
        self.resumes[record.resume.id] = deepcopy(record.resume)

    async def get_resume(
        self, owner_user_id: UUID, resume_id: UUID, *, for_update: bool = False
    ) -> ResumeRecord | None:
        _ = for_update
        resume = self.resumes.get(resume_id)
        if resume is None or resume.owner_user_id != owner_user_id:
            return None
        return deepcopy(self._record(resume))

    async def list_versions(
        self, owner_user_id: UUID, resume_id: UUID
    ) -> tuple[ResumeVersion, ...]:
        return tuple(
            deepcopy(version)
            for version in sorted(self.versions.values(), key=lambda item: item.version_number)
            if version.owner_user_id == owner_user_id and version.resume_id == resume_id
        )

    async def get_version(self, owner_user_id: UUID, version_id: UUID) -> ResumeVersion | None:
        version = self.versions.get(version_id)
        if version is None or version.owner_user_id != owner_user_id:
            return None
        return deepcopy(version)

    async def add_version(self, version: ResumeVersion) -> None:
        self.versions[version.id] = deepcopy(version)

    async def set_current_version(
        self, owner_user_id: UUID, resume_id: UUID, version_id: UUID, *, now: datetime
    ) -> ResumeRecord | None:
        resume = self.resumes.get(resume_id)
        version = self.versions.get(version_id)
        if (
            resume is None
            or version is None
            or resume.owner_user_id != owner_user_id
            or version.owner_user_id != owner_user_id
            or version.resume_id != resume_id
        ):
            return None
        updated = replace(
            resume,
            title=version.title,
            target_role=version.target_role,
            template=version.template,
            current_version_id=version.id,
            version=resume.version + 1,
            updated_at=now,
        )
        self.resumes[resume_id] = deepcopy(updated)
        return deepcopy(ResumeRecord(resume=updated, current_version=version))

    async def find_export_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeExport | None:
        for export in self.exports.values():
            if export.owner_user_id == owner_user_id and export.idempotency_key == idempotency_key:
                return deepcopy(export)
        return None

    async def add_export(
        self, export: ResumeExport, verification: ResumeVerificationReport | None = None
    ) -> None:
        self.exports[export.id] = deepcopy(export)
        if verification is not None:
            self.verifications[export.id] = deepcopy(verification)

    async def save_export(
        self, export: ResumeExport, verification: ResumeVerificationReport | None = None
    ) -> None:
        self.exports[export.id] = deepcopy(export)
        if verification is not None:
            self.verifications[export.id] = deepcopy(verification)

    async def get_export(self, owner_user_id: UUID, export_id: UUID) -> ResumeExport | None:
        export = self.exports.get(export_id)
        if export is None or export.owner_user_id != owner_user_id:
            return None
        return deepcopy(export)

    async def get_verification(
        self, owner_user_id: UUID, export_id: UUID
    ) -> ResumeVerificationReport | None:
        report = self.verifications.get(export_id)
        if report is None or report.owner_user_id != owner_user_id:
            return None
        return deepcopy(report)

    async def find_download_intent_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeDownloadIntent | None:
        intent = self.downloads.get((owner_user_id, idempotency_key))
        return deepcopy(intent) if intent is not None else None

    async def add_download_intent(self, intent: ResumeDownloadIntent) -> None:
        self.downloads[(intent.owner_user_id, intent.idempotency_key)] = deepcopy(intent)

    async def add_idempotency(self, record: ResumeBuilderIdempotencyRecord) -> None:
        self.idempotency[(record.owner_user_id, record.idempotency_key)] = deepcopy(record)

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ResumeBuilderIdempotencyRecord | None:
        record = self.idempotency.get((owner_user_id, idempotency_key))
        return deepcopy(record) if record is not None else None

    async def add_audit(self, event: ResumeBuilderAuditEvent) -> None:
        self.audits.append(deepcopy(event))

    async def commit(self) -> None:
        return None

    def _record(self, resume: ResumeDocument) -> ResumeRecord | None:
        if resume.current_version_id is None:
            return None
        version = self.versions.get(resume.current_version_id)
        if version is None:
            return None
        return ResumeRecord(resume=resume, current_version=version)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
        _ = media_type
        self.objects[object_key] = value

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes:
        value = self.objects[object_key]
        if len(value) > max_bytes:
            raise ValueError("object exceeds maximum read size")
        return value

    async def delete(self, object_key: str) -> None:
        self.objects.pop(object_key, None)
        self.deleted.append(object_key)

    async def presign_get(self, object_key: str, *, expires_in_seconds: int) -> str:
        _ = expires_in_seconds
        return f"https://downloads.invalid/{object_key}"

    async def dispose(self) -> None:
        return None


class PlainTextExtractor:
    async def extract(self, path: Path, media_type: str) -> ExtractedDocumentText:
        _ = media_type
        text = path.read_text(encoding="utf-8", errors="replace")
        return ExtractedDocumentText(
            plain_text=text,
            reading_order=tuple(line for line in text.splitlines() if line.strip()),
            parser_version="plain-test-parser",
        )


class TextOnlyRenderer:
    def __init__(self, *, omit_expected: bool = False) -> None:
        self.omit_expected = omit_expected

    def render(self, version: ResumeVersion, *, fmt: str) -> RenderedResume:
        requested = ResumeFormat(fmt)
        lines = [version.title]
        if version.target_role:
            lines.append(version.target_role)
        for section in version.sections:
            lines.append(section.title)
            lines.extend(item.text for item in section.items)
        content_lines = lines[:1] if self.omit_expected else lines
        media_type = "text/plain; charset=utf-8"
        if requested == ResumeFormat.JSON:
            media_type = "application/json"
        return RenderedResume(
            media_type=media_type,
            filename=f"resume.{requested.value}",
            content=("\n".join(content_lines) + "\n").encode("utf-8"),
            expected_lines=tuple(lines),
            renderer_version="test-renderer",
        )


def _uuids() -> Iterator[UUID]:
    counter = 0x800
    while True:
        counter += 1
        yield UUID(f"00000000-0000-4000-8000-{counter:012x}")


def future(seconds: int) -> datetime:
    return FixedClock().now() + timedelta(seconds=seconds)
