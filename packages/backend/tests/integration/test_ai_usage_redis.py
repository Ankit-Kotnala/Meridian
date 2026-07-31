"""Live Redis proof for atomic AI rate, concurrency, and monthly budgets."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from careeros.modules.change_studio.domain import ChangeStudioRateLimited
from careeros.modules.change_studio.infrastructure.usage import (
    AiUsagePolicy,
    RedisAiUsageStore,
)


def _redis_url() -> str:
    value = os.environ.get("CAREEROS_TEST_REDIS_URL")
    if value is None:
        pytest.skip("CAREEROS_TEST_REDIS_URL is required")
    return value


@pytest.mark.asyncio
async def test_atomic_usage_admission_enforces_concurrency_rate_and_budget() -> None:
    namespace = f"careeros:test:ai-usage:{uuid4().hex}"
    redis = Redis.from_url(_redis_url(), decode_responses=False)
    store = RedisAiUsageStore(
        redis,
        namespace=namespace,
        pepper="fictional-ai-usage-test-pepper-at-least-32-bytes",
    )
    concurrency_policy = AiUsagePolicy(
        requests_per_window=10,
        request_window_seconds=60,
        maximum_concurrency=1,
        monthly_token_limit=100,
        monthly_cost_limit_micros=100,
        reservation_tokens=20,
        reservation_cost_micros=20,
        lease_seconds=30,
    )
    owner = uuid4()
    try:
        reservation = await store.reserve(owner, concurrency_policy)
        with pytest.raises(ChangeStudioRateLimited):
            await store.reserve(owner, concurrency_policy)
        await store.settle(
            reservation,
            concurrency_policy,
            actual_tokens=10,
            actual_cost_micros=5,
            usage_valid=True,
        )
        second = await store.reserve(owner, concurrency_policy)
        await store.settle(
            second,
            concurrency_policy,
            actual_tokens=20,
            actual_cost_micros=20,
            usage_valid=True,
        )

        rate_policy = AiUsagePolicy(
            requests_per_window=1,
            request_window_seconds=60,
            maximum_concurrency=1,
            monthly_token_limit=100,
            monthly_cost_limit_micros=100,
            reservation_tokens=10,
            reservation_cost_micros=10,
            lease_seconds=30,
        )
        rate_owner = uuid4()
        rate_reservation = await store.reserve(rate_owner, rate_policy)
        await store.settle(
            rate_reservation,
            rate_policy,
            actual_tokens=1,
            actual_cost_micros=1,
            usage_valid=True,
        )
        with pytest.raises(ChangeStudioRateLimited):
            await store.reserve(rate_owner, rate_policy)

        budget_policy = AiUsagePolicy(
            requests_per_window=10,
            request_window_seconds=60,
            maximum_concurrency=1,
            monthly_token_limit=20,
            monthly_cost_limit_micros=20,
            reservation_tokens=20,
            reservation_cost_micros=20,
            lease_seconds=30,
        )
        budget_owner = uuid4()
        budget_reservation = await store.reserve(budget_owner, budget_policy)
        await store.settle(
            budget_reservation,
            budget_policy,
            actual_tokens=20,
            actual_cost_micros=20,
            usage_valid=True,
        )
        with pytest.raises(ChangeStudioRateLimited):
            await store.reserve(budget_owner, budget_policy)
    finally:
        keys = [key async for key in redis.scan_iter(match=f"{namespace}:*")]
        if keys:
            await redis.delete(*keys)
        await store.dispose()
