from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from rezumi_worker.qstash import QStashSignatureError, QStashSignatureVerifier


def _signature(*, key: str, body: bytes, url: str, now: int = 1_800_000_000) -> str:
    header = _encode({"alg": "HS256", "typ": "JWT"})
    claims = _encode(
        {
            "iss": "Upstash",
            "sub": url,
            "nbf": now - 5,
            "exp": now + 300,
            "body": _base64url(hashlib.sha256(body).digest()),
        }
    )
    signed = f"{header}.{claims}".encode("ascii")
    signature = _base64url(hmac.new(key.encode("utf-8"), signed, hashlib.sha256).digest())
    return f"{header}.{claims}.{signature}"


def _encode(value: object) -> str:
    return _base64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def test_signature_verifier_accepts_current_key_and_exact_raw_body() -> None:
    endpoint = "https://jobs.example.com/internal/jobs/qstash"
    body = b'{"task":"rezumi.resume_health.process"}'
    key = "current-signing-key-at-least-32-bytes"
    verifier = QStashSignatureVerifier(
        current_signing_key=key,
        next_signing_key="next-signing-key-at-least-32-bytes---",
        expected_url=endpoint,
    )

    verifier.verify(
        signature=_signature(key=key, body=body, url=endpoint), body=body, now=1_800_000_000
    )


@pytest.mark.parametrize("body", [b"{}", b'{"task":"other"}'])
def test_signature_verifier_rejects_wrong_raw_body(body: bytes) -> None:
    endpoint = "https://jobs.example.com/internal/jobs/qstash"
    key = "current-signing-key-at-least-32-bytes"
    verifier = QStashSignatureVerifier(
        current_signing_key=key,
        next_signing_key="next-signing-key-at-least-32-bytes---",
        expected_url=endpoint,
    )

    with pytest.raises(QStashSignatureError, match="invalid_qstash_body"):
        verifier.verify(
            signature=_signature(key=key, body=b'{"task":"expected"}', url=endpoint),
            body=body,
            now=1_800_000_000,
        )


def test_signature_verifier_rejects_a_message_for_another_endpoint() -> None:
    key = "current-signing-key-at-least-32-bytes"
    verifier = QStashSignatureVerifier(
        current_signing_key=key,
        next_signing_key="next-signing-key-at-least-32-bytes---",
        expected_url="https://jobs.example.com/internal/jobs/qstash",
    )
    body = b"{}"

    with pytest.raises(QStashSignatureError, match="invalid_qstash_claims"):
        verifier.verify(
            signature=_signature(
                key=key,
                body=body,
                url="https://other.example.com/internal/jobs/qstash",
            ),
            body=body,
            now=1_800_000_000,
        )
