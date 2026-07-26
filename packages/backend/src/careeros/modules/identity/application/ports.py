"""Inward-facing ports implemented by identity infrastructure and providers."""

from collections.abc import AsyncIterator
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.identity.application.models import (
    EmailMessage,
    IssuedToken,
    OAuthIdentity,
    OAuthStart,
    OnboardingResumeObservation,
)
from careeros.modules.identity.domain import (
    AuditEvent,
    ConsentEvent,
    OAuthAccount,
    OnboardingProgress,
    Profile,
    RefreshToken,
    Session,
    TokenPurpose,
    User,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password_hash: str, password: str) -> bool: ...

    async def verify_dummy(self, password: str) -> None: ...


class TokenManager(Protocol):
    def issue(self) -> IssuedToken: ...

    def issue_for_id(self, token_id: UUID) -> IssuedToken: ...

    def digest(self, secret: str) -> bytes: ...

    def parse(self, encoded: str) -> tuple[UUID, str] | None: ...

    def verify(self, expected: bytes, secret: str) -> bool: ...


class EmailNormalizer(Protocol):
    def normalize(self, value: str) -> str: ...


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class AbuseLimiter(Protocol):
    async def check(self, action: str, subject: str, limit: int, window_seconds: int) -> None: ...


class GoogleOAuthProvider(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def start(self, return_to: str, link_user_id: UUID | None = None) -> OAuthStart: ...

    async def complete(self, code: str, state: str) -> OAuthIdentity: ...


class OnboardingResumeSource(Protocol):
    """Read-only application boundary for an owner's latest Resume Health state."""

    async def observe(self, owner_user_id: UUID) -> OnboardingResumeObservation: ...


class IdentityUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None: ...

    async def get_user_by_email(self, email: str, *, for_update: bool = False) -> User | None: ...

    async def add_user(self, user: User) -> None: ...

    async def save_user(self, user: User) -> None: ...

    async def get_profile(self, user_id: UUID, *, for_update: bool = False) -> Profile | None: ...

    async def add_profile(self, profile: Profile) -> None: ...

    async def save_profile(self, profile: Profile) -> None: ...

    async def get_session(
        self, session_id: UUID, *, for_update: bool = False
    ) -> Session | None: ...

    async def add_session(self, session: Session) -> None: ...

    async def save_session(self, session: Session) -> None: ...

    async def list_sessions(self, user_id: UUID) -> list[Session]: ...

    async def revoke_user_sessions(self, user_id: UUID, revoked_at: datetime) -> None: ...

    async def get_refresh_token(
        self, token_id: UUID, *, for_update: bool = False
    ) -> RefreshToken | None: ...

    async def add_refresh_token(self, token: RefreshToken) -> None: ...

    async def save_refresh_token(self, token: RefreshToken) -> None: ...

    async def revoke_refresh_family(self, session_id: UUID, revoked_at: datetime) -> None: ...

    async def add_one_time_token(
        self,
        token_id: UUID,
        user_id: UUID,
        purpose: TokenPurpose,
        token_hash: bytes,
        created_at: datetime,
        expires_at: datetime,
    ) -> None: ...

    async def get_one_time_token(
        self, token_id: UUID, *, for_update: bool = False
    ) -> tuple[UUID, TokenPurpose, bytes, datetime, datetime | None] | None: ...

    async def consume_one_time_token(self, token_id: UUID, consumed_at: datetime) -> None: ...

    async def invalidate_one_time_tokens(
        self, user_id: UUID, purpose: TokenPurpose, consumed_at: datetime
    ) -> None: ...

    async def get_oauth_account(self, provider: str, subject: str) -> OAuthAccount | None: ...

    async def get_user_oauth_account(self, user_id: UUID, provider: str) -> OAuthAccount | None: ...

    async def add_oauth_account(self, account: OAuthAccount) -> None: ...

    async def save_oauth_account(self, account: OAuthAccount) -> None: ...

    async def delete_oauth_account(self, user_id: UUID, provider: str) -> None: ...

    async def add_consent_event(self, event: ConsentEvent) -> None: ...

    async def list_current_consents(self, user_id: UUID) -> list[ConsentEvent]: ...

    async def add_audit_event(self, event: AuditEvent) -> None: ...

    async def list_audit_events(self, user_id: UUID, *, limit: int) -> list[AuditEvent]: ...

    async def get_onboarding(
        self, user_id: UUID, *, for_update: bool = False
    ) -> OnboardingProgress | None: ...

    async def add_onboarding(self, progress: OnboardingProgress) -> None: ...

    async def save_onboarding(self, progress: OnboardingProgress) -> None: ...

    async def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> IdentityUnitOfWork: ...


class AsyncSessionProvider(Protocol):
    def session(self) -> AsyncIterator[object]: ...
