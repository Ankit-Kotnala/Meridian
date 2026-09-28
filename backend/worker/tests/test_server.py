from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from rezumi.modules.resume_health.application import PROCESS_RESUME_TASK

from rezumi_worker import server
from rezumi_worker.config import WorkerSettings


def _settings() -> WorkerSettings:
    return WorkerSettings.model_validate(
        {
            "environment": "test",
            "job_delivery_provider": "qstash",
            "qstash_token": "qstash-token-at-least-32-bytes---",
            "qstash_job_runner_url": "https://jobs.example.com/internal/jobs/qstash",
            "qstash_current_signing_key": "current-signing-key-at-least-32-bytes",
            "qstash_next_signing_key": "next-signing-key-at-least-32-bytes---",
        }
    )


def _signature(*, body: bytes, now: int | None = None) -> str:
    timestamp = int(time.time()) if now is None else now
    key = b"current-signing-key-at-least-32-bytes"
    header = _encode({"alg": "HS256", "typ": "JWT"})
    claims = _encode(
        {
            "iss": "Upstash",
            "sub": "https://jobs.example.com/internal/jobs/qstash",
            "nbf": timestamp - 5,
            "exp": timestamp + 300,
            "body": _base64url(hashlib.sha256(body).digest()),
        }
    )
    signed = f"{header}.{claims}".encode("ascii")
    return f"{header}.{claims}.{_base64url(hmac.new(key, signed, hashlib.sha256).digest())}"


def _encode(value: dict[str, Any]) -> str:
    return _base64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def test_runner_accepts_only_a_valid_signed_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[server.JobEnvelope] = []

    async def fake_execute(
        envelope: server.JobEnvelope,
        _: WorkerSettings,
    ) -> dict[str, str]:
        observed.append(envelope)
        return {"status": "completed"}

    monkeypatch.setattr(server, "execute_job", fake_execute)
    body = json.dumps(
        {"task": PROCESS_RESUME_TASK, "jobId": "9e5a36e9-d573-4b51-a9e4-16469315d4cf"},
        separators=(",", ":"),
    ).encode("utf-8")
    application = server.create_app(_settings())

    with TestClient(application) as client:
        response = client.post(
            "/internal/jobs/qstash",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Upstash-Signature": _signature(body=body),
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "completed"}
    assert observed[0].task == PROCESS_RESUME_TASK


def test_runner_rejects_altered_or_unsigned_requests() -> None:
    application = server.create_app(_settings())
    body = b'{"task":"rezumi.unknown"}'

    with TestClient(application) as client:
        unsigned = client.post("/internal/jobs/qstash", content=body)
        altered = client.post(
            "/internal/jobs/qstash",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Upstash-Signature": _signature(body=b'{"task":"original"}'),
            },
        )

    assert unsigned.status_code == 401
    assert altered.status_code == 401
