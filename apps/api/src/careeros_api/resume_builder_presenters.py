"""Presentation mapping for Phase 7 resume builder responses."""

from __future__ import annotations

from careeros.modules.resume_builder.application import (
    DownloadIntentView,
    ResumeExportRecord,
    ResumeList,
    ResumeRecord,
    ResumeSourceSnapshot,
    ResumeVersionList,
)
from careeros.modules.resume_builder.domain import (
    ResumeBullet,
    ResumeEntityFact,
    ResumeEvidenceReference,
    ResumeExport,
    ResumeLayout,
    ResumePersonalFact,
    ResumeSection,
    ResumeVerificationReport,
    ResumeVersion,
)

from careeros_api.resume_builder_schemas import (
    ResumeBulletResponse,
    ResumeDownloadIntentResponse,
    ResumeEntityResponse,
    ResumeEvidenceReferenceResponse,
    ResumeExportRecordResponse,
    ResumeExportResponse,
    ResumeLayoutSchema,
    ResumeListResponse,
    ResumePartialDateResponse,
    ResumePersonalFactResponse,
    ResumeResponse,
    ResumeSectionResponse,
    ResumeSourceBulletResponse,
    ResumeSourceOptionsResponse,
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
        layout=_layout_response(record.resume.layout),
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
        layout=_layout_response(version.layout),
        personal_facts=[_personal_fact_response(item) for item in version.personal_facts],
        entities=[_entity_response(item) for item in version.entities],
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
        attempts=export.attempts,
        max_attempts=export.max_attempts,
        cleanup_attempts=export.cleanup_attempts,
        cleanup_max_attempts=export.cleanup_max_attempts,
        last_error=export.last_error,
        retry_at=export.retry_at,
        dead_lettered_at=export.dead_lettered_at,
        version_content_sha256=export.version_content_sha256,
        fidelity_manifest_sha256=export.fidelity_manifest_sha256,
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
        occurrence_mismatches=list(report.occurrence_mismatches),
        reading_order_failures=list(report.reading_order_failures),
        file_sha256=report.file_sha256,
        manifest_sha256=report.manifest_sha256,
        version_content_sha256=report.version_content_sha256,
        page_count=report.page_count,
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


def source_options_response(value: ResumeSourceSnapshot) -> ResumeSourceOptionsResponse:
    return ResumeSourceOptionsResponse(
        headline=value.headline,
        summary=value.summary,
        skills=list(value.skills),
        bullets=[
            ResumeSourceBulletResponse(
                text=item.text,
                evidence_ids=list(item.evidence_ids),
                source=item.source,
                section_kind=item.section_kind,
                entity_id=item.entity_id,
                evidence_references=[
                    _evidence_reference_response(reference)
                    for reference in item.evidence_references
                ],
            )
            for item in value.bullets
        ],
        source_evidence_ids=list(value.source_evidence_ids),
        personal_facts=[_personal_fact_response(item) for item in value.personal_facts],
        entities=[_entity_response(item) for item in value.entities],
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
        entity_id=item.entity_id,
        evidence_references=[
            _evidence_reference_response(reference) for reference in item.evidence_references
        ],
    )


def _layout_response(value: ResumeLayout) -> ResumeLayoutSchema:
    return ResumeLayoutSchema(
        page_size=value.page_size.value,
        page_limit=value.page_limit,  # type: ignore[arg-type]
        font_family=value.font_family.value,
        font_size_pt=value.font_size_pt,
        line_spacing=value.line_spacing.value,
        margins=value.margins.value,
    )


def _personal_fact_response(value: ResumePersonalFact) -> ResumePersonalFactResponse:
    return ResumePersonalFactResponse(
        id=value.id,
        kind=value.kind,
        value=value.value,
        label=value.label,
        is_primary=value.is_primary,
    )


def _entity_response(value: ResumeEntityFact) -> ResumeEntityResponse:
    return ResumeEntityResponse(
        id=value.id,
        kind=value.kind,
        title=value.title,
        organization=value.organization,
        official_title=value.official_title,
        display_title=value.display_title,
        location=value.location,
        start_date=(
            ResumePartialDateResponse(year=value.start_date.year, month=value.start_date.month)
            if value.start_date is not None
            else None
        ),
        end_date=(
            ResumePartialDateResponse(year=value.end_date.year, month=value.end_date.month)
            if value.end_date is not None
            else None
        ),
        is_current=value.is_current,
        evidence_ids=list(value.evidence_ids),
    )


def _evidence_reference_response(
    value: ResumeEvidenceReference,
) -> ResumeEvidenceReferenceResponse:
    return ResumeEvidenceReferenceResponse(
        evidence_id=value.evidence_id,
        evidence_revision_id=value.evidence_revision_id,
        revision_number=value.revision_number,
        statement_sha256=value.statement_sha256,
        claim_sha256=value.claim_sha256,
        link_basis=value.link_basis.value,
        source_skill_id=value.source_skill_id,
    )
