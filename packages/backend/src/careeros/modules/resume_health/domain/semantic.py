"""Typed, source-anchored semantic resume values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class SemanticEntityKind(StrEnum):
    CONTACT = "contact"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECT = "project"
    SKILL = "skill"
    CERTIFICATION = "certification"


class SemanticFieldType(StrEnum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    DATE = "date"
    BULLET = "bullet"


class SemanticReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    USER_ADDED = "user_added"
    REMOVED = "removed"


class DatePrecision(StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"


_FIELD_NAMES: dict[SemanticEntityKind, frozenset[str]] = {
    SemanticEntityKind.CONTACT: frozenset({"name", "email", "phone", "location", "link"}),
    SemanticEntityKind.EXPERIENCE: frozenset(
        {
            "employer",
            "title",
            "start_date",
            "end_date",
            "location",
            "employment_type",
            "description",
            "achievement",
        }
    ),
    SemanticEntityKind.EDUCATION: frozenset(
        {"institution", "degree", "field", "start_date", "end_date", "location"}
    ),
    SemanticEntityKind.PROJECT: frozenset(
        {"name", "description", "start_date", "end_date", "skill", "link"}
    ),
    SemanticEntityKind.SKILL: frozenset({"name", "category"}),
    SemanticEntityKind.CERTIFICATION: frozenset(
        {
            "name",
            "issuer",
            "issued_date",
            "expires_date",
            "credential_id",
            "link",
        }
    ),
}

_FIELD_TYPES: dict[str, frozenset[SemanticFieldType]] = {
    "achievement": frozenset({SemanticFieldType.BULLET}),
    "description": frozenset({SemanticFieldType.TEXT, SemanticFieldType.BULLET}),
    "email": frozenset({SemanticFieldType.EMAIL}),
    "end_date": frozenset({SemanticFieldType.DATE}),
    "expires_date": frozenset({SemanticFieldType.DATE}),
    "issued_date": frozenset({SemanticFieldType.DATE}),
    "link": frozenset({SemanticFieldType.URL}),
    "phone": frozenset({SemanticFieldType.PHONE}),
    "start_date": frozenset({SemanticFieldType.DATE}),
}
_DEFAULT_FIELD_TYPES = frozenset({SemanticFieldType.TEXT})


@dataclass(frozen=True, slots=True)
class SemanticSourceAnchor:
    block_id: UUID
    page: int
    start: int
    end: int
    source_sha256: str

    def __post_init__(self) -> None:
        if self.page < 1 or self.start < 0 or self.end <= self.start:
            raise ValueError("invalid semantic source anchor")
        if len(self.source_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.source_sha256
        ):
            raise ValueError("semantic source anchor requires a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "blockId": str(self.block_id),
            "page": self.page,
            "start": self.start,
            "end": self.end,
            "sourceSha256": self.source_sha256,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticSourceAnchor:
        return cls(
            block_id=UUID(str(value["blockId"])),
            page=int(value["page"]),
            start=int(value["start"]),
            end=int(value["end"]),
            source_sha256=str(value["sourceSha256"]),
        )


@dataclass(frozen=True, slots=True)
class SemanticField:
    id: UUID
    name: str
    field_type: SemanticFieldType
    value: str
    confidence_basis_points: int
    review_state: SemanticReviewState
    anchors: tuple[SemanticSourceAnchor, ...] = ()
    date_precision: DatePrecision | None = None

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 80:
            raise ValueError("semantic field name is invalid")
        if not self.value.strip() or len(self.value) > 10_000 or "\x00" in self.value:
            raise ValueError("semantic field value is invalid")
        if not 0 <= self.confidence_basis_points <= 10_000:
            raise ValueError("semantic field confidence is invalid")
        if self.field_type is SemanticFieldType.DATE and self.date_precision is None:
            raise ValueError("semantic date fields require precision")
        if self.field_type is not SemanticFieldType.DATE and self.date_precision is not None:
            raise ValueError("only semantic date fields may carry date precision")
        if self.review_state is SemanticReviewState.USER_ADDED:
            if self.anchors:
                raise ValueError("user-added semantic fields must not claim source anchors")
        elif self.review_state is not SemanticReviewState.REMOVED and not self.anchors:
            raise ValueError("parser-derived semantic fields require source anchors")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "fieldType": self.field_type.value,
            "value": self.value,
            "confidenceBasisPoints": self.confidence_basis_points,
            "reviewState": self.review_state.value,
            "anchors": [anchor.to_dict() for anchor in self.anchors],
            "datePrecision": self.date_precision.value if self.date_precision else None,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticField:
        precision = value.get("datePrecision")
        return cls(
            id=UUID(str(value["id"])),
            name=str(value["name"]),
            field_type=SemanticFieldType(str(value["fieldType"])),
            value=str(value["value"]),
            confidence_basis_points=int(value["confidenceBasisPoints"]),
            review_state=SemanticReviewState(str(value["reviewState"])),
            anchors=tuple(
                SemanticSourceAnchor.from_dict(anchor) for anchor in value.get("anchors", [])
            ),
            date_precision=DatePrecision(str(precision)) if precision else None,
        )


@dataclass(frozen=True, slots=True)
class SemanticEntity:
    id: UUID
    kind: SemanticEntityKind
    review_state: SemanticReviewState
    fields: tuple[SemanticField, ...]
    source_section_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("semantic entities require at least one field")
        identifiers = [field.id for field in self.fields]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("semantic field identifiers must be unique within an entity")
        allowed = _FIELD_NAMES[self.kind]
        if any(field.name not in allowed for field in self.fields):
            raise ValueError(f"semantic entity contains a field not allowed for {self.kind.value}")
        if any(
            field.field_type not in allowed_semantic_field_types(self.kind, field.name)
            for field in self.fields
        ):
            raise ValueError(
                f"semantic entity contains a field type not allowed for {self.kind.value}"
            )
        if (
            self.review_state is SemanticReviewState.USER_ADDED
            and self.source_section_id is not None
        ):
            raise ValueError("user-added semantic entities cannot claim a source section")
        if self.review_state is SemanticReviewState.USER_ADDED and any(
            field.review_state not in {SemanticReviewState.USER_ADDED, SemanticReviewState.REMOVED}
            for field in self.fields
        ):
            raise ValueError("user-added semantic entities require user-added fields")
        if self.review_state is SemanticReviewState.REMOVED and any(
            field.review_state is not SemanticReviewState.REMOVED for field in self.fields
        ):
            raise ValueError("removed semantic entities require removed fields")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "reviewState": self.review_state.value,
            "sourceSectionId": (
                str(self.source_section_id) if self.source_section_id is not None else None
            ),
            "fields": [field.to_dict() for field in self.fields],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticEntity:
        section_id = value.get("sourceSectionId")
        return cls(
            id=UUID(str(value["id"])),
            kind=SemanticEntityKind(str(value["kind"])),
            review_state=SemanticReviewState(str(value["reviewState"])),
            source_section_id=UUID(str(section_id)) if section_id else None,
            fields=tuple(SemanticField.from_dict(field) for field in value.get("fields", [])),
        )


@dataclass(frozen=True, slots=True)
class CanonicalSemantics:
    schema_version: str
    parser_version: str
    entities: tuple[SemanticEntity, ...]
    warnings: tuple[str, ...] = ()
    review_state: SemanticReviewState = SemanticReviewState.UNREVIEWED

    def __post_init__(self) -> None:
        if not self.schema_version or len(self.schema_version) > 80:
            raise ValueError("semantic schema version is invalid")
        if not self.parser_version or len(self.parser_version) > 80:
            raise ValueError("semantic parser version is invalid")
        identifiers = [entity.id for entity in self.entities]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("semantic entity identifiers must be unique")
        field_identifiers = [field.id for entity in self.entities for field in entity.fields]
        if len(field_identifiers) != len(set(field_identifiers)):
            raise ValueError("semantic field identifiers must be globally unique")
        if any(not warning or len(warning) > 160 for warning in self.warnings):
            raise ValueError("semantic parser warning is invalid")
        if self.review_state not in {
            SemanticReviewState.UNREVIEWED,
            SemanticReviewState.CONFIRMED,
            SemanticReviewState.CORRECTED,
        }:
            raise ValueError("semantic aggregate review state is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "parserVersion": self.parser_version,
            "entities": [entity.to_dict() for entity in self.entities],
            "warnings": list(self.warnings),
            "reviewState": self.review_state.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CanonicalSemantics:
        return cls(
            schema_version=str(value["schemaVersion"]),
            parser_version=str(value["parserVersion"]),
            entities=tuple(
                SemanticEntity.from_dict(entity) for entity in value.get("entities", [])
            ),
            warnings=tuple(str(item) for item in value.get("warnings", [])),
            review_state=SemanticReviewState(
                str(value.get("reviewState", SemanticReviewState.UNREVIEWED.value))
            ),
        )


def allowed_semantic_field_names(kind: SemanticEntityKind) -> frozenset[str]:
    """Return the closed field vocabulary for a semantic entity kind."""
    return _FIELD_NAMES[kind]


def allowed_semantic_field_types(
    kind: SemanticEntityKind,
    name: str,
) -> frozenset[SemanticFieldType]:
    """Return the closed type vocabulary for a semantic field name."""
    if name not in _FIELD_NAMES[kind]:
        return frozenset()
    return _FIELD_TYPES.get(name, _DEFAULT_FIELD_TYPES)
