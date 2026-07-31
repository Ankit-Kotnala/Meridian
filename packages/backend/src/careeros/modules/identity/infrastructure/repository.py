"""Async SQLAlchemy unit of work for the identity module."""

from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.identity.application.ports import IdentityUnitOfWork
from careeros.modules.identity.domain import (
    AuditEvent,
    AuthMethod,
    ConsentDecision,
    ConsentEvent,
    HandoffStatus,
    OAuthAccount,
    OnboardingProgress,
    OnboardingStatus,
    OnboardingStep,
    Profile,
    RefreshToken,
    Session,
    TokenPurpose,
    User,
    UserStatus,
)
from careeros.modules.identity.domain.errors import IdentityConflict
from careeros.modules.identity.infrastructure.models import (
    AuditEventModel,
    AuthOneTimeTokenModel,
    AuthRefreshTokenModel,
    AuthSessionModel,
    ConsentEventModel,
    OAuthAccountModel,
    OnboardingProgressModel,
    UserModel,
    UserProfileModel,
)


class SqlAlchemyIdentityUnitOfWork:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> "SqlAlchemyIdentityUnitOfWork":
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("identity unit of work is not active")
        return self._session

    async def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None:
        statement = select(UserModel).where(UserModel.id == user_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _user(model) if model is not None else None

    async def get_user_by_email(self, email: str, *, for_update: bool = False) -> User | None:
        statement = select(UserModel).where(UserModel.email_normalized == email)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _user(model) if model is not None else None

    async def add_user(self, user: User) -> None:
        self.session.add(
            UserModel(
                id=user.id,
                email_normalized=user.email_normalized,
                password_hash=user.password_hash,
                status=user.status.value,
                email_verified_at=user.email_verified_at,
                auth_version=user.auth_version,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
        await self._flush()

    async def save_user(self, user: User) -> None:
        await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(
                password_hash=user.password_hash,
                status=user.status.value,
                email_verified_at=user.email_verified_at,
                auth_version=user.auth_version,
                updated_at=user.updated_at,
            )
        )

    async def get_profile(self, user_id: UUID, *, for_update: bool = False) -> Profile | None:
        statement = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _profile(model) if model is not None else None

    async def add_profile(self, profile: Profile) -> None:
        self.session.add(_profile_model(profile))

    async def save_profile(self, profile: Profile) -> None:
        await self.session.execute(
            update(UserProfileModel)
            .where(UserProfileModel.user_id == profile.user_id)
            .values(**_profile_values(profile))
        )

    async def get_session(self, session_id: UUID, *, for_update: bool = False) -> Session | None:
        statement = select(AuthSessionModel).where(AuthSessionModel.id == session_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _session(model) if model is not None else None

    async def add_session(self, session: Session) -> None:
        self.session.add(
            AuthSessionModel(
                id=session.id,
                user_id=session.user_id,
                access_token_hash=session.access_token_hash,
                csrf_token_hash=session.csrf_token_hash,
                auth_method=session.auth_method.value,
                device_label=session.device_label,
                created_at=session.created_at,
                authenticated_at=session.authenticated_at,
                last_seen_at=session.last_seen_at,
                access_expires_at=session.access_expires_at,
                expires_at=session.expires_at,
                revoked_at=session.revoked_at,
            )
        )
        await self._flush()

    async def save_session(self, session: Session) -> None:
        await self.session.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.id == session.id)
            .values(
                access_token_hash=session.access_token_hash,
                csrf_token_hash=session.csrf_token_hash,
                last_seen_at=session.last_seen_at,
                access_expires_at=session.access_expires_at,
                expires_at=session.expires_at,
                revoked_at=session.revoked_at,
            )
        )

    async def list_sessions(self, user_id: UUID) -> list[Session]:
        models = (
            await self.session.scalars(
                select(AuthSessionModel)
                .where(AuthSessionModel.user_id == user_id)
                .order_by(AuthSessionModel.created_at.desc())
                .limit(50)
            )
        ).all()
        return [_session(model) for model in models]

    async def revoke_user_sessions(self, user_id: UUID, revoked_at: datetime) -> None:
        session_ids = select(AuthSessionModel.id).where(AuthSessionModel.user_id == user_id)
        await self.session.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.user_id == user_id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        await self.session.execute(
            update(AuthRefreshTokenModel)
            .where(
                AuthRefreshTokenModel.session_id.in_(session_ids),
                AuthRefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def get_refresh_token(
        self, token_id: UUID, *, for_update: bool = False
    ) -> RefreshToken | None:
        statement = select(AuthRefreshTokenModel).where(AuthRefreshTokenModel.id == token_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _refresh(model) if model is not None else None

    async def add_refresh_token(self, token: RefreshToken) -> None:
        self.session.add(
            AuthRefreshTokenModel(
                id=token.id,
                session_id=token.session_id,
                token_hash=token.token_hash,
                parent_token_id=token.parent_token_id,
                replaced_by_token_id=token.replaced_by_token_id,
                issued_at=token.issued_at,
                expires_at=token.expires_at,
                used_at=token.used_at,
                revoked_at=token.revoked_at,
            )
        )
        await self._flush()

    async def save_refresh_token(self, token: RefreshToken) -> None:
        await self.session.execute(
            update(AuthRefreshTokenModel)
            .where(AuthRefreshTokenModel.id == token.id)
            .values(
                replaced_by_token_id=token.replaced_by_token_id,
                used_at=token.used_at,
                revoked_at=token.revoked_at,
            )
        )

    async def revoke_refresh_family(self, session_id: UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(AuthRefreshTokenModel)
            .where(
                AuthRefreshTokenModel.session_id == session_id,
                AuthRefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def add_one_time_token(
        self,
        token_id: UUID,
        user_id: UUID,
        purpose: TokenPurpose,
        token_hash: bytes,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.session.add(
            AuthOneTimeTokenModel(
                id=token_id,
                user_id=user_id,
                purpose=purpose.value,
                token_hash=token_hash,
                created_at=created_at,
                expires_at=expires_at,
                consumed_at=None,
            )
        )

    async def get_one_time_token(
        self, token_id: UUID, *, for_update: bool = False
    ) -> tuple[UUID, TokenPurpose, bytes, datetime, datetime | None] | None:
        statement = select(AuthOneTimeTokenModel).where(AuthOneTimeTokenModel.id == token_id)
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        if model is None:
            return None
        return (
            model.user_id,
            TokenPurpose(model.purpose),
            model.token_hash,
            model.expires_at,
            model.consumed_at,
        )

    async def consume_one_time_token(self, token_id: UUID, consumed_at: datetime) -> None:
        await self.session.execute(
            update(AuthOneTimeTokenModel)
            .where(AuthOneTimeTokenModel.id == token_id)
            .values(consumed_at=consumed_at)
        )

    async def invalidate_one_time_tokens(
        self, user_id: UUID, purpose: TokenPurpose, consumed_at: datetime
    ) -> None:
        await self.session.execute(
            update(AuthOneTimeTokenModel)
            .where(
                AuthOneTimeTokenModel.user_id == user_id,
                AuthOneTimeTokenModel.purpose == purpose.value,
                AuthOneTimeTokenModel.consumed_at.is_(None),
            )
            .values(consumed_at=consumed_at)
        )

    async def get_oauth_account(self, provider: str, subject: str) -> OAuthAccount | None:
        model = await self.session.scalar(
            select(OAuthAccountModel).where(
                OAuthAccountModel.provider == provider,
                OAuthAccountModel.provider_subject == subject,
            )
        )
        return _oauth(model) if model is not None else None

    async def get_user_oauth_account(self, user_id: UUID, provider: str) -> OAuthAccount | None:
        model = await self.session.scalar(
            select(OAuthAccountModel).where(
                OAuthAccountModel.user_id == user_id,
                OAuthAccountModel.provider == provider,
            )
        )
        return _oauth(model) if model is not None else None

    async def add_oauth_account(self, account: OAuthAccount) -> None:
        self.session.add(
            OAuthAccountModel(
                id=account.id,
                user_id=account.user_id,
                provider=account.provider,
                provider_subject=account.provider_subject,
                provider_email_normalized=account.provider_email_normalized,
                created_at=account.created_at,
                last_login_at=account.last_login_at,
            )
        )

    async def save_oauth_account(self, account: OAuthAccount) -> None:
        await self.session.execute(
            update(OAuthAccountModel)
            .where(OAuthAccountModel.id == account.id)
            .values(
                provider_email_normalized=account.provider_email_normalized,
                last_login_at=account.last_login_at,
            )
        )

    async def delete_oauth_account(self, user_id: UUID, provider: str) -> None:
        await self.session.execute(
            delete(OAuthAccountModel).where(
                OAuthAccountModel.user_id == user_id,
                OAuthAccountModel.provider == provider,
            )
        )

    async def add_consent_event(self, event: ConsentEvent) -> None:
        self.session.add(
            ConsentEventModel(
                id=event.id,
                user_id=event.user_id,
                purpose=event.purpose,
                decision=event.decision.value,
                policy_version=event.policy_version,
                request_id=event.request_id,
                trace_id=event.trace_id,
                recorded_at=event.recorded_at,
            )
        )

    async def list_current_consents(self, user_id: UUID) -> list[ConsentEvent]:
        models = (
            await self.session.scalars(
                select(ConsentEventModel)
                .where(ConsentEventModel.user_id == user_id)
                .order_by(ConsentEventModel.purpose, ConsentEventModel.recorded_at.desc())
            )
        ).all()
        current: dict[str, ConsentEventModel] = {}
        for model in models:
            current.setdefault(model.purpose, model)
        return [_consent(model) for model in current.values()]

    async def add_audit_event(self, event: AuditEvent) -> None:
        self.session.add(
            AuditEventModel(
                id=event.id,
                actor_user_id=event.actor_user_id,
                subject_user_id=event.subject_user_id,
                session_id=event.session_id,
                event_type=event.event_type,
                outcome=event.outcome,
                target_type=event.target_type,
                target_id=event.target_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                metadata_json=event.metadata,
                occurred_at=event.occurred_at,
            )
        )

    async def list_audit_events(self, user_id: UUID, *, limit: int) -> list[AuditEvent]:
        models = (
            await self.session.scalars(
                select(AuditEventModel)
                .where(
                    or_(
                        AuditEventModel.actor_user_id == user_id,
                        AuditEventModel.subject_user_id == user_id,
                    )
                )
                .order_by(
                    AuditEventModel.occurred_at.desc(),
                    AuditEventModel.id.desc(),
                )
                .limit(limit)
            )
        ).all()
        return [_audit_event(model) for model in models]

    async def get_onboarding(
        self, user_id: UUID, *, for_update: bool = False
    ) -> OnboardingProgress | None:
        statement = select(OnboardingProgressModel).where(
            OnboardingProgressModel.user_id == user_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _onboarding(model) if model is not None else None

    async def add_onboarding(self, progress: OnboardingProgress) -> None:
        self.session.add(
            OnboardingProgressModel(
                user_id=progress.user_id,
                status=progress.status.value,
                current_step=progress.current_step.value,
                resume_handoff=progress.resume_handoff.value,
                parsed_review_handoff=progress.parsed_review_handoff.value,
                skipped_steps=[step.value for step in progress.skipped_steps],
                version=progress.version,
                created_at=progress.created_at,
                updated_at=progress.updated_at,
                completed_at=progress.completed_at,
            )
        )

    async def save_onboarding(self, progress: OnboardingProgress) -> None:
        await self.session.execute(
            update(OnboardingProgressModel)
            .where(OnboardingProgressModel.user_id == progress.user_id)
            .values(
                status=progress.status.value,
                current_step=progress.current_step.value,
                resume_handoff=progress.resume_handoff.value,
                parsed_review_handoff=progress.parsed_review_handoff.value,
                skipped_steps=[step.value for step in progress.skipped_steps],
                version=progress.version,
                updated_at=progress.updated_at,
                completed_at=progress.completed_at,
            )
        )

    async def delete_user(self, user_id: UUID) -> bool:
        result = await self.session.execute(delete(UserModel).where(UserModel.id == user_id))
        await self._flush()
        return bool(getattr(result, "rowcount", 0) > 0)

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise IdentityConflict from exc
        self._committed = True

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise IdentityConflict from exc


class SqlAlchemyIdentityUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> IdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(self._database)


def _user(model: UserModel) -> User:
    return User(
        id=model.id,
        email_normalized=model.email_normalized,
        password_hash=model.password_hash,
        status=UserStatus(model.status),
        email_verified_at=model.email_verified_at,
        auth_version=model.auth_version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _profile(model: UserProfileModel) -> Profile:
    return Profile(
        user_id=model.user_id,
        display_name=model.display_name,
        locale=model.locale,
        timezone=model.timezone,
        target_role=model.target_role,
        preferred_location=model.preferred_location,
        work_model=model.work_model,
        seniority=model.seniority,
        industry=model.industry,
        language=model.language,
        writing_style=model.writing_style,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _profile_model(profile: Profile) -> UserProfileModel:
    return UserProfileModel(user_id=profile.user_id, **_profile_values(profile))


def _profile_values(profile: Profile) -> dict[str, object]:
    return {
        "display_name": profile.display_name,
        "locale": profile.locale,
        "timezone": profile.timezone,
        "target_role": profile.target_role,
        "preferred_location": profile.preferred_location,
        "work_model": profile.work_model,
        "seniority": profile.seniority,
        "industry": profile.industry,
        "language": profile.language,
        "writing_style": profile.writing_style,
        "version": profile.version,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _session(model: AuthSessionModel) -> Session:
    return Session(
        id=model.id,
        user_id=model.user_id,
        access_token_hash=model.access_token_hash,
        csrf_token_hash=model.csrf_token_hash,
        auth_method=AuthMethod(model.auth_method),
        device_label=model.device_label,
        created_at=model.created_at,
        authenticated_at=model.authenticated_at,
        last_seen_at=model.last_seen_at,
        access_expires_at=model.access_expires_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
    )


def _refresh(model: AuthRefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=model.id,
        session_id=model.session_id,
        token_hash=model.token_hash,
        parent_token_id=model.parent_token_id,
        replaced_by_token_id=model.replaced_by_token_id,
        issued_at=model.issued_at,
        expires_at=model.expires_at,
        used_at=model.used_at,
        revoked_at=model.revoked_at,
    )


def _oauth(model: OAuthAccountModel) -> OAuthAccount:
    return OAuthAccount(
        id=model.id,
        user_id=model.user_id,
        provider=model.provider,
        provider_subject=model.provider_subject,
        provider_email_normalized=model.provider_email_normalized,
        created_at=model.created_at,
        last_login_at=model.last_login_at,
    )


def _consent(model: ConsentEventModel) -> ConsentEvent:
    return ConsentEvent(
        id=model.id,
        user_id=model.user_id,
        purpose=model.purpose,
        decision=ConsentDecision(model.decision),
        policy_version=model.policy_version,
        request_id=model.request_id,
        trace_id=model.trace_id,
        recorded_at=model.recorded_at,
    )


def _audit_event(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        actor_user_id=model.actor_user_id,
        subject_user_id=model.subject_user_id,
        session_id=model.session_id,
        event_type=model.event_type,
        outcome=model.outcome,
        target_type=model.target_type,
        target_id=model.target_id,
        request_id=model.request_id,
        trace_id=model.trace_id,
        metadata=model.metadata_json,
        occurred_at=model.occurred_at,
    )


def _onboarding(model: OnboardingProgressModel) -> OnboardingProgress:
    return OnboardingProgress(
        user_id=model.user_id,
        status=OnboardingStatus(model.status),
        current_step=OnboardingStep(model.current_step),
        resume_handoff=HandoffStatus(model.resume_handoff),
        parsed_review_handoff=HandoffStatus(model.parsed_review_handoff),
        skipped_steps=tuple(OnboardingStep(value) for value in model.skipped_steps),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
    )
