"""Atomic per-owner admission and accounting for live AI provider usage."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

from redis.asyncio import Redis

from careeros.modules.change_studio.application.models import (
    AiGenerationRequest,
    AiProviderResponse,
)
from careeros.modules.change_studio.application.ports import SuggestionProvider
from careeros.modules.change_studio.domain import (
    ChangeStudioRateLimited,
    ChangeStudioUnavailable,
)

_RESERVE_SCRIPT = """
local rate = redis.call('INCR', KEYS[1])
if rate == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local rate_ttl = math.max(1, redis.call('TTL', KEYS[1]))
if rate > tonumber(ARGV[2]) then return {1, rate_ttl} end

redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', ARGV[3])
local active = redis.call('ZCARD', KEYS[2])
if active >= tonumber(ARGV[4]) then
  local oldest = redis.call('ZRANGE', KEYS[2], 0, 0, 'WITHSCORES')
  local retry = 1
  if oldest[2] then
    retry = math.max(1, math.ceil((tonumber(oldest[2]) - tonumber(ARGV[3])) / 1000))
  end
  return {2, retry}
end

local used_tokens = tonumber(redis.call('HGET', KEYS[3], 'tokens') or '0')
local used_cost = tonumber(redis.call('HGET', KEYS[3], 'cost') or '0')
if used_tokens + tonumber(ARGV[5]) > tonumber(ARGV[6]) then
  return {3, tonumber(ARGV[9])}
end
if used_cost + tonumber(ARGV[7]) > tonumber(ARGV[8]) then
  return {4, tonumber(ARGV[9])}
end

redis.call('ZADD', KEYS[2], ARGV[10], ARGV[11])
redis.call('EXPIRE', KEYS[2], ARGV[12])
redis.call('HINCRBY', KEYS[3], 'tokens', ARGV[5])
redis.call('HINCRBY', KEYS[3], 'cost', ARGV[7])
redis.call('HINCRBY', KEYS[3], 'requests', 1)
redis.call('EXPIRE', KEYS[3], ARGV[9])
return {0, 0}
"""

_SETTLE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
if tonumber(ARGV[2]) == 1 then
  local token_refund = tonumber(ARGV[3]) - tonumber(ARGV[4])
  local cost_refund = tonumber(ARGV[5]) - tonumber(ARGV[6])
  if token_refund > 0 then redis.call('HINCRBY', KEYS[2], 'tokens', -token_refund) end
  if cost_refund > 0 then redis.call('HINCRBY', KEYS[2], 'cost', -cost_refund) end
end
return 1
"""


@dataclass(frozen=True, slots=True)
class AiUsagePolicy:
    """Owner-approved live-provider ceilings; no plan values are inferred."""

    requests_per_window: int
    request_window_seconds: int
    maximum_concurrency: int
    monthly_token_limit: int
    monthly_cost_limit_micros: int
    reservation_tokens: int
    reservation_cost_micros: int
    lease_seconds: int

    def __post_init__(self) -> None:
        if not 1 <= self.requests_per_window <= 10_000:
            raise ValueError("AI request rate limit is invalid")
        if not 60 <= self.request_window_seconds <= 86_400:
            raise ValueError("AI request rate window is invalid")
        if not 1 <= self.maximum_concurrency <= 20:
            raise ValueError("AI concurrency limit is invalid")
        if not 1 <= self.reservation_tokens <= self.monthly_token_limit:
            raise ValueError("AI token reservation or monthly limit is invalid")
        if not 1 <= self.reservation_cost_micros <= self.monthly_cost_limit_micros:
            raise ValueError("AI cost reservation or monthly limit is invalid")
        if not 10 <= self.lease_seconds <= 600:
            raise ValueError("AI usage lease is invalid")


@dataclass(frozen=True, slots=True)
class AiUsageReservation:
    owner_user_id: UUID
    lease_id: str
    period: str


class AiUsageStore(Protocol):
    async def reserve(self, owner_user_id: UUID, policy: AiUsagePolicy) -> AiUsageReservation: ...

    async def settle(
        self,
        reservation: AiUsageReservation,
        policy: AiUsagePolicy,
        *,
        actual_tokens: int,
        actual_cost_micros: int,
        usage_valid: bool,
    ) -> None: ...


class RedisAiUsageStore:
    """Use Redis scripts so rate, concurrency, and budget admission is indivisible."""

    def __init__(self, redis: Redis, *, namespace: str, pepper: str) -> None:
        encoded = pepper.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("AI usage pepper must be at least 32 UTF-8 bytes")
        if not namespace or len(namespace) > 80:
            raise ValueError("AI usage namespace is invalid")
        self._redis = redis
        self._namespace = namespace
        self._pepper = encoded

    async def reserve(self, owner_user_id: UUID, policy: AiUsagePolicy) -> AiUsageReservation:
        now = datetime.now(UTC)
        now_millis = int(now.timestamp() * 1000)
        period = now.strftime("%Y%m")
        lease_id = secrets.token_urlsafe(24)
        budget_ttl = _period_ttl_seconds(now)
        lease_expiry = now_millis + policy.lease_seconds * 1000
        owner_key = self._owner_key(owner_user_id)
        keys = (
            f"{self._namespace}:rate:{owner_key}",
            f"{self._namespace}:inflight:{owner_key}",
            f"{self._namespace}:usage:{period}:{owner_key}",
        )
        try:
            evaluation = cast(
                Awaitable[list[int | bytes | str]],
                self._redis.eval(
                    _RESERVE_SCRIPT,
                    len(keys),
                    *keys,
                    str(policy.request_window_seconds),
                    str(policy.requests_per_window),
                    str(now_millis),
                    str(policy.maximum_concurrency),
                    str(policy.reservation_tokens),
                    str(policy.monthly_token_limit),
                    str(policy.reservation_cost_micros),
                    str(policy.monthly_cost_limit_micros),
                    str(budget_ttl),
                    str(lease_expiry),
                    lease_id,
                    str(policy.lease_seconds * 2),
                ),
            )
            result = await evaluation
        except Exception as exc:
            raise ChangeStudioUnavailable("AI usage admission is unavailable") from exc
        code, retry_after = int(result[0]), max(1, int(result[1]))
        if code != 0:
            raise ChangeStudioRateLimited(retry_after)
        return AiUsageReservation(
            owner_user_id=owner_user_id,
            lease_id=lease_id,
            period=period,
        )

    async def settle(
        self,
        reservation: AiUsageReservation,
        policy: AiUsagePolicy,
        *,
        actual_tokens: int,
        actual_cost_micros: int,
        usage_valid: bool,
    ) -> None:
        owner_key = self._owner_key(reservation.owner_user_id)
        keys = (
            f"{self._namespace}:inflight:{owner_key}",
            f"{self._namespace}:usage:{reservation.period}:{owner_key}",
        )
        try:
            evaluation = cast(
                Awaitable[int | bytes | str],
                self._redis.eval(
                    _SETTLE_SCRIPT,
                    len(keys),
                    *keys,
                    reservation.lease_id,
                    "1" if usage_valid else "0",
                    str(policy.reservation_tokens),
                    str(actual_tokens),
                    str(policy.reservation_cost_micros),
                    str(actual_cost_micros),
                ),
            )
            await evaluation
        except Exception as exc:
            raise ChangeStudioUnavailable("AI usage settlement is unavailable") from exc

    async def ping(self) -> None:
        await self._redis.ping()

    async def dispose(self) -> None:
        await self._redis.aclose()

    def _owner_key(self, owner_user_id: UUID) -> str:
        return hmac.new(
            self._pepper,
            b"careeros:ai-usage:owner:v1:" + owner_user_id.bytes,
            hashlib.sha256,
        ).hexdigest()


class BudgetedSuggestionProvider:
    """Reserve worst-case usage before a live call and settle only valid usage."""

    def __init__(
        self,
        provider: SuggestionProvider,
        store: AiUsageStore,
        policy: AiUsagePolicy,
    ) -> None:
        self._provider = provider
        self._store = store
        self._policy = policy

    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse:
        reservation = await self._store.reserve(request.owner_user_id, self._policy)
        try:
            response = await self._provider.generate(request)
        except Exception:
            await self._store.settle(
                reservation,
                self._policy,
                actual_tokens=self._policy.reservation_tokens,
                actual_cost_micros=self._policy.reservation_cost_micros,
                usage_valid=False,
            )
            raise
        usage = _validated_usage(response)
        if usage is None:
            await self._store.settle(
                reservation,
                self._policy,
                actual_tokens=self._policy.reservation_tokens,
                actual_cost_micros=self._policy.reservation_cost_micros,
                usage_valid=False,
            )
            raise ChangeStudioUnavailable("AI provider usage was absent or outside reservation")
        tokens, cost_micros = usage
        if (
            tokens > self._policy.reservation_tokens
            or cost_micros > self._policy.reservation_cost_micros
        ):
            await self._store.settle(
                reservation,
                self._policy,
                actual_tokens=self._policy.reservation_tokens,
                actual_cost_micros=self._policy.reservation_cost_micros,
                usage_valid=False,
            )
            raise ChangeStudioUnavailable("AI provider usage was absent or outside reservation")
        await self._store.settle(
            reservation,
            self._policy,
            actual_tokens=tokens,
            actual_cost_micros=cost_micros,
            usage_valid=True,
        )
        return response


def _validated_usage(response: AiProviderResponse) -> tuple[int, int] | None:
    usage = response.payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("promptTokens")
    completion = usage.get("completionTokens")
    cost = usage.get("costMicros")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (prompt, completion, cost)
    ):
        return None
    return cast(int, prompt) + cast(int, completion), cast(int, cost)


def _period_ttl_seconds(now: datetime) -> int:
    if now.month == 12:
        next_period = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_period = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return max(1, int((next_period - now).total_seconds()))
