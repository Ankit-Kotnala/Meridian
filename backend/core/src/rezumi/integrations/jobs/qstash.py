"""Minimal QStash REST adapter for identifier-only Rezumi jobs.

This module deliberately uses QStash's documented HTTP API instead of making
product modules depend on a queue SDK.  It never accepts resume content or
other candidate data: all delivery payloads are small, durable identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

import httpx


class QStashPublishError(RuntimeError):
    """Raised when QStash does not durably accept a delivery request."""


@dataclass(frozen=True, slots=True)
class QStashOptions:
    """Validated transport configuration for a single public job endpoint."""

    token: str
    destination_url: str
    base_url: str = "https://qstash.upstash.io"
    retries: int = 3
    # Leave room for the runner to serialize and return a response after its
    # 300-second default hard task limit.
    delivery_timeout_seconds: int = 330
    publish_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if len(self.token.strip()) < 16:
            raise ValueError("QStash token must be configured")
        _validate_https_origin_url(self.destination_url, field_name="destination_url")
        _validate_https_origin_url(self.base_url, field_name="base_url")
        if not 0 <= self.retries <= 10:
            raise ValueError("QStash retries must be between 0 and 10")
        if not 10 <= self.delivery_timeout_seconds <= 900:
            raise ValueError("QStash delivery timeout must be between 10 and 900 seconds")
        if not 1 <= self.publish_timeout_seconds <= 30:
            raise ValueError("QStash publish timeout must be between 1 and 30 seconds")


class QStashClient:
    """Publish redacted, retryable work to a signed public endpoint."""

    def __init__(
        self,
        options: QStashOptions,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._options = options
        self._client = client

    async def publish(self, payload: dict[str, Any]) -> None:
        """Accept only a compact JSON object and request durable QStash delivery."""

        encoded_destination = quote(self._options.destination_url, safe=":/")
        endpoint = f"{self._options.base_url}/v2/publish/{encoded_destination}"
        headers = self._headers()
        if self._client is not None:
            await self._post(self._client, endpoint, headers, payload)
            return

        timeout = httpx.Timeout(self._options.publish_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await self._post(client, endpoint, headers, payload)

    async def upsert_schedule(
        self,
        *,
        schedule_id: str,
        cron: str,
        payload: dict[str, Any],
    ) -> None:
        """Create or replace a deterministic schedule without duplicate cron jobs."""

        if not schedule_id or len(schedule_id) > 128:
            raise ValueError("QStash schedule_id must contain 1 to 128 characters")
        if not cron.strip() or len(cron) > 256:
            raise ValueError("QStash cron expression must contain 1 to 256 characters")
        encoded_destination = quote(self._options.destination_url, safe=":/")
        endpoint = f"{self._options.base_url}/v2/schedules/{encoded_destination}"
        headers = {
            **self._headers(),
            "Upstash-Cron": cron,
            "Upstash-Schedule-Id": schedule_id,
            "Upstash-Label": "rezumi",
        }
        if self._client is not None:
            await self._post(self._client, endpoint, headers, payload)
            return

        timeout = httpx.Timeout(self._options.publish_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await self._post(client, endpoint, headers, payload)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._options.token}",
            "Content-Type": "application/json",
            "Upstash-Method": "POST",
            "Upstash-Retries": str(self._options.retries),
            "Upstash-Timeout": f"{self._options.delivery_timeout_seconds}s",
            # Payloads contain only durable identifiers, but their identifiers
            # should not become visible in shared operational dashboards.
            "Upstash-Redact-Fields": "body",
        }

    async def _post(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> None:
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise QStashPublishError("qstash_publish_failed") from exc


def _validate_https_origin_url(value: str, *, field_name: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"QStash {field_name} must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"QStash {field_name} must not include credentials, query, or fragment")
    if parsed.path not in {"", "/"} and field_name == "base_url":
        raise ValueError("QStash base_url must not include a path")
