"""Presentation mapping for Phase 7 resume builder responses."""

from __future__ import annotations

from careeros.modules.resume_builder.application import (
    DownloadIntentView,
    ResumeExportRecord,
    ResumeList,
    ResumeRecord,
    ResumeVersionList,
)
from careeros.modules.resume_builder.domain import (
    ResumeBullet,
    ResumeExport,
    ResumeSection,
    ResumeVerificationReport,
    ResumeVersion,
)

from careeros_api.resume_builder_schemas import (
    ResumeBulletResponse,
    ResumeDownloadIntentResponse,
    ResumeEvidenceReferenceResponse,
    ResumeExportRecordResponse,
    ResumeExportResponse,
    ResumeListResponse,
    ResumeResponse,
    ResumeSectionResponse,
    ResumeVerificationResponse,
    ResumeVersionListResponse,
    ResumeVersionResponse,
)


def resume_list_response(value: ResumeList) -> ResumeListResponse:
    return ResumeListResponse(items=[resume_response(item) for item in value.items])


def resume_response(record: ResumeRecord) -> ResumeResponse:
    return ResumeResponse(
        id=record.resume.id,
        title=record.resume.title,
        target_role=record.resume.target_role,
        template=record.resume.template.value,
        current_version_id=record.current_version.id,
        current_version=resume_version_response(record.current_version),
        version=record.resume.version,
        created_at=record.resume.created_at,
        updated_at=record.resume.updated_at,
    )


def resume_version_list_response(value: ResumeVersionList) -> ResumeVersionListResponse:
    return ResumeVersionListResponse(items=[resume_version_response(item) for item in value.items])


def resume_version_response(version: ResumeVersion) -> ResumeVersionResponse:
    return ResumeVersionResponse(
        id=version.id,
        resume_id=version.resume_id,
        version_number=version.version_number,
        parent_version_id=version.parent_version_id,
        title=version.title,
        target_role=version.target_role,
        template=version.template.value,
        sections=[_section_response(section) for section in version.sections],
        plain_text=version.plain_text,
        source_evidence_ids=list(version.source_evidence_ids),
        source_change_set_id=version.source_change_set_id,
        source_change_set_version_id=version.source_change_set_version_id,
        created_at=version.created_at,
    )


def export_record_response(value: ResumeExportRecord) -> ResumeExportRecordResponse:
    return ResumeExportRecordResponse(
        export=export_response(value.export),
        verification=(
            verification_response(value.verification) if value.verification is not None else None
        ),
    )


def export_response(export: ResumeExport) -> ResumeExportResponse:
    return ResumeExportResponse(
        id=export.id,
        resume_id=export.resume_id,
        version_id=export.version_id,
        format=export.format.value,
        status=export.status.value,
        media_type=export.media_type,
        size_bytes=export.size_bytes,
        sha256_digest=export.sha256_digest,
        verification_status=(
            export.verification_status.value if export.verification_status is not None else None
        ),
        verification_codes=list(export.verification_codes),
        critical_failures=list(export.critical_failures),
        warnings=list(export.warnings),
        renderer_version=export.renderer_version,
        parser_version=export.parser_version,
        requested_at=export.requested_at,
        completed_at=export.completed_at,
        deleted_at=export.deleted_at,
    )


def verification_response(report: ResumeVerificationReport) -> ResumeVerificationResponse:
    return ResumeVerificationResponse(
        id=report.id,
        export_id=report.export_id,
        version_id=report.version_id,
        status=report.status.value,
        critical_failures=list(report.critical_failures),
        warnings=list(report.warnings),
        detected_lines=list(report.detected_lines),
        missing_lines=list(report.missing_lines),
        duplicate_lines=list(report.duplicate_lines),
        reading_order=list(report.reading_order),
        grounding_codes=list(report.grounding_codes),
        file_sha256=report.file_sha256,
        parser_version=report.parser_version,
        created_at=report.created_at,
    )


def download_intent_response(value: DownloadIntentView) -> ResumeDownloadIntentResponse:
    return ResumeDownloadIntentResponse(
        export_id=value.export_id,
        method=value.method,
        url=value.url,
        expires_at=value.expires_at,
    )


def _section_response(section: ResumeSection) -> ResumeSectionResponse:
    return ResumeSectionResponse(
        id=section.id,
        title=section.title,
        kind=section.kind,
        items=[_bullet_response(item) for item in section.items],
    )


def _bullet_response(item: ResumeBullet) -> ResumeBulletResponse:
    return ResumeBulletResponse(
        id=item.id,
        text=item.text,
        evidence_ids=list(item.evidence_ids),
        source=item.source,
        evidence_references=[
            ResumeEvidenceReferenceResponse(
                evidence_id=reference.evidence_id,
                evidence_revision_id=reference.evidence_revision_id,
                revision_number=reference.revision_number,
                statement_sha256=reference.statement_sha256,
                claim_sha256=reference.claim_sha256,
                link_basis=reference.link_basis.value,
                source_skill_id=reference.source_skill_id,
            )
            for reference in item.evidence_references
        ],
    )
