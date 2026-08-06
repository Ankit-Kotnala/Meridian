"""Suggestion-provider implementations for Change Studio."""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from rezumi.modules.change_studio.application import AiGenerationRequest, AiProviderResponse
from rezumi.modules.change_studio.application.ports import SuggestionProvider
from rezumi.modules.change_studio.domain import ChangeStudioUnavailable


class DeterministicSuggestionProvider:
    """Local provider for tests and development; it only reuses eligible evidence text."""

    provider_name = "deterministic-local"
    provider_model = "change-studio-fake/1"

    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse:
        evidence_by_id = {item.id: item for item in request.evidence}
        operations: list[dict[str, object]] = []
        questions: list[dict[str, object]] = []
        for requirement in request.job.requirements:
            if len(operations) >= request.max_operations:
                break
            evidence = next(
                (
                    evidence_by_id[evidence_id]
                    for evidence_id in requirement.evidence_ids
                    if evidence_id in evidence_by_id
                ),
                None,
            )
            if evidence is None:
                questions.append(
                    {
                        "requirementId": str(requirement.requirement.id),
                        "evidenceId": None,
                        "question": (
                            "What evidence can support this requirement: "
                            f"{requirement.requirement.text}"
                        ),
                        "reason": (
                            "No eligible evidence is currently available for this requirement."
                        ),
                    }
                )
                continue
            statement = _shape_text(evidence.statement, request.length, request.preserve_terms)
            operations.append(
                {
                    "operationType": "add_bullet",
                    "targetId": str(requirement.requirement.id),
                    "targetKind": request.target_kind.value,
                    "before": "",
                    "after": statement,
                    "reason": (
                        "Uses eligible Career Record evidence that already matched this "
                        "job requirement."
                    ),
                    "claims": [
                        {
                            "text": statement,
                            "kind": _claim_kind(
                                requirement.requirement.requirement_type,
                                statement,
                            ),
                            "evidenceIds": [str(evidence.id)],
                        }
                    ],
                    "requirementIds": [str(requirement.requirement.id)],
                    "confidenceBasisPoints": 9200,
                    "risk": "medium" if evidence.metrics else "low",
                    "requiresConfirmation": True,
                    "expectedScoreDeltaBasisPoints": 150
                    if request.job.display_score is not None
                    else None,
                }
            )
        return AiProviderResponse(
            provider_name=self.provider_name,
            provider_model=self.provider_model,
            latency_ms=0,
            payload={
                "operations": operations,
                "questions": questions[:10],
                "usage": {
                    "promptTokens": len(request.evidence) * 24 + len(request.job.requirements) * 16,
                    "completionTokens": len(operations) * 18 + len(questions) * 12,
                    "costMicros": 0,
                },
            },
        )


class DisabledSuggestionProvider:
    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse:
        del request
        raise ChangeStudioUnavailable("AI provider is disabled")


@dataclass(frozen=True, slots=True)
class HttpJsonProviderOptions:
    endpoint_url: str
    api_key: str
    timeout_seconds: float = 10.0
    max_attempts: int = 2
    max_response_bytes: int = 262_144


class HttpJsonSuggestionProvider:
    """Production-capable strict JSON adapter without committing provider credentials."""

    provider_name = "http-json"
    provider_model = "configured-remote"

    def __init__(self, options: HttpJsonProviderOptions) -> None:
        if not options.endpoint_url.startswith("https://"):
            raise ValueError("AI HTTP provider endpoint must use HTTPS")
        if not options.api_key:
            raise ValueError("AI HTTP provider requires an API key")
        if not 1 <= options.max_attempts <= 3:
            raise ValueError("AI HTTP retry attempts must be between 1 and 3")
        self._options = options

    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse:
        body = json.dumps(_request_payload(request), separators=(",", ":")).encode("utf-8")
        last_error: Exception | None = None
        started = time.perf_counter()
        for attempt in range(self._options.max_attempts):
            try:
                payload = await asyncio.to_thread(self._post, body)
                return AiProviderResponse(
                    provider_name=self.provider_name,
                    provider_model=self.provider_model,
                    latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
                    payload=payload,
                )
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                last_error = exc
                if attempt + 1 >= self._options.max_attempts:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))
        raise ChangeStudioUnavailable("AI provider request failed") from last_error

    def _post(self, body: bytes) -> dict[str, object]:
        request = urllib.request.Request(  # noqa: S310 - constructor rejects non-HTTPS URLs.
            self._options.endpoint_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._options.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(  # noqa: S310 - endpoint was validated as HTTPS.
            request,
            timeout=self._options.timeout_seconds,
        ) as response:
            raw = response.read(self._options.max_response_bytes + 1)
        if len(raw) > self._options.max_response_bytes:
            raise ChangeStudioUnavailable("AI provider response exceeded the size limit")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ChangeStudioUnavailable("AI provider response must be an object")
        return cast(dict[str, object], parsed)


class CircuitBreakingSuggestionProvider:
    def __init__(
        self,
        provider: SuggestionProvider,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: int = 60,
    ) -> None:
        self._provider = provider
        self._failure_threshold = failure_threshold
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._failures = 0
        self._opened_until: datetime | None = None

    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse:
        now = datetime.now().astimezone()
        if self._opened_until is not None and now < self._opened_until:
            raise ChangeStudioUnavailable("AI provider circuit is open")
        try:
            response = await self._provider.generate(request)
        except Exception:
            self._failures += 1
            if self._failures >= self._failure_threshold:
                self._opened_until = now + self._cooldown
            raise
        self._failures = 0
        self._opened_until = None
        return response


def _shape_text(statement: str, length: str, preserve_terms: tuple[str, ...]) -> str:
    text = statement.strip()
    if length == "concise":
        sentence_end = min(
            (index for index in [text.find("."), text.find(";")] if index >= 40),
            default=-1,
        )
        if sentence_end > 0:
            text = text[: sentence_end + 1]
    for term in preserve_terms:
        if term and term.casefold() not in text.casefold():
            return statement.strip()
    return text


def _claim_kind(requirement_type: str, statement: str) -> str:
    if any(character.isdigit() for character in statement):
        return "metric_outcome"
    if requirement_type in {"skill", "certification", "experience"}:
        return "skill" if requirement_type == "skill" else requirement_type
    return "responsibility"


def _request_payload(request: AiGenerationRequest) -> dict[str, object]:
    return {
        "purpose": request.purpose,
        "targetKind": request.target_kind.value,
        "tone": request.tone,
        "length": request.length,
        "maxOperations": request.max_operations,
        "alternativeForOperationId": (
            str(request.alternative_for_operation_id)
            if request.alternative_for_operation_id
            else None
        ),
        "preserveTerms": list(request.preserve_terms),
        "job": {
            "id": str(request.job.job_id),
            "analysisId": str(request.job.analysis_id),
            "title": request.job.job_title,
            "displayScore": request.job.display_score,
            "requirements": [
                {
                    "id": str(item.requirement.id),
                    "text": item.requirement.text,
                    "type": item.requirement.requirement_type,
                    "importance": item.requirement.importance,
                    "matchState": item.match_state,
                    "hardGap": item.hard_gap,
                    "evidenceIds": [str(value) for value in item.evidence_ids],
                }
                for item in request.job.requirements
            ],
        },
        "evidence": [
            {
                "id": str(item.id),
                "title": item.title,
                "statement": item.statement,
                "context": item.context,
                "strength": item.strength,
                "metrics": [
                    {
                        "value": str(metric.value),
                        "valueMax": str(metric.value_max) if metric.value_max is not None else None,
                        "unit": metric.unit,
                        "period": metric.period,
                        "attribution": metric.attribution,
                    }
                    for metric in item.metrics
                ],
            }
            for item in request.evidence
        ],
        "schemaVersion": "change-studio-provider-output/1",
    }
