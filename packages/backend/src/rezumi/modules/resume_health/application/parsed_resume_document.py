"""Organize parsed resume semantics into a MongoDB-friendly document shape."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from rezumi.modules.resume_health.domain import (
    CanonicalResume,
    OwnerScope,
    SemanticEntity,
    SemanticEntityKind,
    SemanticFieldType,
    SemanticReviewState,
)


def build_user_data_document(
    *,
    resume_id: UUID,
    owner: OwnerScope,
    snapshot_id: UUID,
    display_filename: str,
    canonical: CanonicalResume,
    parsed_at: datetime,
) -> dict[str, Any]:
    """Return an upsert payload keyed by ``resumeId`` for the user-data collection."""
    semantics = canonical.semantics
    organized = _empty_organized_sections()
    if semantics is not None:
        organized = _organize_semantics(semantics.entities)

    return {
        "resumeId": str(resume_id),
        "userId": str(owner.user_id) if owner.user_id is not None else None,
        "guestSessionId": (
            str(owner.guest_session_id) if owner.guest_session_id is not None else None
        ),
        "snapshotId": str(snapshot_id),
        "displayFilename": display_filename,
        "schemaVersion": canonical.schema_version,
        "parserVersion": semantics.parser_version if semantics is not None else None,
        "parsedAt": parsed_at.isoformat(),
        "updatedAt": parsed_at.isoformat(),
        **organized,
    }


def _empty_organized_sections() -> dict[str, Any]:
    return {
        "contact": {},
        "experience": [],
        "education": [],
        "projects": [],
        "skills": [],
        "certifications": [],
    }


def _organize_semantics(entities: tuple[SemanticEntity, ...]) -> dict[str, Any]:
    organized = _empty_organized_sections()
    for entity in entities:
        if entity.review_state is SemanticReviewState.REMOVED:
            continue
        record = _entity_to_record(entity)
        if record is None:
            continue
        match entity.kind:
            case SemanticEntityKind.CONTACT:
                organized["contact"] = record
            case SemanticEntityKind.EXPERIENCE:
                organized["experience"].append(record)
            case SemanticEntityKind.EDUCATION:
                organized["education"].append(record)
            case SemanticEntityKind.PROJECT:
                organized["projects"].append(record)
            case SemanticEntityKind.SKILL:
                organized["skills"].append(record)
            case SemanticEntityKind.CERTIFICATION:
                organized["certifications"].append(record)
    return organized


def _entity_to_record(entity: SemanticEntity) -> dict[str, Any] | None:
    record: dict[str, Any] = {"id": str(entity.id)}
    list_fields: dict[str, list[str]] = {}
    has_values = False

    for field in entity.fields:
        if field.review_state is SemanticReviewState.REMOVED:
            continue
        has_values = True
        if field.field_type is SemanticFieldType.BULLET or field.name in {"achievement", "skill"}:
            list_fields.setdefault(field.name, []).append(field.value)
            continue
        record[field.name] = field.value

    for name, values in list_fields.items():
        record[name] = values

    if not has_values:
        return None
    return record
