"""Redis-backed atomic authentication abuse controls and OAuth flow storage."""

import hashlib
import hmac
import json
from collections.abc import Awaitable
from typing import Any, cast

from redis.asyncio import Redis

from careeros.modules.identity.domain.errors import OAuthFlowRejected, RateLimited

_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""

_GET_DELETE_SCRIPT = """
local value = redis.call('GET', KEYS[1])
if value then redis.call('DEL', KEYS[1]) end
return value
"""


class RedisSecurityStore:
    def __init__(self, redis: Redis, namespace: str, pepper: str) -> None:
        self._redis = redis
        self._namespace = namespace
        self._pepper = pepper.encode("utf-8")

    async def check(self, action: str, subject: str, limit: int, window_seconds: int) -> None:
        key = self._key("limit", action, subject)
        evaluation = cast(
            Awaitable[list[int | bytes | str]],
            self._redis.eval(_LIMIT_SCRIPT, 1, key, str(window_seconds)),
        )
        result = await evaluation
        current, ttl = int(result[0]), max(1, int(result[1]))
        if current > limit:
            raise RateLimited(ttl)

    async def save_oauth_flow(self, state: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        key = self._key("oauth", state)
        await self._redis.set(
            key, json.dumps(payload, separators=(",", ":")), ex=ttl_seconds, nx=True
        )

    async def consume_oauth_flow(self, state: str) -> dict[str, Any]:
        key = self._key("oauth", state)
        raw = await cast(Awaitable[bytes | None], self._redis.eval(_GET_DELETE_SCRIPT, 1, key))
        if raw is None:
            raise OAuthFlowRejected
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise OAuthFlowRejected
        return value

    async def ping(self) -> None:
        await self._redis.ping()

    async def dispose(self) -> None:
        await self._redis.aclose()

    def _key(self, category: str, *values: str) -> str:
        material = "\x1f".join(values).encode("utf-8")
        digest = hmac.new(self._pepper, material, hashlib.sha256).hexdigest()
        return f"{self._namespace}:{category}:{digest}"
