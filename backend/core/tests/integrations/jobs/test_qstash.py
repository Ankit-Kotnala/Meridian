from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from rezumi.integrations.jobs import QStashClient, QStashOptions, QStashPublishError


def _options() -> QStashOptions:
    return QStashOptions(
        token="a" * 32,
        destination_url="https://jobs.example.com/internal/jobs/qstash",
        base_url="https://qstash.example.com",
    )


def test_publish_posts_redacted_identifier_payload_to_qstash() -> None:
    received: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        received["url"] = str(request.url)
        received["headers"] = dict(request.headers)
        received["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"messageId": "msg_123"})

    async def exercise() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = QStashClient(_options(), client=client)
            await publisher.publish({"task": "rezumi.worker.resume.process", "jobId": "job-1"})

    asyncio.run(exercise())

    assert received["url"] == (
        "https://qstash.example.com/v2/publish/https://jobs.example.com/internal/jobs/qstash"
    )
    headers = received["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == f"Bearer {'a' * 32}"
    assert headers["upstash-redact-fields"] == "body"
    assert received["payload"] == {"task": "rezumi.worker.resume.process", "jobId": "job-1"}


def test_upsert_schedule_uses_stable_schedule_id() -> None:
    received: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        received["url"] = str(request.url)
        received["headers"] = dict(request.headers)
        return httpx.Response(200, json={"scheduleId": "rezumi-maintenance"})

    async def exercise() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            publisher = QStashClient(_options(), client=client)
            await publisher.upsert_schedule(
                schedule_id="rezumi-maintenance",
                cron="*/15 * * * *",
                payload={"task": "rezumi.cloud.maintenance.sweep"},
            )

    asyncio.run(exercise())

    assert received["url"] == (
        "https://qstash.example.com/v2/schedules/https://jobs.example.com/internal/jobs/qstash"
    )
    headers = received["headers"]
    assert isinstance(headers, dict)
    assert headers["upstash-schedule-id"] == "rezumi-maintenance"
    assert headers["upstash-cron"] == "*/15 * * * *"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("destination_url", "http://jobs.example.com/internal/jobs/qstash"),
        ("base_url", "https://qstash.example.com/v2"),
    ],
)
def test_options_reject_unsafe_urls(field: str, value: str) -> None:
    values = {
        "token": "a" * 32,
        "destination_url": "https://jobs.example.com/internal/jobs/qstash",
        "base_url": "https://qstash.example.com",
    }
    values[field] = value

    with pytest.raises(ValueError):
        QStashOptions(**values)


def test_publish_hides_transport_errors() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async def exercise() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(QStashPublishError, match="qstash_publish_failed"):
                await QStashClient(_options(), client=client).publish({"task": "test"})

    asyncio.run(exercise())
