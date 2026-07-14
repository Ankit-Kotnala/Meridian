"""Deterministic local/test adapters; never selected implicitly in production."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from careeros.modules.identity.application.models import (
    EmailMessage,
    OAuthIdentity,
    OAuthStart,
)
from careeros.modules.identity.domain.errors import OAuthFlowRejected, RateLimited


class FrozenClock:
    def __init__(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("frozen clock requires a timezone-aware datetime")
        self.value = value

    def now(self) -> datetime:
        return self.value


class CapturingEmailSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


class InMemoryAbuseLimiter:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = defaultdict(int)

    async def check(self, action: str, subject: str, limit: int, window_seconds: int) -> None:
        del window_seconds
        key = (action, subject)
        self._counts[key] += 1
        if self._counts[key] > limit:
            raise RateLimited(1)


@dataclass(frozen=True, slots=True)
class FakeOAuthUser:
    subject: str = "google-test-subject"
    email: str = "alex@example.test"
    display_name: str = "Alex Example"
    email_verified: bool = True


class DeterministicGoogleOAuthProvider:
    """Explicit deterministic provider for isolated tests and local acceptance."""

    enabled = True

    def __init__(self, user: FakeOAuthUser | None = None) -> None:
        self.user = user or FakeOAuthUser()
        self._flows: dict[str, tuple[str, UUID | None]] = {}

    async def start(self, return_to: str, link_user_id: UUID | None = None) -> OAuthStart:
        state = f"test-state-{len(self._flows) + 1:04d}-deterministic"
        self._flows[state] = (return_to, link_user_id)
        return OAuthStart(
            authorization_url=f"https://oauth.test/authorize?state={state}",
            state=state,
        )

    async def complete(self, code: str, state: str) -> OAuthIdentity:
        flow = self._flows.pop(state, None)
        if flow is None or code != "test-code":
            raise OAuthFlowRejected
        return_to, link_user_id = flow
        return OAuthIdentity(
            subject=self.user.subject,
            email=self.user.email,
            email_verified=self.user.email_verified,
            display_name=self.user.display_name,
            return_to=return_to,
            link_user_id=link_user_id,
        )


class DisabledGoogleOAuthProvider:
    enabled = False

    async def start(self, return_to: str, link_user_id: UUID | None = None) -> OAuthStart:
        del return_to, link_user_id
        raise OAuthFlowRejected

    async def complete(self, code: str, state: str) -> OAuthIdentity:
        del code, state
        raise OAuthFlowRejected


def utc_test_clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
