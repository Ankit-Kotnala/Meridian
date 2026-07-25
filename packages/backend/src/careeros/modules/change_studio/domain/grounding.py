"""Strict provider-output parsing and deterministic grounding checks."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from .entities import (
    ChangeOperationType,
    ChangeTargetKind,
    ClaimKind,
    GroundingStatus,
    RiskLevel,
    ValidationStatus,
    _text,
)
from .errors import ChangeStudioValidationError, ProviderOutputRejected

SCHEMA_VERSION = "change-studio-provider-output/1"
GROUNDING_VERSION = "change-studio-grounding/1.0.0"
PROMPT_VERSION = "change-studio-prompt/1"
POLICY_VERSION = "ai-grounding-policy/2026-07-14"

_NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?%?")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.-]*")
_HTML_OR_TEMPLATE = re.compile(r"<[^>]+>|javascript:|data:text/html|{{|}}|<script", re.I)
_PROMPT_INJECTION = re.compile(
    r"ignore (all )?(previous|prior) instructions|system prompt|developer message|"
    r"disable (the )?(policy|grounding)|reveal (secrets|tokens)|highest priority",
    re.I,
)
_OWNERSHIP_WORDS = {
    "lead",
    "led",
    "own",
    "owned",
    "owner",
    "managed",
    "manager",
    "directed",
}
_CAUSAL_WORDS = {"drove", "increased", "reduced", "resulted", "caused", "improved"}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True, slots=True)
class MetricContext:
    value: Decimal
    value_max: Decimal | None
    unit: str
    period: str
    attribution: str


@dataclass(frozen=True, slots=True)
class EvidenceGroundingContext:
    id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    title: str
    statement: str
    context: str | None
    strength: str
    metrics: tuple[MetricContext, ...]

    def __post_init__(self) -> None:
        if self.revision_number < 1:
            raise ChangeStudioValidationError("evidence grounding revision must be positive")
        if (
            re.fullmatch(r"[0-9a-f]{64}", self.statement_sha256) is None
            or hashlib.sha256(self.statement.encode("utf-8")).hexdigest() != self.statement_sha256
        ):
            raise ChangeStudioValidationError("evidence grounding statement hash is invalid")

    @property
    def source_text(self) -> str:
        return " ".join(part for part in (self.title, self.statement, self.context) if part)

    @property
    def numeric_eligible(self) -> bool:
        return self.strength in {"confirmed", "verified"} and bool(self.metrics)


@dataclass(frozen=True, slots=True)
class RequirementGroundingContext:
    id: UUID
    text: str
    requirement_type: str
    importance: str


@dataclass(frozen=True, slots=True)
class ProviderClaimCandidate:
    text: str
    kind: ClaimKind
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ProviderOperationCandidate:
    operation_type: ChangeOperationType
    target_id: UUID
    target_kind: ChangeTargetKind
    before: str
    after: str
    reason: str
    claims: tuple[ProviderClaimCandidate, ...]
    requirement_ids: tuple[UUID, ...]
    confidence_basis_points: int
    risk: RiskLevel
    requires_confirmation: bool
    expected_score_delta_basis_points: int | None


@dataclass(frozen=True, slots=True)
class ProviderQuestionCandidate:
    requirement_id: UUID | None
    evidence_id: UUID | None
    question: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_micros: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderCandidateResponse:
    operations: tuple[ProviderOperationCandidate, ...]
    questions: tuple[ProviderQuestionCandidate, ...]
    usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    candidate: ProviderClaimCandidate
    evidence: EvidenceGroundingContext
    status: ValidationStatus
    codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    status: GroundingStatus
    codes: tuple[str, ...]
    claims: tuple[GroundedClaim, ...]


def parse_provider_payload(payload: Mapping[str, Any]) -> ProviderCandidateResponse:
    _only(payload, {"operations", "questions", "usage"}, "provider response")
    operations = _list(payload.get("operations"), "operations", maximum=20)
    questions = _list(payload.get("questions", []), "questions", maximum=20)
    usage_raw = payload.get("usage") or {}
    if not isinstance(usage_raw, Mapping):
        raise ProviderOutputRejected("usage must be an object")
    _only(usage_raw, {"promptTokens", "completionTokens", "costMicros"}, "usage")
    return ProviderCandidateResponse(
        operations=tuple(_operation(item) for item in operations),
        questions=tuple(_question(item) for item in questions),
        usage=ProviderUsage(
            prompt_tokens=_optional_nonnegative_int(usage_raw.get("promptTokens"), "promptTokens"),
            completion_tokens=_optional_nonnegative_int(
                usage_raw.get("completionTokens"), "completionTokens"
            ),
            cost_micros=_optional_nonnegative_int(usage_raw.get("costMicros"), "costMicros"),
        ),
    )


def ground_operation(
    candidate: ProviderOperationCandidate,
    *,
    evidence: Mapping[UUID, EvidenceGroundingContext],
    requirements: Mapping[UUID, RequirementGroundingContext],
) -> GroundingDecision:
    codes: list[str] = []
    claims: list[GroundedClaim] = []

    if _unsafe_sink(candidate.after) or _unsafe_sink(candidate.before):
        codes.append("sink_unsafe")
    if not candidate.claims:
        codes.append("missing_claim_ledger")
    if not candidate.after.strip():
        codes.append("empty_suggestion")
    for requirement_id in candidate.requirement_ids:
        if requirement_id not in requirements:
            codes.append("unauthorized_requirement")

    claim_text = " ".join(claim.text for claim in candidate.claims)
    after_tokens = {
        token
        for token in _tokens(candidate.after)
        if token not in _STOPWORDS and not _NUMBER.fullmatch(token)
    }
    claim_tokens = set(_tokens(claim_text))
    unsupported_after_tokens = after_tokens - claim_tokens
    if unsupported_after_tokens:
        codes.append("undeclared_text_tokens")

    for claim in candidate.claims:
        claim_codes: list[str] = []
        if _unsafe_sink(claim.text):
            claim_codes.append("claim_sink_unsafe")
        if _contains(candidate.after, claim.text) is False:
            claim_codes.append("claim_missing_from_suggestion")
        if not claim.evidence_ids:
            claim_codes.append("claim_missing_evidence")

        primary: EvidenceGroundingContext | None = None
        for evidence_id in claim.evidence_ids:
            evidence_context = evidence.get(evidence_id)
            if evidence_context is None:
                claim_codes.append("unauthorized_evidence")
                continue
            primary = primary or evidence_context
            if not _contains(evidence_context.source_text, claim.text):
                claim_codes.append("unsupported_claim")
            if _numbers(claim.text) and not _numeric_supported(claim.text, evidence_context):
                claim_codes.append("numeric_not_grounded")
            claim_tokens_for_semantics = set(_tokens(claim.text))
            evidence_tokens = set(_tokens(evidence_context.source_text))
            if _OWNERSHIP_WORDS & claim_tokens_for_semantics and not (
                _OWNERSHIP_WORDS & evidence_tokens
            ):
                claim_codes.append("contribution_elevation")
            if _CAUSAL_WORDS & claim_tokens_for_semantics and not (_CAUSAL_WORDS & evidence_tokens):
                claim_codes.append("causality_elevation")

        if primary is not None:
            claims.append(
                GroundedClaim(
                    candidate=claim,
                    evidence=primary,
                    status=ValidationStatus.FAILED if claim_codes else ValidationStatus.PASSED,
                    codes=tuple(dict.fromkeys(claim_codes or ["grounded"])),
                )
            )
        codes.extend(claim_codes)

    final_codes = tuple(dict.fromkeys(codes or ["grounded"]))
    return GroundingDecision(
        status=(
            GroundingStatus.GROUNDED if final_codes == ("grounded",) else GroundingStatus.BLOCKED
        ),
        codes=final_codes,
        claims=tuple(claims),
    )


def validate_question(
    candidate: ProviderQuestionCandidate,
    *,
    requirements: Mapping[UUID, RequirementGroundingContext],
    evidence: Mapping[UUID, EvidenceGroundingContext],
) -> tuple[str, ...]:
    codes: list[str] = []
    if candidate.requirement_id is not None and candidate.requirement_id not in requirements:
        codes.append("unauthorized_requirement")
    if candidate.evidence_id is not None and candidate.evidence_id not in evidence:
        codes.append("unauthorized_evidence")
    if _unsafe_sink(candidate.question) or _unsafe_sink(candidate.reason):
        codes.append("sink_unsafe")
    if re.search(r"\b(around|about|approximately)\s+[-+]?\d", candidate.question, re.I):
        codes.append("leading_numeric_question")
    return tuple(dict.fromkeys(codes or ["question_valid"]))


def _operation(value: Any) -> ProviderOperationCandidate:
    if not isinstance(value, Mapping):
        raise ProviderOutputRejected("operation must be an object")
    _only(
        value,
        {
            "operationType",
            "targetId",
            "targetKind",
            "before",
            "after",
            "reason",
            "claims",
            "requirementIds",
            "confidenceBasisPoints",
            "risk",
            "requiresConfirmation",
            "expectedScoreDeltaBasisPoints",
        },
        "operation",
    )
    claims = _list(value.get("claims"), "claims", maximum=20)
    requirement_ids = _list(value.get("requirementIds", []), "requirementIds", maximum=20)
    confidence = _int(value.get("confidenceBasisPoints"), "confidenceBasisPoints")
    if not 0 <= confidence <= 10_000:
        raise ProviderOutputRejected("confidenceBasisPoints is out of range")
    delta = value.get("expectedScoreDeltaBasisPoints")
    parsed_delta = None if delta is None else _int(delta, "expectedScoreDeltaBasisPoints")
    if parsed_delta is not None and not -10_000 <= parsed_delta <= 10_000:
        raise ProviderOutputRejected("expectedScoreDeltaBasisPoints is out of range")
    requires_confirmation = value.get("requiresConfirmation")
    if not isinstance(requires_confirmation, bool):
        raise ProviderOutputRejected("requiresConfirmation must be boolean")
    return ProviderOperationCandidate(
        operation_type=ChangeOperationType(_string(value.get("operationType"), "operationType")),
        target_id=_uuid(value.get("targetId"), "targetId"),
        target_kind=ChangeTargetKind(_string(value.get("targetKind"), "targetKind")),
        before=_text(_string(value.get("before"), "before"), "before", 2_000, minimum=0),
        after=_text(_string(value.get("after"), "after"), "after", 2_000),
        reason=_text(_string(value.get("reason"), "reason"), "reason", 1_000),
        claims=tuple(_claim(item) for item in claims),
        requirement_ids=tuple(_uuid(item, "requirementId") for item in requirement_ids),
        confidence_basis_points=confidence,
        risk=RiskLevel(_string(value.get("risk"), "risk")),
        requires_confirmation=requires_confirmation,
        expected_score_delta_basis_points=parsed_delta,
    )


def _claim(value: Any) -> ProviderClaimCandidate:
    if not isinstance(value, Mapping):
        raise ProviderOutputRejected("claim must be an object")
    _only(value, {"text", "kind", "evidenceIds"}, "claim")
    evidence_ids = _list(value.get("evidenceIds"), "evidenceIds", maximum=8)
    return ProviderClaimCandidate(
        text=_text(_string(value.get("text"), "claim.text"), "claim text", 1_000),
        kind=ClaimKind(_string(value.get("kind"), "claim.kind")),
        evidence_ids=tuple(_uuid(item, "evidenceId") for item in evidence_ids),
    )


def _question(value: Any) -> ProviderQuestionCandidate:
    if not isinstance(value, Mapping):
        raise ProviderOutputRejected("question must be an object")
    _only(value, {"requirementId", "evidenceId", "question", "reason"}, "question")
    requirement_id = value.get("requirementId")
    evidence_id = value.get("evidenceId")
    return ProviderQuestionCandidate(
        requirement_id=None if requirement_id is None else _uuid(requirement_id, "requirementId"),
        evidence_id=None if evidence_id is None else _uuid(evidence_id, "evidenceId"),
        question=_text(_string(value.get("question"), "question"), "question", 1_000),
        reason=_text(_string(value.get("reason"), "reason"), "reason", 1_000),
    )


def _only(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extras = set(value) - allowed
    optional = {
        "provider response": {"questions", "usage"},
        "usage": {"promptTokens", "completionTokens", "costMicros"},
    }.get(label, set())
    missing = {key for key in allowed if key not in value and key not in optional}
    if extras:
        raise ProviderOutputRejected(f"{label} contains unsupported fields")
    if missing:
        raise ProviderOutputRejected(f"{label} is missing required fields")


def _list(value: Any, field: str, *, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise ProviderOutputRejected(f"{field} must be an array")
    if len(value) > maximum:
        raise ProviderOutputRejected(f"{field} exceeds maximum length")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ProviderOutputRejected(f"{field} must be a string")
    return value


def _int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProviderOutputRejected(f"{field} must be an integer")
    return value


def _optional_nonnegative_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    parsed = _int(value, field)
    if parsed < 0:
        raise ProviderOutputRejected(f"{field} must be nonnegative")
    return parsed


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(_string(value, field))
    except ValueError as exc:
        raise ProviderOutputRejected(f"{field} must be a UUID") from exc


def _contains(container: str, item: str) -> bool:
    return _normalize(item) in _normalize(container)


def _normalize(value: str) -> str:
    return " ".join(_tokens(value))


def _tokens(value: str) -> list[str]:
    return [match.group(0).casefold() for match in _TOKEN.finditer(value)]


def _numbers(value: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMBER.finditer(value)}


def _numeric_supported(claim_text: str, evidence: EvidenceGroundingContext) -> bool:
    if not evidence.numeric_eligible:
        return False
    source_numbers = _numbers(evidence.source_text)
    metric_numbers = {_decimal_string(metric.value) for metric in evidence.metrics} | {
        _decimal_string(metric.value_max)
        for metric in evidence.metrics
        if metric.value_max is not None
    }
    return _numbers(claim_text).issubset(source_numbers | metric_numbers)


def _decimal_string(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f").rstrip("0").rstrip(".")


def _unsafe_sink(value: str) -> bool:
    return bool(_HTML_OR_TEMPLATE.search(value) or _PROMPT_INJECTION.search(value))
