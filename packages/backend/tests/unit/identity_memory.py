"""Small transactional-port fake used to exercise identity policy without infrastructure."""

from datetime import datetime
from types import TracebackType
from uuid import UUID

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


class MemoryIdentityUnitOfWork:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.profiles: dict[UUID, Profile] = {}
        self.sessions: dict[UUID, Session] = {}
        self.refresh_tokens: dict[UUID, RefreshToken] = {}
        self.one_time_tokens: dict[
            UUID, tuple[UUID, TokenPurpose, bytes, datetime, datetime, datetime | None]
        ] = {}
        self.oauth_accounts: dict[UUID, OAuthAccount] = {}
        self.consents: list[ConsentEvent] = []
        self.audit_events: list[AuditEvent] = []
        self.onboarding: dict[UUID, OnboardingProgress] = {}
        self.commits = 0

    async def __aenter__(self) -> "MemoryIdentityUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None:
        del for_update
        return self.users.get(user_id)

    async def get_user_by_email(self, email: str, *, for_update: bool = False) -> User | None:
        del for_update
        return next((user for user in self.users.values() if user.email_normalized == email), None)

    async def add_user(self, user: User) -> None:
        self.users[user.id] = user

    async def save_user(self, user: User) -> None:
        self.users[user.id] = user

    async def get_profile(self, user_id: UUID, *, for_update: bool = False) -> Profile | None:
        del for_update
        return self.profiles.get(user_id)

    async def add_profile(self, profile: Profile) -> None:
        self.profiles[profile.user_id] = profile

    async def save_profile(self, profile: Profile) -> None:
        self.profiles[profile.user_id] = profile

    async def get_session(self, session_id: UUID, *, for_update: bool = False) -> Session | None:
        del for_update
        return self.sessions.get(session_id)

    async def add_session(self, session: Session) -> None:
        self.sessions[session.id] = session

    async def save_session(self, session: Session) -> None:
        self.sessions[session.id] = session

    async def list_sessions(self, user_id: UUID) -> list[Session]:
        return [session for session in self.sessions.values() if session.user_id == user_id]

    async def revoke_user_sessions(self, user_id: UUID, revoked_at: datetime) -> None:
        for session in self.sessions.values():
            if session.user_id == user_id and session.revoked_at is None:
                session.revoked_at = revoked_at
                await self.revoke_refresh_family(session.id, revoked_at)

    async def get_refresh_token(
        self, token_id: UUID, *, for_update: bool = False
    ) -> RefreshToken | None:
        del for_update
        return self.refresh_tokens.get(token_id)

    async def add_refresh_token(self, token: RefreshToken) -> None:
        self.refresh_tokens[token.id] = token

    async def save_refresh_token(self, token: RefreshToken) -> None:
        self.refresh_tokens[token.id] = token

    async def revoke_refresh_family(self, session_id: UUID, revoked_at: datetime) -> None:
        for token in self.refresh_tokens.values():
            if token.session_id == session_id and token.revoked_at is None:
                token.revoked_at = revoked_at

    async def add_one_time_token(
        self,
        token_id: UUID,
        user_id: UUID,
        purpose: TokenPurpose,
        token_hash: bytes,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.one_time_tokens[token_id] = (
            user_id,
            purpose,
            token_hash,
            created_at,
            expires_at,
            None,
        )

    async def get_one_time_token(
        self, token_id: UUID, *, for_update: bool = False
    ) -> tuple[UUID, TokenPurpose, bytes, datetime, datetime | None] | None:
        del for_update
        record = self.one_time_tokens.get(token_id)
        if record is None:
            return None
        user_id, purpose, token_hash, _created_at, expires_at, consumed_at = record
        return user_id, purpose, token_hash, expires_at, consumed_at

    async def consume_one_time_token(self, token_id: UUID, consumed_at: datetime) -> None:
        user_id, purpose, token_hash, created_at, expires_at, _ = self.one_time_tokens[token_id]
        self.one_time_tokens[token_id] = (
            user_id,
            purpose,
            token_hash,
            created_at,
            expires_at,
            consumed_at,
        )

    async def invalidate_one_time_tokens(
        self, user_id: UUID, purpose: TokenPurpose, consumed_at: datetime
    ) -> None:
        for token_id, record in list(self.one_time_tokens.items()):
            owner, record_purpose, token_hash, created_at, expires_at, consumed = record
            if owner == user_id and record_purpose is purpose and consumed is None:
                self.one_time_tokens[token_id] = (
                    owner,
                    record_purpose,
                    token_hash,
                    created_at,
                    expires_at,
                    consumed_at,
                )

    async def get_oauth_account(self, provider: str, subject: str) -> OAuthAccount | None:
        return next(
            (
                account
                for account in self.oauth_accounts.values()
                if account.provider == provider and account.provider_subject == subject
            ),
            None,
        )

    async def get_user_oauth_account(self, user_id: UUID, provider: str) -> OAuthAccount | None:
        return next(
            (
                account
                for account in self.oauth_accounts.values()
                if account.user_id == user_id and account.provider == provider
            ),
            None,
        )

    async def add_oauth_account(self, account: OAuthAccount) -> None:
        self.oauth_accounts[account.id] = account

    async def save_oauth_account(self, account: OAuthAccount) -> None:
        self.oauth_accounts[account.id] = account

    async def delete_oauth_account(self, user_id: UUID, provider: str) -> None:
        for account_id, account in list(self.oauth_accounts.items()):
            if account.user_id == user_id and account.provider == provider:
                del self.oauth_accounts[account_id]

    async def add_consent_event(self, event: ConsentEvent) -> None:
        self.consents.append(event)

    async def list_current_consents(self, user_id: UUID) -> list[ConsentEvent]:
        current: dict[str, ConsentEvent] = {}
        for event in reversed(self.consents):
            if event.user_id == user_id:
                current.setdefault(event.purpose, event)
        return list(current.values())

    async def add_audit_event(self, event: AuditEvent) -> None:
        self.audit_events.append(event)

    async def list_audit_events(self, user_id: UUID, *, limit: int) -> list[AuditEvent]:
        return [
            event
            for event in reversed(self.audit_events)
            if event.actor_user_id == user_id or event.subject_user_id == user_id
        ][:limit]

    async def get_onboarding(
        self, user_id: UUID, *, for_update: bool = False
    ) -> OnboardingProgress | None:
        del for_update
        return self.onboarding.get(user_id)

    async def add_onboarding(self, progress: OnboardingProgress) -> None:
        self.onboarding[progress.user_id] = progress

    async def save_onboarding(self, progress: OnboardingProgress) -> None:
        self.onboarding[progress.user_id] = progress

    async def commit(self) -> None:
        self.commits += 1


class MemoryIdentityUnitOfWorkFactory:
    def __init__(self, store: MemoryIdentityUnitOfWork) -> None:
        self.store = store

    def __call__(self) -> MemoryIdentityUnitOfWork:
        return self.store
