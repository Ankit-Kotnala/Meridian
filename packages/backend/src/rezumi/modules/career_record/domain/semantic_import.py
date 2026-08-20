"""Typed Career Record confirmation, provenance, and semantic import aggregates."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from .errors import CareerRecordTransitionRejected, CareerRecordValidationError


def _bounded_text(value: str, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or "\x00" in normalized:
        raise CareerRecordValidationError(f"{field} is invalid")
    return normalized


def normalize_semantic_url(value: str) -> str:
    """Normalize resume-extracted links into absolute HTTP(S) URLs."""

    normalized = _bounded_text(value, "personal link", 2_048)
    parsed = urlsplit(normalized)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return normalized
    if normalized.lower().startswith("www."):
        return f"https://{normalized}"
    if "://" not in normalized:
        return f"https://{normalized.lstrip('/')}"
    raise CareerRecordValidationError("personal link must use HTTP(S)")


def _personal_fact_value(kind: PersonalFactKind, value: str) -> str:
    normalized = _bounded_text(value, "personal fact value", 2_048)
    if (
        kind is PersonalFactKind.EMAIL
        and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized) is None
    ):
        raise CareerRecordValidationError("personal email is invalid")
    if kind is PersonalFactKind.LINK:
        normalized = normalize_semantic_url(normalized)
    return normalized


class ConfirmationState(StrEnum):
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"


class PersonalFactKind(StrEnum):
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    LOCATION = "location"
    LINK = "link"


class SemanticCandidateKind(StrEnum):
    CONTACT = "contact"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECT = "project"
    SKILL = "skill"
    CERTIFICATION = "certification"


class SemanticImportTarget(StrEnum):
    PERSONAL_FACTS = "personal_facts"
    ENTITY = "entity"
    SKILL = "skill"


class SemanticImportFieldState(StrEnum):
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    USER_ADDED = "user_added"


class SemanticFieldOrigin(StrEnum):
    RESUME_PARSER = "resume_parser"
    RESUME_USER_ADDED = "resume_user_added"
    OWNER_EDIT = "owner_edit"
    OWNER_ATTESTATION = "owner_attestation"


class SemanticImportStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CareerFieldTarget(StrEnum):
    PERSONAL_FACT = "personal_fact"
    ENTITY = "entity"
    SKILL = "skill"


class CareerRelationshipKind(StrEnum):
    EXPERIENCE_PROJECT = "experience_project"


@dataclass(frozen=True, slots=True)
class SemanticImportAnchor:
    block_id: UUID
    page: int
    start_offset: int
    end_offset: int
    source_sha256: bytes
    source_excerpt: str

    def __post_init__(self) -> None:
        if self.page < 1 or self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise CareerRecordValidationError("semantic source anchor is invalid")
        if len(self.source_sha256) != 32:
            raise CareerRecordValidationError("semantic source anchor requires SHA-256")
        object.__setattr__(
            self,
            "source_excerpt",
            _bounded_text(self.source_excerpt, "semantic source excerpt", 1_000),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "blockId": str(self.block_id),
            "page": self.page,
            "startOffset": self.start_offset,
            "endOffset": self.end_offset,
            "sourceSha256": self.source_sha256.hex(),
            "sourceExcerpt": self.source_excerpt,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticImportAnchor:
        return cls(
            block_id=UUID(str(value["blockId"])),
            page=int(value["page"]),
            start_offset=int(value["startOffset"]),
            end_offset=int(value["endOffset"]),
            source_sha256=bytes.fromhex(str(value["sourceSha256"])),
            source_excerpt=str(value["sourceExcerpt"]),
        )


@dataclass(frozen=True, slots=True)
class SemanticImportField:
    semantic_field_id: UUID
    name: str
    field_type: str
    value: str
    review_state: SemanticImportFieldState
    confidence_basis_points: int
    date_precision: str | None
    anchors: tuple[SemanticImportAnchor, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _bounded_text(self.name, "semantic field name", 80))
        object.__setattr__(
            self, "field_type", _bounded_text(self.field_type, "semantic field type", 24)
        )
        object.__setattr__(self, "value", _bounded_text(self.value, "semantic field value", 10_000))
        if not 0 <= self.confidence_basis_points <= 10_000:
            raise CareerRecordValidationError("semantic field confidence is invalid")
        if self.field_type == "date" and self.date_precision not in {
            "day",
            "month",
            "year",
            "unknown",
        }:
            raise CareerRecordValidationError("semantic date precision is invalid")
        if self.field_type != "date" and self.date_precision is not None:
            raise CareerRecordValidationError("only semantic dates may carry precision")
        if self.review_state is SemanticImportFieldState.USER_ADDED:
            if self.anchors:
                raise CareerRecordValidationError(
                    "user-added semantic fields cannot claim source anchors"
                )
        elif not self.anchors:
            raise CareerRecordValidationError(
                "parser-derived semantic fields require source anchors"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "semanticFieldId": str(self.semantic_field_id),
            "name": self.name,
            "fieldType": self.field_type,
            "value": self.value,
            "reviewState": self.review_state.value,
            "confidenceBasisPoints": self.confidence_basis_points,
            "datePrecision": self.date_precision,
            "anchors": [anchor.to_dict() for anchor in self.anchors],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SemanticImportField:
        return cls(
            semantic_field_id=UUID(str(value["semanticFieldId"])),
            name=str(value["name"]),
            field_type=str(value["fieldType"]),
            value=str(value["value"]),
            review_state=SemanticImportFieldState(str(value["reviewState"])),
            confidence_basis_points=int(value["confidenceBasisPoints"]),
            date_precision=(
                str(value["datePrecision"]) if value.get("datePrecision") is not None else None
            ),
            anchors=tuple(
                SemanticImportAnchor.from_dict(anchor) for anchor in value.get("anchors", [])
            ),
        )


@dataclass(frozen=True, slots=True)
class ValidatedSemanticCandidate:
    document_id: UUID
    snapshot_id: UUID
    snapshot_revision: int
    schema_version: str
    parser_version: str
    semantic_entity_id: UUID
    kind: SemanticCandidateKind
    fields: tuple[SemanticImportField, ...]

    def __post_init__(self) -> None:
        if self.snapshot_revision < 1:
            raise CareerRecordValidationError("semantic snapshot revision is invalid")
        _bounded_text(self.schema_version, "semantic schema version", 80)
        _bounded_text(self.parser_version, "semantic parser version", 120)
        if not self.fields:
            raise CareerRecordValidationError("semantic candidate requires reviewed fields")
        identifiers = [field.semantic_field_id for field in self.fields]
        if len(identifiers) != len(set(identifiers)):
            raise CareerRecordValidationError("semantic field identifiers must be unique")


@dataclass(slots=True)
class SemanticImportProposal:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    target: SemanticImportTarget
    target_record_id: UUID | None
    document_id: UUID
    snapshot_id: UUID
    snapshot_revision: int
    schema_version: str
    parser_version: str
    semantic_entity_id: UUID
    semantic_kind: SemanticCandidateKind
    fields: tuple[SemanticImportField, ...]
    status: SemanticImportStatus
    conflict_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
    accepted_values: dict[str, str] | None = None
    decision_idempotency_key: str | None = None

    def __post_init__(self) -> None:
        ValidatedSemanticCandidate(
            document_id=self.document_id,
            snapshot_id=self.snapshot_id,
            snapshot_revision=self.snapshot_revision,
            schema_version=self.schema_version,
            parser_version=self.parser_version,
            semantic_entity_id=self.semantic_entity_id,
            kind=self.semantic_kind,
            fields=self.fields,
        )
        if self.version < 1:
            raise CareerRecordValidationError("semantic proposal version is invalid")
        if self.status is SemanticImportStatus.PENDING and (
            self.reviewed_at is not None
            or self.accepted_values is not None
            or self.decision_idempotency_key is not None
        ):
            raise CareerRecordValidationError("pending semantic proposal has decision data")
        if self.status is SemanticImportStatus.ACCEPTED and (
            self.reviewed_at is None
            or self.accepted_values is None
            or self.decision_idempotency_key is None
        ):
            raise CareerRecordValidationError("accepted semantic proposal lacks reviewed values")
        if self.status is SemanticImportStatus.REJECTED and (
            self.reviewed_at is None
            or self.accepted_values is not None
            or self.decision_idempotency_key is None
        ):
            raise CareerRecordValidationError("rejected semantic proposal state is invalid")

    def accept(self, values: dict[str, str], idempotency_key: str, now: datetime) -> None:
        if self.status is not SemanticImportStatus.PENDING:
            raise CareerRecordTransitionRejected("only a pending semantic proposal can be accepted")
        expected = {str(field.semantic_field_id) for field in self.fields}
        if set(values) != expected:
            raise CareerRecordValidationError(
                "accepted semantic proposal values must match its reviewed fields"
            )
        normalized = {
            str(UUID(key)): _bounded_text(value, "accepted field value", 10_000)
            for key, value in values.items()
        }
        self.status = SemanticImportStatus.ACCEPTED
        self.accepted_values = normalized
        self.decision_idempotency_key = _bounded_text(
            idempotency_key, "decision idempotency key", 128
        )
        self.reviewed_at = now
        self.updated_at = now
        self.version += 1

    def reject(self, idempotency_key: str, now: datetime) -> None:
        if self.status is not SemanticImportStatus.PENDING:
            raise CareerRecordTransitionRejected("only a pending semantic proposal can be rejected")
        self.status = SemanticImportStatus.REJECTED
        self.decision_idempotency_key = _bounded_text(
            idempotency_key, "decision idempotency key", 128
        )
        self.reviewed_at = now
        self.updated_at = now
        self.version += 1

    def payload(self) -> dict[str, object]:
        return {
            "fields": [field.to_dict() for field in self.fields],
            "acceptedValues": self.accepted_values,
        }


@dataclass(slots=True)
class PersonalFact:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    kind: PersonalFactKind
    value: str
    label: str | None
    is_primary: bool
    confirmation: ConfirmationState
    version: int
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.value = _personal_fact_value(self.kind, self.value)
        if self.label is not None:
            normalized = self.label.strip()
            self.label = normalized or None
            if self.label is not None and len(self.label) > 80:
                raise CareerRecordValidationError("personal fact label is invalid")
        if self.version < 1:
            raise CareerRecordValidationError("personal fact version is invalid")
        if (self.confirmation is ConfirmationState.CONFIRMED) != (self.confirmed_at is not None):
            raise CareerRecordValidationError("personal fact confirmation state is invalid")

    def edit(
        self,
        *,
        value: str,
        label: str | None,
        is_primary: bool,
        now: datetime,
    ) -> None:
        self.value = _personal_fact_value(self.kind, value)
        normalized_label = label.strip() if label is not None else ""
        self.label = normalized_label or None
        if self.label is not None and len(self.label) > 80:
            raise CareerRecordValidationError("personal fact label is invalid")
        self.is_primary = is_primary
        self.confirmation = ConfirmationState.NEEDS_REVIEW
        self.confirmed_at = None
        self.updated_at = now
        self.version += 1

    def confirm(self, now: datetime) -> None:
        self.confirmation = ConfirmationState.CONFIRMED
        self.confirmed_at = now
        self.updated_at = now
        self.version += 1


@dataclass(frozen=True, slots=True)
class CareerFieldProvenance:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    target: CareerFieldTarget
    target_id: UUID
    field_name: str
    value_sha256: bytes
    origin: SemanticFieldOrigin
    created_at: datetime
    document_id: UUID | None = None
    snapshot_id: UUID | None = None
    snapshot_revision: int | None = None
    schema_version: str | None = None
    parser_version: str | None = None
    semantic_entity_id: UUID | None = None
    semantic_field_id: UUID | None = None
    anchors: tuple[SemanticImportAnchor, ...] = ()

    def __post_init__(self) -> None:
        _bounded_text(self.field_name, "provenance field name", 80)
        if len(self.value_sha256) != 32:
            raise CareerRecordValidationError("field provenance requires SHA-256")
        semantic_values = (
            self.document_id,
            self.snapshot_id,
            self.snapshot_revision,
            self.schema_version,
            self.parser_version,
            self.semantic_entity_id,
            self.semantic_field_id,
        )
        has_semantic_source = all(value is not None for value in semantic_values)
        if self.origin is SemanticFieldOrigin.OWNER_ATTESTATION:
            if any(value is not None for value in semantic_values) or self.anchors:
                raise CareerRecordValidationError(
                    "owner attestation cannot claim semantic provenance"
                )
        elif not has_semantic_source:
            raise CareerRecordValidationError(
                "resume-derived provenance requires complete semantic identity"
            )
        if self.origin is SemanticFieldOrigin.RESUME_PARSER and not self.anchors:
            raise CareerRecordValidationError("parser provenance requires source anchors")
        if self.origin is SemanticFieldOrigin.RESUME_USER_ADDED and self.anchors:
            raise CareerRecordValidationError(
                "resume user-added provenance cannot claim source anchors"
            )

    @classmethod
    def digest_value(cls, value: str) -> bytes:
        return hashlib.sha256(value.encode("utf-8")).digest()


@dataclass(slots=True)
class CareerEntityConfirmation:
    entity_id: UUID
    owner_user_id: UUID
    state: ConfirmationState
    version: int
    updated_at: datetime
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise CareerRecordValidationError("entity confirmation version is invalid")
        if (self.state is ConfirmationState.CONFIRMED) != (self.confirmed_at is not None):
            raise CareerRecordValidationError("entity confirmation state is invalid")

    def confirm(self, now: datetime) -> None:
        self.state = ConfirmationState.CONFIRMED
        self.confirmed_at = now
        self.updated_at = now
        self.version += 1

    def require_review(self, now: datetime) -> None:
        self.state = ConfirmationState.NEEDS_REVIEW
        self.confirmed_at = None
        self.updated_at = now
        self.version += 1


@dataclass(slots=True)
class CareerSkillConfirmation:
    skill_id: UUID
    owner_user_id: UUID
    state: ConfirmationState
    version: int
    updated_at: datetime
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise CareerRecordValidationError("skill confirmation version is invalid")
        if (self.state is ConfirmationState.CONFIRMED) != (self.confirmed_at is not None):
            raise CareerRecordValidationError("skill confirmation state is invalid")

    def confirm(self, now: datetime) -> None:
        self.state = ConfirmationState.CONFIRMED
        self.confirmed_at = now
        self.updated_at = now
        self.version += 1

    def require_review(self, now: datetime) -> None:
        self.state = ConfirmationState.NEEDS_REVIEW
        self.confirmed_at = None
        self.updated_at = now
        self.version += 1


@dataclass(frozen=True, slots=True)
class CareerEntityRelationship:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    kind: CareerRelationshipKind
    created_at: datetime

    def __post_init__(self) -> None:
        if self.source_entity_id == self.target_entity_id:
            raise CareerRecordValidationError("an entity cannot relate to itself")
