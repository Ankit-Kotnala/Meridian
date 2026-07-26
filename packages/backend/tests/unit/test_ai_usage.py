"""AI usage reservation and settlement behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from careeros.modules.change_studio.application import (
    AiGenerationRequest,
    AiProviderResponse,
)
from careeros.modules.change_studio.domain import ChangeStudioUnavailable
from careeros.modules.change_studio.infrastructure.usage import (
    AiUsagePolicy,
    AiUsageReservation,
    BudgetedSuggestionProvider,
)


class _Store:
    def __init__(self) -> None:
        self.reservation = AiUsageReservation(uuid4(), "lease", "202607")
        self.settlements: list[tuple[int, int, bool]] = []

    async def reserve(self, owner_user_id: UUID, policy: AiUsagePolicy) -> AiUsageReservation:
        del policy
        self.reservation = AiUsageReservation(
            owner_user_id,
            "lease",
            "202607",
        )
        return self.reservation

    async def settle(
        self,
        reservation: AiUsageReservation,
        policy: AiUsagePolicy,
        *,
        actual_tokens: int,
        actual_cost_micros: int,
        usage_valid: bool,
    ) -> None:
        del reservation, policy
        self.settlements.append((actual_tokens, actual_cost_micros, usage_valid))


class _Provider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def generate(self, request: AiGenerationRequest) -> AiProviderResponse:
        del request
        return AiProviderResponse("provider", "model", 1, self.payload)


def _policy() -> AiUsagePolicy:
    return AiUsagePolicy(
        requests_per_window=5,
        request_window_seconds=60,
        maximum_concurrency=1,
        monthly_token_limit=1_000,
        monthly_cost_limit_micros=1_000,
        reservation_tokens=100,
        reservation_cost_micros=100,
        lease_seconds=30,
    )


def _request() -> AiGenerationRequest:
    return cast(AiGenerationRequest, SimpleNamespace(owner_user_id=uuid4()))


@pytest.mark.asyncio
async def test_valid_usage_releases_the_unused_reservation() -> None:
    store = _Store()
    provider = BudgetedSuggestionProvider(
        _Provider(
            {
                "usage": {
                    "promptTokens": 12,
                    "completionTokens": 8,
                    "costMicros": 30,
                }
            }
        ),
        store,
        _policy(),
    )

    await provider.generate(_request())

    assert store.settlements == [(20, 30, True)]


@pytest.mark.asyncio
async def test_missing_or_over_reservation_usage_retains_the_full_reservation() -> None:
    store = _Store()
    provider = BudgetedSuggestionProvider(
        _Provider(
            {
                "usage": {
                    "promptTokens": 101,
                    "completionTokens": 0,
                    "costMicros": 1,
                }
            }
        ),
        store,
        _policy(),
    )

    with pytest.raises(ChangeStudioUnavailable):
        await provider.generate(_request())

    assert store.settlements == [(100, 100, False)]


def test_policy_rejects_reservations_larger_than_monthly_limits() -> None:
    with pytest.raises(ValueError):
        AiUsagePolicy(
            requests_per_window=5,
            request_window_seconds=60,
            maximum_concurrency=1,
            monthly_token_limit=99,
            monthly_cost_limit_micros=1_000,
            reservation_tokens=100,
            reservation_cost_micros=100,
            lease_seconds=30,
        )
