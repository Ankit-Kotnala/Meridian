"""Validation helpers for structured resume content."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from uuid import UUID

from .entities import ResumeBullet, ResumeSection
from .errors import ResumeBuilderValidationError

MAX_TITLE_LENGTH = 120
MAX_TARGET_ROLE_LENGTH = 120
MAX_SECTION_TITLE_LENGTH = 80
MAX_SECTION_KIND_LENGTH = 40
MAX_BULLET_LENGTH = 450
MAX_SECTIONS = 12
MAX_ITEMS_PER_SECTION = 24


_SMART_APOSTROPHES = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "`": "'",
    }
)
_DASH_CHARS = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)
_FIDELITY_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_FIDELITY_SENTENCE_PUNCTUATION_SPACING = re.compile(r"([.!?])([A-Z])")
_FIDELITY_HYPHENATION_BREAKS = re.compile(r"-\s+")
_FIDELITY_SECTION_HEADING_BOUNDARY = re.compile(
    r"(?<=[A-Za-z])"
    r"(?=(EXPERIENCE|EDUCATION|SKILLS|PROJECTS|SUMMARY|AWARDS|CREDENTIALS)\b)",
    re.IGNORECASE,
)
_FIDELITY_TITLE_CASE_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])")


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_fidelity_match_text(value: str) -> str:
    """Normalize resume text for export round-trip verification.

    PDF/DOCX re-extraction can rewrite smart quotes, drop control characters, and
    split words across lines. Collapse those artifacts before comparing manifest
    entries to extracted bytes.
    """

    normalized = normalize_text(value)
    normalized = unicodedata.normalize(
        "NFKC",
        normalized.translate(_SMART_APOSTROPHES).translate(_DASH_CHARS),
    )
    normalized = normalized.replace("\u00ad", "")
    normalized = _FIDELITY_CONTROL_CHARS.sub(" ", normalized)
    normalized = _FIDELITY_SECTION_HEADING_BOUNDARY.sub(" ", normalized)
    normalized = _FIDELITY_TITLE_CASE_BOUNDARY.sub(" ", normalized)
    normalized = _FIDELITY_SENTENCE_PUNCTUATION_SPACING.sub(r"\1 \2", normalized)
    normalized = _FIDELITY_HYPHENATION_BREAKS.sub("-", normalized)
    return " ".join(normalized.split()).casefold()


def fidelity_match_tokens(value: str) -> tuple[str, ...]:
    """Tokenize normalized resume text for order/occurrence verification."""

    normalized = normalize_fidelity_match_text(value).replace("'", "")
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return tuple(re.findall(r"\w+", normalized, flags=re.UNICODE))


def validate_title(value: str) -> str:
    normalized = normalize_text(value)
    if not 1 <= len(normalized) <= MAX_TITLE_LENGTH:
        raise ResumeBuilderValidationError("resume title must be 1-120 characters")
    return normalized


def validate_optional_target_role(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_text(value)
    if normalized == "":
        return None
    if len(normalized) > MAX_TARGET_ROLE_LENGTH:
        raise ResumeBuilderValidationError("target role must be 120 characters or fewer")
    return normalized


def validate_sections(
    sections: Iterable[ResumeSection],
    *,
    eligible_evidence_ids: set[UUID],
    eligible_entity_ids: set[UUID] | None = None,
) -> tuple[ResumeSection, ...]:
    normalized_sections: list[ResumeSection] = []
    seen_section_ids: set[UUID] = set()
    seen_item_ids: set[UUID] = set()
    evidence_revisions: dict[UUID, tuple[UUID, int, str]] = {}
    for section in sections:
        if section.id in seen_section_ids:
            raise ResumeBuilderValidationError("section ids must be unique")
        seen_section_ids.add(section.id)
        title = normalize_text(section.title)
        kind = normalize_text(section.kind)
        if not 1 <= len(title) <= MAX_SECTION_TITLE_LENGTH:
            raise ResumeBuilderValidationError("section titles must be 1-80 characters")
        if not 1 <= len(kind) <= MAX_SECTION_KIND_LENGTH:
            raise ResumeBuilderValidationError("section kinds must be 1-40 characters")
        if len(section.items) > MAX_ITEMS_PER_SECTION:
            raise ResumeBuilderValidationError("sections may contain at most 24 items")
        normalized_items = _validate_items(
            section.items,
            eligible_evidence_ids=eligible_evidence_ids,
            seen_item_ids=seen_item_ids,
            evidence_revisions=evidence_revisions,
            eligible_entity_ids=eligible_entity_ids,
        )
        normalized_sections.append(
            ResumeSection(id=section.id, title=title, kind=kind, items=normalized_items)
        )
    if not 1 <= len(normalized_sections) <= MAX_SECTIONS:
        raise ResumeBuilderValidationError("resumes must contain 1-12 sections")
    return tuple(normalized_sections)


def _validate_items(
    items: Iterable[ResumeBullet],
    *,
    eligible_evidence_ids: set[UUID],
    seen_item_ids: set[UUID],
    evidence_revisions: dict[UUID, tuple[UUID, int, str]],
    eligible_entity_ids: set[UUID] | None,
) -> tuple[ResumeBullet, ...]:
    normalized_items: list[ResumeBullet] = []
    for item in items:
        if item.id in seen_item_ids:
            raise ResumeBuilderValidationError("item ids must be globally unique")
        seen_item_ids.add(item.id)
        text = normalize_text(item.text)
        if not 1 <= len(text) <= MAX_BULLET_LENGTH:
            raise ResumeBuilderValidationError("resume bullets must be 1-450 characters")
        if not item.evidence_ids:
            raise ResumeBuilderValidationError("resume bullets must cite eligible evidence")
        evidence_ids = tuple(dict.fromkeys(item.evidence_ids))
        if len(evidence_ids) > 20:
            raise ResumeBuilderValidationError(
                "resume bullets may cite at most 20 evidence revisions"
            )
        unknown = [
            evidence_id
            for evidence_id in item.evidence_ids
            if evidence_id not in eligible_evidence_ids
        ]
        if unknown:
            raise ResumeBuilderValidationError("resume bullets must cite eligible evidence")
        if (
            item.entity_id is not None
            and eligible_entity_ids is not None
            and item.entity_id not in eligible_entity_ids
        ):
            raise ResumeBuilderValidationError("resume bullets must cite an eligible entity")
        references_by_id = {
            reference.evidence_id: reference for reference in item.evidence_references
        }
        if (
            len(references_by_id) != len(item.evidence_references)
            or set(references_by_id) != set(evidence_ids)
            or any(
                reference.claim_sha256 != hashlib.sha256(text.encode("utf-8")).hexdigest()
                for reference in item.evidence_references
            )
        ):
            raise ResumeBuilderValidationError(
                "resume bullets require one exact revision reference per evidence item"
            )
        for reference in item.evidence_references:
            revision_key = (
                reference.evidence_revision_id,
                reference.revision_number,
                reference.statement_sha256,
            )
            existing_revision = evidence_revisions.setdefault(
                reference.evidence_id,
                revision_key,
            )
            if existing_revision != revision_key:
                raise ResumeBuilderValidationError(
                    "a resume version cannot cite multiple revisions of one evidence item"
                )
        normalized_items.append(
            ResumeBullet(
                id=item.id,
                text=text,
                evidence_ids=evidence_ids,
                source=normalize_text(item.source) or "career_record",
                evidence_references=tuple(
                    references_by_id[evidence_id] for evidence_id in evidence_ids
                ),
                entity_id=item.entity_id,
            )
        )
    return tuple(normalized_items)
