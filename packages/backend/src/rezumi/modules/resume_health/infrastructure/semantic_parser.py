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
_SPLIT = re.compile(r"\s*(?:\||•|·|\t)\s*")
# Weak separators are only applied when a record still has unfilled names, so a
# header line is cut exactly as far as the record requires and no further. The
# first cut may use "at" ("Senior Engineer at Acme"); later cuts may not, so an
# institution such as "University of Texas at Austin" survives intact.
_WEAK_SPLIT_FIRST = re.compile(r"\s*,\s*|\s+[\u2013\u2014-]\s+|\s+at\s+", re.IGNORECASE)
_WEAK_SPLIT_REST = re.compile(r"\s*,\s*|\s+[\u2013\u2014-]\s+")
# Skills lists commonly separate individual skills with commas or semicolons in
# addition to pipes/bullets. Slashes and hyphens are intentionally excluded so
# compound skills like "CI/CD", "TCP/IP", or "A/B testing" stay intact.
_SKILL_SPLIT = re.compile(r"\s*(?:,|;|\||•|·)\s*")


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
                candidates = _group_candidates(kind, blocks)
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


def _group_candidates(
    kind: SemanticEntityKind,
    blocks: tuple[CanonicalBlock, ...],
) -> tuple[_FieldCandidate, ...]:
    if kind is SemanticEntityKind.SKILL:
        candidates: list[_FieldCandidate] = []
        for block in blocks:
            text = block.text
            prefix_len = 0
            if ":" in text:
                prefix, _, text = text.partition(":")
                prefix_len = len(prefix) + 1
            candidates.extend(
                _FieldCandidate(
                    "name",
                    SemanticFieldType.TEXT,
                    value,
                    block,
                    start + prefix_len,
                    end + prefix_len,
                    8_000,
                )
                for value, start, end in _source_values(text, (), _SKILL_SPLIT)
            )
        return tuple(candidates)

    candidates: list[_FieldCandidate] = []
    pending_text: list[str] = []
    pending_dates = list(_date_names(kind))
    for index, block in enumerate(blocks):
        if not pending_text:
            pending_text = list(_text_names_for_block(kind, block))
        if block.kind is BlockKind.BULLET:
            name = "achievement" if kind is SemanticEntityKind.EXPERIENCE else "description"
            candidates.append(
                _FieldCandidate(
                    name,
                    SemanticFieldType.BULLET,
                    block.text,
                    block,
                    0,
                    len(block.text),
                    8_500,
                )
            )
            continue
        if _is_wrapped_bullet_continuation(block, blocks, index):
            if kind is SemanticEntityKind.EXPERIENCE:
                candidates.append(
                    _FieldCandidate(
                        "achievement",
                        SemanticFieldType.BULLET,
                        block.text,
                        block,
                        0,
                        len(block.text),
                        8_000,
                    )
                )
            continue
        candidates.extend(_header_candidates(block, pending_text, pending_dates))

    if candidates:
        return tuple(candidates)
    header = next(
        (block for block in blocks if block.kind is not BlockKind.BULLET and block.text),
        None,
    )
    if header is None:
        return ()
    # A header whose only content is separator punctuation yields no exact
    # source value. Name the whole line rather than dropping the record.
    return (
        _FieldCandidate(
            _text_names_for_block(kind, header)[0],
            SemanticFieldType.TEXT,
            header.text,
            header,
            0,
            len(header.text),
            5_500,
        ),
    )


def _header_candidates(
    block: CanonicalBlock,
    pending_text: list[str],
    pending_dates: list[str],
) -> list[_FieldCandidate]:
    """Consume the record's still-unfilled names from one header line."""
    text = block.text
    candidates: list[_FieldCandidate] = []
    date_matches = list(_DATE.finditer(text))
    for match in date_matches:
        if not pending_dates:
            break
        candidates.append(
            _FieldCandidate(
                pending_dates.pop(0),
                SemanticFieldType.DATE,
                match.group(),
                block,
                match.start(),
                match.end(),
                8_500,
                _date_precision(match.group()),
            )
        )
    segments = _source_values(
        text,
        tuple((match.start(), match.end()) for match in date_matches),
    )
    for value, start, end in _split_for_names(text, segments, len(pending_text)):
        if not pending_text:
            break
        candidates.append(
            _FieldCandidate(
                pending_text.pop(0),
                SemanticFieldType.TEXT,
                value,
                block,
                start,
                end,
                7_000,
            )
        )
    return candidates


def _split_for_names(
    text: str,
    segments: tuple[tuple[str, int, int], ...],
    needed: int,
) -> tuple[tuple[str, int, int], ...]:
    """Sub-split header segments only while the record still needs more names.

    "Senior Engineer, Acme Corp" has to become a title and an employer, but
    "San Francisco, CA" has to stay a single location once title and employer
    are already filled. Splitting strictly on demand keeps both readings exact.
    """
    if len(segments) >= needed:
        return segments
    expanded: list[tuple[str, int, int]] = []
    for index, (_, start, end) in enumerate(segments):
        room = needed - len(expanded) - (len(segments) - index - 1)
        expanded.extend(_split_segment(text, start, end, room))
    return tuple(expanded)


def _split_segment(
    text: str,
    start: int,
    end: int,
    limit: int,
) -> tuple[tuple[str, int, int], ...]:
    """Cut one header segment into at most ``limit`` exact source values."""
    parts: list[tuple[str, int, int]] = [(text[start:end], start, end)]
    pattern = _WEAK_SPLIT_FIRST
    while len(parts) < limit:
        value, value_start, value_end = parts[-1]
        cut = _source_values(value, (), pattern)
        if len(cut) < 2:
            break
        head, head_start, head_end = cut[0]
        rest_start = value_start + cut[1][1]
        parts[-1] = (head, value_start + head_start, value_start + head_end)
        parts.append((text[rest_start:value_end], rest_start, value_end))
        pattern = _WEAK_SPLIT_REST
    return tuple(parts)


def _entity_block_groups(
    kind: SemanticEntityKind,
    blocks: tuple[CanonicalBlock, ...],
) -> tuple[tuple[CanonicalBlock, ...], ...]:
    if kind is SemanticEntityKind.EDUCATION:
        blocks = _education_blocks(blocks)
    if kind is SemanticEntityKind.SKILL:
        # Every skill line belongs to one structured Skills entity, so the review
        # UI shows a single section listing each skill instead of one card per
        # line. An empty section yields no group and is skipped by the caller.
        return (blocks,) if blocks else ()
    groups: list[list[CanonicalBlock]] = []
    for block in blocks:
        if block.kind is BlockKind.BULLET:
            if groups:
                groups[-1].append(block)
            else:
                groups.append([block])
            continue
        starts_record = not groups or _starts_new_record(kind, block, groups[-1])
        if starts_record:
            groups.append([block])
        else:
            groups[-1].append(block)
    return tuple(tuple(group) for group in groups)


def _starts_new_record(
    kind: SemanticEntityKind,
    block: CanonicalBlock,
    current_group: list[CanonicalBlock],
) -> bool:
    if _carries_date(current_group) and _DATE.search(block.text) is not None:
        return True
    if not any(item.kind is BlockKind.BULLET for item in current_group):
        return False
    text = block.text.lstrip()
    if text and text[0].islower():
        return False
    if "|" in block.text:
        return True
    return "," in block.text and _DATE.search(block.text) is None


def _is_wrapped_bullet_continuation(
    block: CanonicalBlock,
    blocks: tuple[CanonicalBlock, ...],
    index: int,
) -> bool:
    if block.kind is BlockKind.BULLET or index == 0:
        return False
    if blocks[index - 1].kind is BlockKind.BULLET:
        return True
    text = block.text.lstrip()
    return bool(text) and text[0].islower()


def _education_blocks(blocks: tuple[CanonicalBlock, ...]) -> tuple[CanonicalBlock, ...]:
    cutoff = len(blocks)
    for index, block in enumerate(blocks):
        if block.kind is not BlockKind.HEADING:
            continue
        normalized = block.text.casefold()
        if "certification" in normalized or "achievement" in normalized:
            cutoff = index
            break
    return blocks[:cutoff]


def _text_names_for_block(kind: SemanticEntityKind, block: CanonicalBlock) -> tuple[str, ...]:
    if kind is SemanticEntityKind.EXPERIENCE:
        if "|" in block.text:
            return ("employer", "title", "location")
        return ("title", "employer", "location")
    if kind is SemanticEntityKind.EDUCATION:
        if "|" in block.text:
            return ("institution", "degree", "field", "location")
        return ("degree", "institution", "field", "location")
    return _text_names(kind)


def _carries_date(group: list[CanonicalBlock]) -> bool:
    """Whether a record's header lines already supplied a date range."""
    return any(
        block.kind is not BlockKind.BULLET and _DATE.search(block.text) is not None
        for block in group
    )


def _text_names(kind: SemanticEntityKind) -> tuple[str, ...]:
    return {
        SemanticEntityKind.EXPERIENCE: ("title", "employer", "location"),
        SemanticEntityKind.EDUCATION: ("degree", "institution", "field", "location"),
        SemanticEntityKind.PROJECT: ("name", "description"),
        SemanticEntityKind.CERTIFICATION: ("name", "issuer", "credential_id"),
        SemanticEntityKind.CONTACT: ("name",),
        SemanticEntityKind.SKILL: ("name",),
    }[kind]


def _date_names(kind: SemanticEntityKind) -> tuple[str, ...]:
    if kind is SemanticEntityKind.CERTIFICATION:
        return ("issued_date", "expires_date")
    if kind in {
        SemanticEntityKind.EXPERIENCE,
        SemanticEntityKind.EDUCATION,
        SemanticEntityKind.PROJECT,
    }:
        return ("start_date", "end_date")
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
    splitter: re.Pattern[str] = _SPLIT,
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
        for separator in splitter.finditer(text, source_start, source_end):
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
