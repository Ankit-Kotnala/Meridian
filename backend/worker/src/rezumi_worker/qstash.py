"""QStash delivery and signature verification for the stateless job runner."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from rezumi.integrations.jobs import QStashClient
from rezumi.modules.resume_builder.domain import ResumeExportOperation


class QStashSignatureError(ValueError):
    """A public job request did not originate from the configured QStash instance."""


@dataclass(frozen=True, slots=True)
class QStashSignatureVerifier:
    """Verify the HMAC JWT and raw-body hash sent by QStash.

    QStash retries may legitimately invoke the same durable job more than once;
    every Rezumi job remains fenced/idempotent at the database layer.
    """

    current_signing_key: str
    next_signing_key: str
    expected_url: str

    def __post_init__(self) -> None:
        if len(self.current_signing_key.strip()) < 16:
            raise ValueError("QStash current signing key must be configured")
        if len(self.next_signing_key.strip()) < 16:
            raise ValueError("QStash next signing key must be configured")
        if not self.expected_url.startswith("https://"):
            raise ValueError("QStash expected URL must use HTTPS")

    def verify(self, *, signature: str | None, body: bytes, now: int | None = None) -> None:
        if not signature:
            raise QStashSignatureError("missing_qstash_signature")
        segments = signature.split(".")
        if len(segments) != 3:
            raise QStashSignatureError("invalid_qstash_signature")
        header, encoded_claims, encoded_signature = segments
        signed_portion = f"{header}.{encoded_claims}".encode("ascii")
        if not any(
            hmac.compare_digest(
                _base64url_encode(
                    hmac.new(key.encode("utf-8"), signed_portion, hashlib.sha256).digest()
                ),
                encoded_signature,
            )
            for key in (self.current_signing_key, self.next_signing_key)
        ):
            raise QStashSignatureError("invalid_qstash_signature")

        try:
            claims = json.loads(_base64url_decode(encoded_claims))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise QStashSignatureError("invalid_qstash_claims") from exc
        if not isinstance(claims, dict):
            raise QStashSignatureError("invalid_qstash_claims")
        timestamp = int(time.time()) if now is None else now
        if claims.get("iss") != "Upstash" or claims.get("sub") != self.expected_url:
            raise QStashSignatureError("invalid_qstash_claims")
        if not _valid_timestamp(claims.get("exp"), now=timestamp, comparator="expires"):
            raise QStashSignatureError("expired_qstash_signature")
        if not _valid_timestamp(claims.get("nbf"), now=timestamp, comparator="not_before"):
            raise QStashSignatureError("invalid_qstash_claims")
        expected_hash = _base64url_encode(hashlib.sha256(body).digest())
        provided_hash = claims.get("body")
        if not isinstance(provided_hash, str) or not hmac.compare_digest(
            provided_hash.rstrip("="), expected_hash
        ):
            raise QStashSignatureError("invalid_qstash_body")


class QStashWorkerPublisher:
    """Adapts all worker outboxes to QStash's identifier-only envelope."""

    def __init__(self, client: QStashClient) -> None:
        self._client = client

    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None:
        await self._client.publish(
            {
                "task": task_name,
                "jobId": str(job_id),
                "traceId": trace_id[:64],
            }
        )

    async def publish_analytics(self, job_id: UUID) -> None:
        await self._client.publish(
            {
                "task": "rezumi.worker.career_analytics.process_refresh",
                "jobId": str(job_id),
            }
        )

    async def publish_resume_export(
        self,
        export_id: UUID,
        trace_id: str,
        operation: ResumeExportOperation,
    ) -> None:
        await self._client.publish(
            {
                "task": "rezumi.worker.resume_builder.process_export",
                "exportId": str(export_id),
                "operation": operation.value,
                "traceId": trace_id[:64],
            }
        )


class QStashAnalyticsPublisher:
    """Match the analytics outbox's single-identifier publisher protocol."""

    def __init__(self, publisher: QStashWorkerPublisher) -> None:
        self._publisher = publisher

    async def publish(self, job_id: UUID) -> None:
        await self._publisher.publish_analytics(job_id)


class QStashResumeExportPublisher:
    """Match the resume-export outbox's operation-aware publisher protocol."""

    def __init__(self, publisher: QStashWorkerPublisher) -> None:
        self._publisher = publisher

    async def publish(
        self,
        export_id: UUID,
        trace_id: str,
        operation: ResumeExportOperation,
    ) -> None:
        await self._publisher.publish_resume_export(export_id, trace_id, operation)


def _base64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _valid_timestamp(value: Any, *, now: int, comparator: str) -> bool:
    if not isinstance(value, int):
        return False
    if comparator == "expires":
        return now <= value
    return now >= value
