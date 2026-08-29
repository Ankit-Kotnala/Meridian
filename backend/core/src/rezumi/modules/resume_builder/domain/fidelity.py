"""Canonical cross-format resume fidelity manifest."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from .entities import (
    ResumeEntityFact,
    ResumePersonalFact,
    ResumeSection,
    ResumeTemplate,
    ResumeVersion,
)
from .validation import normalize_text

FIDELITY_MANIFEST_VERSION = "career-resume-fidelity-v1"
_NUMERIC_TOKEN = re.compile(r"(?<!\w)[+-]?(?:\d[\d,.]*)(?:%|[kKmMbB])?(?!\w)")
_PERSONAL_FACT_ORDER = {
    "name": 0,
    "email": 1,
    "phone": 2,
    "location": 3,
    "link": 4,
}
_SECTION_PRIORITIES: dict[ResumeTemplate, dict[str, int]] = {
    ResumeTemplate.STANDARD_PROFESSIONAL: {
        "summary": 0,
        "experience": 1,
        "projects": 2,
        "education": 3,
        "skills": 4,
        "credentials": 5,
        "awards": 6,
    },
    ResumeTemplate.COMPACT_TECHNICAL: {
        "skills": 0,
        "experience": 1,
        "projects": 2,
        "education": 3,
        "credentials": 4,
        "summary": 5,
        "awards": 6,
    },
    ResumeTemplate.EXECUTIVE: {
        "summary": 0,
        "experience": 1,
        "awards": 2,
        "skills": 3,
        "education": 4,
        "projects": 5,
        "credentials": 6,
    },
    ResumeTemplate.GRADUATE: {
        "summary": 0,
        "education": 1,
        "projects": 2,
        "experience": 3,
        "skills": 4,
        "credentials": 5,
        "awards": 6,
    },
    ResumeTemplate.CONSULTING_FINANCE: {
        "summary": 0,
        "experience": 1,
        "education": 2,
        "skills": 3,
        "projects": 4,
        "credentials": 5,
        "awards": 6,
    },
}


@dataclass(frozen=True, slots=True)
class ResumeFidelityEntry:
    key: str
    kind: str
    text: str
    normalized_text: str
    source_ids: tuple[UUID, ...]
    factual: bool
    numeric: bool
    order: int


@dataclass(frozen=True, slots=True)
class ResumeFidelityManifest:
    schema_version: str
    version_id: UUID
    version_content_sha256: str
    template: str
    page_limit: int
    entries: tuple[ResumeFidelityEntry, ...]


def ordered_sections(version: ResumeVersion) -> tuple[ResumeSection, ...]:
    priorities = _SECTION_PRIORITIES[version.template]
    indexed = tuple(enumerate(version.sections))
    return tuple(
        item
        for _, item in sorted(
            indexed,
            key=lambda pair: (
                priorities.get(pair[1].kind.casefold(), 100),
                pair[0],
            ),
        )
    )


def ordered_personal_facts(version: ResumeVersion) -> tuple[ResumePersonalFact, ...]:
    indexed = tuple(enumerate(version.personal_facts))
    return tuple(
        item
        for _, item in sorted(
            indexed,
            key=lambda pair: (
                _PERSONAL_FACT_ORDER.get(pair[1].kind.casefold(), 100),
                0 if pair[1].is_primary else 1,
                pair[0],
            ),
        )
    )


def build_fidelity_manifest(version: ResumeVersion) -> ResumeFidelityManifest:
    entries: list[ResumeFidelityEntry] = []

    def add(
        key: str,
        kind: str,
        text: str,
        *,
        source_ids: tuple[UUID, ...] = (),
        factual: bool,
    ) -> None:
        normalized = normalize_text(text)
        if not normalized:
            return
        entries.append(
            ResumeFidelityEntry(
                key=key,
                kind=kind,
                text=normalized,
                normalized_text=normalized.casefold(),
                source_ids=source_ids,
                factual=factual,
                numeric=bool(_NUMERIC_TOKEN.search(normalized)),
                order=len(entries),
            )
        )

    for fact in ordered_personal_facts(version):
        add(
            f"personal:{fact.id}",
            f"personal_{fact.kind.casefold()}",
            fact.value,
            source_ids=(fact.id,),
            factual=True,
        )
    if version.target_role:
        add("target-role", "target_role", version.target_role, factual=False)

    entities = {entity.id: entity for entity in version.entities}
    emitted_entities: set[UUID] = set()
    for section in ordered_sections(version):
        add(f"section:{section.id}", "section_heading", section.title, factual=False)
        for item in section.items:
            entity = entities.get(item.entity_id) if item.entity_id is not None else None
            if entity is not None and entity.id not in emitted_entities:
                _add_entity_entries(add, entity)
                emitted_entities.add(entity.id)
            add(
                f"bullet:{item.id}",
                "bullet",
                item.text,
                source_ids=item.evidence_ids,
                factual=True,
            )

    return ResumeFidelityManifest(
        schema_version=FIDELITY_MANIFEST_VERSION,
        version_id=version.id,
        version_content_sha256=version_content_sha256(version),
        template=version.template.value,
        page_limit=version.layout.page_limit,
        entries=tuple(entries),
    )


def version_content_sha256(version: ResumeVersion) -> str:
    payload = {
        "entities": [
            {
                "displayTitle": entity.display_title,
                "endDate": asdict(entity.end_date) if entity.end_date is not None else None,
                "evidenceIds": [str(value) for value in entity.evidence_ids],
                "id": str(entity.id),
                "isCurrent": entity.is_current,
                "kind": entity.kind,
                "location": entity.location,
                "officialTitle": entity.official_title,
                "organization": entity.organization,
                "startDate": asdict(entity.start_date) if entity.start_date is not None else None,
                "title": entity.title,
            }
            for entity in version.entities
        ],
        "layout": {
            "fontFamily": version.layout.font_family.value,
            "fontSizePt": version.layout.font_size_pt,
            "lineSpacing": version.layout.line_spacing.value,
            "margins": version.layout.margins.value,
            "pageLimit": version.layout.page_limit,
            "pageSize": version.layout.page_size.value,
        },
        "personalFacts": [
            {
                "id": str(fact.id),
                "isPrimary": fact.is_primary,
                "kind": fact.kind,
                "label": fact.label,
                "value": fact.value,
            }
            for fact in version.personal_facts
        ],
        "resumeId": str(version.resume_id),
        "sections": [
            {
                "id": str(section.id),
                "items": [
                    {
                        "entityId": str(item.entity_id) if item.entity_id is not None else None,
                        "evidenceIds": [str(value) for value in item.evidence_ids],
                        "evidenceReferences": [
                            {
                                "claimSha256": reference.claim_sha256,
                                "evidenceId": str(reference.evidence_id),
                                "evidenceRevisionId": str(reference.evidence_revision_id),
                                "linkBasis": reference.link_basis.value,
                                "revisionNumber": reference.revision_number,
                                "sourceSkillId": (
                                    str(reference.source_skill_id)
                                    if reference.source_skill_id is not None
                                    else None
                                ),
                                "statementSha256": reference.statement_sha256,
                            }
                            for reference in item.evidence_references
                        ],
                        "id": str(item.id),
                        "source": item.source,
                        "text": item.text,
                    }
                    for item in section.items
                ],
                "kind": section.kind,
                "title": section.title,
            }
            for section in version.sections
        ],
        "sourceChangeSetId": (
            str(version.source_change_set_id) if version.source_change_set_id is not None else None
        ),
        "sourceChangeSetVersionId": (
            str(version.source_change_set_version_id)
            if version.source_change_set_version_id is not None
            else None
        ),
        "sourceEvidenceIds": [str(value) for value in version.source_evidence_ids],
        "targetRole": version.target_role,
        "template": version.template.value,
        "title": version.title,
        "versionId": str(version.id),
        "versionNumber": version.version_number,
    }
    return _sha256(payload)


def fidelity_manifest_payload(manifest: ResumeFidelityManifest) -> dict[str, object]:
    return {
        "entries": [
            {
                "factual": entry.factual,
                "key": entry.key,
                "kind": entry.kind,
                "normalizedText": entry.normalized_text,
                "numeric": entry.numeric,
                "order": entry.order,
                "sourceIds": [str(value) for value in entry.source_ids],
                "text": entry.text,
            }
            for entry in manifest.entries
        ],
        "pageLimit": manifest.page_limit,
        "schemaVersion": manifest.schema_version,
        "template": manifest.template,
        "versionContentSha256": manifest.version_content_sha256,
        "versionId": str(manifest.version_id),
    }


def fidelity_manifest_sha256(manifest: ResumeFidelityManifest) -> str:
    return _sha256(fidelity_manifest_payload(manifest))


def manifest_grounding_failures(manifest: ResumeFidelityManifest) -> tuple[str, ...]:
    failures: list[str] = []
    names = [entry for entry in manifest.entries if entry.kind == "personal_name"]
    if len(names) != 1:
        failures.append("required_name_missing_or_ambiguous")
    for entry in manifest.entries:
        if entry.factual and not entry.source_ids:
            failures.append(f"unsupported_manifest_entry:{entry.key}")
        if entry.numeric and entry.factual and not entry.source_ids:
            failures.append(f"numeric_grounding_missing:{entry.key}")
    return tuple(failures)


def _add_entity_entries(
    add: Any,
    entity: ResumeEntityFact,
) -> None:
    title = entity.display_title or entity.official_title or entity.title
    add(
        f"entity:{entity.id}:title",
        f"{entity.kind}_title",
        title,
        source_ids=entity.evidence_ids,
        factual=True,
    )
    if entity.organization:
        add(
            f"entity:{entity.id}:organization",
            f"{entity.kind}_organization",
            entity.organization,
            source_ids=entity.evidence_ids,
            factual=True,
        )
    if entity.location:
        add(
            f"entity:{entity.id}:location",
            f"{entity.kind}_location",
            entity.location,
            source_ids=entity.evidence_ids,
            factual=True,
        )
    dates = _date_range(entity)
    if dates:
        add(
            f"entity:{entity.id}:dates",
            f"{entity.kind}_dates",
            dates,
            source_ids=entity.evidence_ids,
            factual=True,
        )


def entity_display_lines(entity: ResumeEntityFact) -> tuple[str, ...]:
    title = entity.display_title or entity.official_title or entity.title
    details = tuple(value for value in (entity.organization, entity.location) if value)
    dates = _date_range(entity)
    return (
        title,
        *details,
        *((dates,) if dates else ()),
    )


def _date_range(entity: ResumeEntityFact) -> str | None:
    start = _partial_date(entity.start_date)
    end = "Present" if entity.is_current else _partial_date(entity.end_date)
    if start and end:
        return f"{start} - {end}"
    return start or end


def _partial_date(value: Any) -> str | None:
    if value is None:
        return None
    return f"{value.month:02d}/{value.year}" if value.month is not None else str(value.year)


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()
