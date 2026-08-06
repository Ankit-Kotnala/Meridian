"""Deterministic, source-anchored semantic resume parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid5

from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSemantics,
    DatePrecision,
    SectionKind,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SemanticSourceAnchor,
)

SEMANTIC_SCHEMA_VERSION = "canonical-semantics/1.0.0"
SEMANTIC_PARSER_VERSION = "rezumi-semantic-parser/1.0.0"
_SEMANTIC_NAMESPACE = UUID("d6f8269c-f55b-4717-bdc7-2b552f564820")
_SOURCE_VALUE_TRIM = frozenset(" \t\r\n|-,;\u2013\u2014")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{6,}\d)(?!\w)")
_URL = re.compile(
    r"(?:(?:https?://|www\.)[^\s|,;]+|(?:linkedin\.com|github\.com)/[^\s|,;]+)",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"\b(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4}"
    r"|\d{1,2}[/-]\d{4}"
    r"|\d{4}[/-]\d{1,2}"
    r"|\d{4}"
    r"|Present|Current"
    r")\b",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"\s*(?:\||•|·)\s*")


@dataclass(frozen=True, slots=True)
class _FieldCandidate:
    name: str
    field_type: SemanticFieldType
    value: str
    block: CanonicalBlock
    start: int
    end: int
    confidence_basis_points: int
    date_precision: DatePrecision | None = None


class LocalResumeParserProvider:
    """Local baseline parser with deterministic IDs and no provider credentials."""

    async def parse(
        self,
        document_id: UUID,
        resume: CanonicalResume,
        source_sha256: str,
    ) -> CanonicalSemantics:
        if len(source_sha256) != 64:
            raise ValueError("semantic parsing requires the source document SHA-256")
        entities: list[SemanticEntity] = []
        for section_index, section in enumerate(resume.sections):
            kind = _entity_kind(section.kind)
            if kind is None and section_index == 0 and section.kind is SectionKind.OTHER:
                kind = SemanticEntityKind.CONTACT
            if kind is None:
                continue
            if kind is SemanticEntityKind.CONTACT:
                candidates = _contact_candidates(section.blocks)
                if candidates:
                    entities.append(
                        _entity(document_id, kind, section.id, 0, candidates, source_sha256)
                    )
                continue
            groups = _entity_block_groups(kind, section.blocks)
            for index, blocks in enumerate(groups):
                candidates = tuple(
                    candidate for block in blocks for candidate in _section_candidates(kind, block)
                )
                if candidates:
                    entities.append(
                        _entity(
                            document_id,
                            kind,
                            section.id,
                            index,
                            candidates,
                            source_sha256,
                        )
                    )
        warnings: list[str] = []
        discovered = {entity.kind for entity in entities}
        if SemanticEntityKind.CONTACT not in discovered:
            warnings.append("semantic_contact_not_detected")
        if SemanticEntityKind.EXPERIENCE not in discovered:
            warnings.append("semantic_experience_not_detected")
        return CanonicalSemantics(
            schema_version=SEMANTIC_SCHEMA_VERSION,
            parser_version=SEMANTIC_PARSER_VERSION,
            entities=tuple(entities),
            warnings=tuple(warnings),
        )


def _entity_kind(section_kind: SectionKind) -> SemanticEntityKind | None:
    return {
        SectionKind.CONTACT: SemanticEntityKind.CONTACT,
        SectionKind.EXPERIENCE: SemanticEntityKind.EXPERIENCE,
        SectionKind.EDUCATION: SemanticEntityKind.EDUCATION,
        SectionKind.PROJECTS: SemanticEntityKind.PROJECT,
        SectionKind.SKILLS: SemanticEntityKind.SKILL,
        SectionKind.CERTIFICATIONS: SemanticEntityKind.CERTIFICATION,
    }.get(section_kind)


def _contact_candidates(blocks: tuple[CanonicalBlock, ...]) -> tuple[_FieldCandidate, ...]:
    candidates: list[_FieldCandidate] = []
    name_added = False
    for block in blocks:
        for pattern, name, field_type in (
            (_EMAIL, "email", SemanticFieldType.EMAIL),
            (_PHONE, "phone", SemanticFieldType.PHONE),
            (_URL, "link", SemanticFieldType.URL),
        ):
            for match in pattern.finditer(block.text):
                candidates.append(
                    _FieldCandidate(
                        name,
                        field_type,
                        match.group().strip(),
                        block,
                        match.start(),
                        match.end(),
                        9_500,
                    )
                )
        if (
            not name_added
            and block.kind is not BlockKind.BULLET
            and not any(pattern.search(block.text) for pattern in (_EMAIL, _PHONE, _URL))
            and 1 < len(block.text.split()) <= 6
        ):
            candidates.append(
                _FieldCandidate(
                    "name",
                    SemanticFieldType.TEXT,
                    block.text,
                    block,
                    0,
                    len(block.text),
                    7_500,
                )
            )
            name_added = True
    return tuple(candidates)


def _section_candidates(
    kind: SemanticEntityKind, block: CanonicalBlock
) -> tuple[_FieldCandidate, ...]:
    text = block.text
    if kind is SemanticEntityKind.SKILL:
        return tuple(
            _FieldCandidate(
                "name",
                SemanticFieldType.TEXT,
                value,
                block,
                start,
                end,
                8_000,
            )
            for value, start, end in _source_values(text, ())
        )
    if block.kind is BlockKind.BULLET:
        name = "achievement" if kind is SemanticEntityKind.EXPERIENCE else "description"
        return (
            _FieldCandidate(
                name,
                SemanticFieldType.BULLET,
                text,
                block,
                0,
                len(text),
                8_500,
            ),
        )

    candidates: list[_FieldCandidate] = []
    date_matches = list(_DATE.finditer(text))
    date_names = _date_names(kind, len(date_matches))
    for match, name in zip(date_matches, date_names, strict=False):
        candidates.append(
            _FieldCandidate(
                name,
                SemanticFieldType.DATE,
                match.group(),
                block,
                match.start(),
                match.end(),
                8_500,
                _date_precision(match.group()),
            )
        )
    values = _source_values(
        text,
        tuple((match.start(), match.end()) for match in date_matches),
    )
    names = _text_names(kind)
    for (value, start, end), name in zip(values, names, strict=False):
        candidates.append(
            _FieldCandidate(
                name,
                SemanticFieldType.TEXT,
                value,
                block,
                start,
                end,
                7_000,
            )
        )
    if not candidates:
        fallback_name = _text_names(kind)[0]
        candidates.append(
            _FieldCandidate(
                fallback_name,
                SemanticFieldType.TEXT,
                text,
                block,
                0,
                len(text),
                5_500,
            )
        )
    return tuple(candidates)


def _entity_block_groups(
    kind: SemanticEntityKind,
    blocks: tuple[CanonicalBlock, ...],
) -> tuple[tuple[CanonicalBlock, ...], ...]:
    if kind is not SemanticEntityKind.EXPERIENCE:
        return tuple((block,) for block in blocks)
    groups: list[list[CanonicalBlock]] = []
    for block in blocks:
        if block.kind is not BlockKind.BULLET or not groups:
            groups.append([block])
        else:
            groups[-1].append(block)
    return tuple(tuple(group) for group in groups)


def _text_names(kind: SemanticEntityKind) -> tuple[str, ...]:
    return {
        SemanticEntityKind.EXPERIENCE: ("title", "employer", "location"),
        SemanticEntityKind.EDUCATION: ("degree", "institution", "field", "location"),
        SemanticEntityKind.PROJECT: ("name", "description"),
        SemanticEntityKind.CERTIFICATION: ("name", "issuer", "credential_id"),
        SemanticEntityKind.CONTACT: ("name",),
        SemanticEntityKind.SKILL: ("name",),
    }[kind]


def _date_names(kind: SemanticEntityKind, count: int) -> tuple[str, ...]:
    if kind is SemanticEntityKind.CERTIFICATION:
        return ("issued_date", "expires_date")[:count]
    if kind in {
        SemanticEntityKind.EXPERIENCE,
        SemanticEntityKind.EDUCATION,
        SemanticEntityKind.PROJECT,
    }:
        return ("start_date", "end_date")[:count]
    return ()


def _date_precision(value: str) -> DatePrecision:
    if re.search(r"[A-Za-z]", value) and value.casefold() not in {"present", "current"}:
        return DatePrecision.MONTH
    if re.fullmatch(r"(?:\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2})", value):
        return DatePrecision.MONTH
    if re.fullmatch(r"\d{4}", value):
        return DatePrecision.YEAR
    return DatePrecision.UNKNOWN


def _source_values(
    text: str,
    excluded_ranges: tuple[tuple[int, int], ...],
) -> tuple[tuple[str, int, int], ...]:
    """Return only contiguous source substrings with their exact block offsets."""
    values: list[tuple[str, int, int]] = []
    source_ranges: list[tuple[int, int]] = []
    cursor = 0
    for start, end in excluded_ranges:
        if cursor < start:
            source_ranges.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < len(text):
        source_ranges.append((cursor, len(text)))

    for source_start, source_end in source_ranges:
        segment_start = source_start
        for separator in _SPLIT.finditer(text, source_start, source_end):
            _append_source_value(values, text, segment_start, separator.start())
            segment_start = separator.end()
        _append_source_value(values, text, segment_start, source_end)
    return tuple(values)


def _append_source_value(
    values: list[tuple[str, int, int]],
    text: str,
    start: int,
    end: int,
) -> None:
    while start < end and text[start] in _SOURCE_VALUE_TRIM:
        start += 1
    while end > start and text[end - 1] in _SOURCE_VALUE_TRIM:
        end -= 1
    if start == end or text[start:end].casefold() == "to":
        return
    values.append((text[start:end], start, end))


def _entity(
    document_id: UUID,
    kind: SemanticEntityKind,
    section_id: UUID,
    entity_index: int,
    candidates: tuple[_FieldCandidate, ...],
    source_sha256: str,
) -> SemanticEntity:
    entity_id = uuid5(
        _SEMANTIC_NAMESPACE,
        f"{document_id}:{section_id}:{kind.value}:{entity_index}",
    )
    fields = tuple(
        _field(entity_id, index, candidate, source_sha256)
        for index, candidate in enumerate(candidates)
    )
    return SemanticEntity(
        id=entity_id,
        kind=kind,
        review_state=SemanticReviewState.UNREVIEWED,
        fields=fields,
        source_section_id=section_id,
    )


def _field(
    entity_id: UUID,
    index: int,
    candidate: _FieldCandidate,
    source_sha256: str,
) -> SemanticField:
    span = candidate.block.spans[0] if candidate.block.spans else None
    if span is None:
        raise ValueError("semantic source fields require an extracted source span")
    field_id = uuid5(
        _SEMANTIC_NAMESPACE,
        f"{entity_id}:{candidate.name}:{index}:{sha256(candidate.value.encode()).hexdigest()}",
    )
    return SemanticField(
        id=field_id,
        name=candidate.name,
        field_type=candidate.field_type,
        value=candidate.value,
        confidence_basis_points=candidate.confidence_basis_points,
        review_state=SemanticReviewState.UNREVIEWED,
        anchors=(
            SemanticSourceAnchor(
                block_id=candidate.block.id,
                page=span.page,
                start=span.start + candidate.start,
                end=span.start + candidate.end,
                source_sha256=source_sha256,
            ),
        ),
        date_precision=candidate.date_precision,
    )
