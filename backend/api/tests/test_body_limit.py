"""Request body limits reject declared and streamed payloads without buffering."""

import json
from collections.abc import Iterator
from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient
from rezumi.modules.identity.application import IdentityService
from starlette.types import Message, Scope

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.main import create_app
from rezumi_api.middleware import RequestBodyLimitMiddleware


def test_declared_oversize_is_rejected_before_body_or_dependencies_are_read(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    limited = settings.model_copy(update={"max_request_body_bytes": 1_024})
    service = create_autospec(IdentityService, instance=True)

    with TestClient(create_app(limited, database=fake_database, identity=service)) as client:
        response = client.post(
            "/api/v1/auth/register",
            content=b"x" * 1_025,
            headers={
                "Content-Length": "1025",
                "Content-Type": "application/json",
                "X-Request-ID": "oversize-request",
            },
        )

    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Request-ID"] == "oversize-request"
    assert response.json() == {
        "type": "https://rezumi.example/problems/payload-too-large",
        "title": "Payload too large",
        "status": 413,
        "code": "payload_too_large",
        "detail": "The request body exceeds the allowed size.",
        "instance": "/api/v1/auth/register",
        "requestId": "oversize-request",
        "errors": [],
    }
    service.register.assert_not_awaited()


@pytest.mark.asyncio
async def test_chunked_oversize_is_rejected_after_cumulative_limit_without_buffering() -> None:
    downstream_received: list[bytes] = []

    async def downstream(scope: Scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        del scope
        while True:
            message = await receive()
            downstream_received.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    requests: Iterator[Message] = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ]
    )

    async def receive() -> Message:
        return next(requests)

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/register",
        "raw_path": b"/api/v1/auth/register",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"transfer-encoding", b"chunked")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {"request_id": "chunked-request"},
    }
    middleware = RequestBodyLimitMiddleware(downstream, max_body_bytes=4)

    await middleware(scope, receive, send)

    assert downstream_received == [b"123"]
    assert sent[0]["status"] == 413
    body = json.loads(sent[1]["body"])
    assert body["code"] == "payload_too_large"
    assert body["requestId"] == "chunked-request"


def test_normal_requests_pass_through_body_limit(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    limited = settings.model_copy(update={"max_request_body_bytes": 1_024})

    with TestClient(create_app(limited, database=fake_database)) as client:
        response = client.get("/health")

    assert response.status_code == 200
