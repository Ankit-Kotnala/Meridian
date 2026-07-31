"""Platform request admission and response-header regressions."""

from unittest.mock import create_autospec

from careeros.modules.identity.domain.errors import RateLimited
from careeros.modules.identity.infrastructure.redis_security import RedisSecurityStore
from fastapi.testclient import TestClient

from careeros_api.application import create_app
from careeros_api.config import Settings
from conftest import FakeDatabase


def _settings(**updates: object) -> Settings:
    return Settings.model_validate(
        {
            "environment": "test",
            "trusted_hosts": ["testserver"],
            **updates,
        }
    )


def test_platform_limiter_uses_coarse_read_and_mutation_buckets() -> None:
    limiter = create_autospec(RedisSecurityStore, instance=True)
    settings = _settings(api_read_rate_limit=77, api_mutation_rate_limit=33)

    with TestClient(
        create_app(
            settings,
            database=FakeDatabase(),
            request_limiter=limiter,
        )
    ) as client:
        assert client.get("/api/v1/meta").status_code == 200
        assert client.post("/api/v1/unknown").status_code == 404

    calls = limiter.check.await_args_list
    assert calls[0].args[0] == "platform_api_read"
    assert calls[0].args[2:] == (77, 60)
    assert calls[1].args[0] == "platform_api_mutation"
    assert calls[1].args[2:] == (33, 60)
    assert calls[0].args[1].startswith("development-peer:")


def test_platform_rate_rejection_is_safe_and_retryable() -> None:
    limiter = create_autospec(RedisSecurityStore, instance=True)
    limiter.check.side_effect = RateLimited(17)

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            request_limiter=limiter,
        )
    ) as client:
        response = client.get("/api/v1/meta")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "17"
    assert response.json()["code"] == "rate_limited"


def test_api_responses_receive_deny_by_default_browser_headers() -> None:
    with TestClient(create_app(_settings(), database=FakeDatabase())) as client:
        response = client.get("/api/v1/meta")
        health = client.get("/health")

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"].startswith("camera=()")
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" not in health.headers
