"""Redis integration coverage for atomic abuse limits and one-use OAuth state."""

import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from careeros.modules.identity.domain.errors import OAuthFlowRejected, RateLimited
from careeros.modules.identity.infrastructure.redis_security import RedisSecurityStore


@pytest.mark.asyncio
async def test_redis_limits_are_atomic_and_oauth_state_is_single_use() -> None:
    redis_url = os.environ.get("CAREEROS_TEST_REDIS_URL")
    if redis_url is None:
        pytest.skip("CAREEROS_TEST_REDIS_URL is required for Redis integration tests")

    namespace = f"careeros:test:{uuid4().hex}"
    redis = Redis.from_url(redis_url, decode_responses=False)
    store = RedisSecurityStore(
        redis,
        namespace,
        "integration-pepper-that-is-longer-than-thirty-two-bytes",
    )
    subject = "private-user@example.com"
    try:
        await store.check("login", subject, 2, 60)
        await store.check("login", subject, 2, 60)
        with pytest.raises(RateLimited) as limited:
            await store.check("login", subject, 2, 60)
        assert limited.value.retry_after_seconds > 0

        await store.save_oauth_flow(
            "opaque-state",
            {"nonce": "one", "return_to": "/dashboard"},
            60,
        )
        assert await store.consume_oauth_flow("opaque-state") == {
            "nonce": "one",
            "return_to": "/dashboard",
        }
        with pytest.raises(OAuthFlowRejected):
            await store.consume_oauth_flow("opaque-state")

        keys = await redis.keys(f"{namespace}:*")
        assert keys
        assert subject.encode() not in b"".join(keys)
        if keys:
            await redis.delete(*keys)
    finally:
        await store.dispose()
