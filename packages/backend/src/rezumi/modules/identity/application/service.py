"""Identity application service coordinating policy and persistence ports."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from uuid import UUID, uuid4

from rezumi.modules.identity.application.models import (
    AccountSecurityView,
    ConsentView,
    CurrentUser,
    EmailMessage,
    IssuedSession,
    OAuthCompletion,
    OAuthStart,
    OnboardingResumeObservation,
    OnboardingView,
    RequestContext,
    SecurityActivityView,
    SessionSummary,
)
from rezumi.modules.identity.application.ports import (
    AbuseLimiter,
    Clock,
    EmailNormalizer,
    EmailSender,
    GoogleOAuthProvider,
    IdentityUnitOfWork,
    OnboardingResumeSource,
    PasswordHasher,
    TokenManager,
    UnitOfWorkFactory,
)
from rezumi.modules.identity.domain import (
    AuditEvent,
    AuthenticatedPrincipal,
    AuthMethod,
    ConsentDecision,
    ConsentEvent,
    HandoffStatus,
    OAuthAccount,
    ObservedResumeStatus,
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
from rezumi.modules.identity.domain.errors import (
    AuthenticationRequired,
    CsrfRejected,
    CurrentPasswordRejected,
    EmailVerificationRequired,
    IdentityConflict,
    InvalidCredentials,
    InvalidOrExpiredToken,
    OAuthCollision,
    OAuthFlowRejected,
    OAuthUnavailable,
    RecentAuthenticationRequired,
    ResourceNotFound,
    VersionConflict,
)


@dataclass(frozen=True, slots=True)
class IdentityPolicy:
    public_app_url: str
    access_ttl_seconds: int = 900
    refresh_ttl_seconds: int = 2_592_000
    verification_ttl_seconds: int = 86_400
    reset_ttl_seconds: int = 3_600
    recent_auth_ttl_seconds: int = 600
    rate_limit_window_seconds: int = 300
    consent_policy_version: str = "2026-07-15"


class IdentityService:
    """Execute identity use cases without depending on HTTP or SQLAlchemy."""

    def __init__(
        self,
        *,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        passwords: PasswordHasher,
        tokens: TokenManager,
        emails: EmailSender,
        email_normalizer: EmailNormalizer,
        limiter: AbuseLimiter,
        google: GoogleOAuthProvider,
        policy: IdentityPolicy,
        onboarding_resume_source: OnboardingResumeSource | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._passwords = passwords
        self._tokens = tokens
        self._emails = emails
        self._email_normalizer = email_normalizer
        self._limiter = limiter
        self._google = google
        self._policy = policy
        self._onboarding_resume_source = onboarding_resume_source

    def set_onboarding_resume_source(self, source: OnboardingResumeSource) -> None:
        """Complete application composition after Resume Health is available."""

        self._onboarding_resume_source = source

    def issue_pre_auth_csrf(self) -> str:
        """Issue an unprivileged double-submit nonce for pre-authentication forms."""
        return self._tokens.issue().encoded

    def validate_pre_auth_csrf(self, csrf_token: str) -> None:
        if self._tokens.parse(csrf_token) is None:
            raise CsrfRejected

    async def register(
        self, email: str, password: str, display_name: str, context: RequestContext
    ) -> None:
        normalized = self._email_normalizer.normalize(email)
        await self._limit("register", normalized, 5, context)
        password_hash = await self._passwords.hash(password)
        now = self._clock.now()
        delivery: EmailMessage | None = None

        try:
            async with self._uow() as uow:
                user = await uow.get_user_by_email(normalized, for_update=True)
                if user is None:
                    user = User(
                        id=uuid4(),
                        email_normalized=normalized,
                        password_hash=password_hash,
                        status=UserStatus.PENDING,
                        email_verified_at=None,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    await uow.add_user(user)
                    await uow.add_profile(self._new_profile(user.id, display_name, now))
                    await uow.add_onboarding(self._new_onboarding(user.id, now))
                    delivery = await self._issue_email_token(
                        uow, user, TokenPurpose.VERIFY_EMAIL, now
                    )
                    await self._audit(
                        uow,
                        "auth.registration.accepted",
                        "success",
                        context,
                        subject_user_id=user.id,
                    )
                elif user.status is UserStatus.PENDING:
                    delivery = await self._issue_email_token(
                        uow, user, TokenPurpose.VERIFY_EMAIL, now
                    )
                    await self._audit(
                        uow,
                        "auth.registration.existing_pending",
                        "accepted",
                        context,
                        subject_user_id=user.id,
                    )
                else:
                    await self._audit(
                        uow,
                        "auth.registration.existing",
                        "accepted",
                        context,
                        subject_user_id=user.id,
                    )
                await uow.commit()
        except IdentityConflict:
            # A concurrent registration must remain indistinguishable from an existing account.
            return

        if delivery is not None:
            await self._send_enumeration_safe(delivery)

    async def verify_email(self, encoded_token: str, context: RequestContext) -> None:
        now = self._clock.now()
        parsed = self._tokens.parse(encoded_token)
        if parsed is None:
            raise InvalidOrExpiredToken
        token_id, secret = parsed

        async with self._uow() as uow:
            record = await uow.get_one_time_token(token_id, for_update=True)
            if record is None:
                raise InvalidOrExpiredToken
            user_id, purpose, digest, expires_at, consumed_at = record
            if (
                purpose is not TokenPurpose.VERIFY_EMAIL
                or consumed_at is not None
                or expires_at <= now
                or not self._tokens.verify(digest, secret)
            ):
                raise InvalidOrExpiredToken
            user = await uow.get_user(user_id, for_update=True)
            if user is None or user.status is UserStatus.DISABLED:
                raise InvalidOrExpiredToken
            await uow.consume_one_time_token(token_id, now)
            user.email_verified_at = now
            user.status = UserStatus.ACTIVE
            user.updated_at = now
            await uow.save_user(user)
            await self._audit(
                uow,
                "auth.email_verified",
                "success",
                context,
                subject_user_id=user.id,
            )
            await uow.commit()

    async def resend_verification(self, email: str, context: RequestContext) -> None:
        normalized = self._email_normalizer.normalize(email)
        await self._limit("resend_verification", normalized, 3, context)
        now = self._clock.now()
        delivery: EmailMessage | None = None
        async with self._uow() as uow:
            user = await uow.get_user_by_email(normalized, for_update=True)
            if user is not None and user.status is UserStatus.PENDING:
                delivery = await self._issue_email_token(uow, user, TokenPurpose.VERIFY_EMAIL, now)
                await self._audit(
                    uow,
                    "auth.verification_resent",
                    "accepted",
                    context,
                    subject_user_id=user.id,
                )
            await uow.commit()
        if delivery is not None:
            await self._send_enumeration_safe(delivery)

    async def login(self, email: str, password: str, context: RequestContext) -> IssuedSession:
        normalized = self._email_normalizer.normalize(email)
        await self._limit("login", normalized, 10, context)
        now = self._clock.now()
        async with self._uow() as uow:
            user = await uow.get_user_by_email(normalized, for_update=True)
            if user is None or user.password_hash is None:
                await self._passwords.verify_dummy(password)
                raise InvalidCredentials
            valid = await self._passwords.verify(user.password_hash, password)
            if not valid or user.status is UserStatus.DISABLED:
                await self._audit(
                    uow,
                    "auth.login",
                    "denied",
                    context,
                    subject_user_id=user.id,
                )
                await uow.commit()
                raise InvalidCredentials
            if user.status is UserStatus.PENDING or user.email_verified_at is None:
                raise EmailVerificationRequired
            issued = await self._create_session(uow, user, AuthMethod.PASSWORD, context, now)
            await self._audit(
                uow,
                "auth.login",
                "success",
                context,
                actor_user_id=user.id,
                subject_user_id=user.id,
                session_id=issued.principal.session_id,
            )
            await uow.commit()
            return issued

    async def authenticate(self, encoded_access_token: str | None) -> AuthenticatedPrincipal:
        if encoded_access_token is None:
            raise AuthenticationRequired
        parsed = self._tokens.parse(encoded_access_token)
        if parsed is None:
            raise AuthenticationRequired
        session_id, secret = parsed
        now = self._clock.now()
        async with self._uow() as uow:
            session = await uow.get_session(session_id)
            if (
                session is None
                or not session.is_active(now)
                or session.access_expires_at <= now
                or not self._tokens.verify(session.access_token_hash, secret)
            ):
                raise AuthenticationRequired
            user = await uow.get_user(session.user_id)
            if user is None or user.status is not UserStatus.ACTIVE:
                raise AuthenticationRequired
            if (now - session.last_seen_at).total_seconds() >= 300:
                session.last_seen_at = now
                await uow.save_session(session)
                await uow.commit()
            return AuthenticatedPrincipal(
                user_id=user.id,
                session_id=session.id,
                authenticated_at=session.authenticated_at,
                auth_method=session.auth_method,
            )

    async def verify_csrf(self, principal: AuthenticatedPrincipal, csrf_token: str) -> None:
        parsed = self._tokens.parse(csrf_token)
        if parsed is None:
            raise CsrfRejected
        _token_id, secret = parsed
        async with self._uow() as uow:
            session = await uow.get_session(principal.session_id)
            if session is None or not self._tokens.verify(session.csrf_token_hash, secret):
                raise CsrfRejected

    async def refresh(self, encoded_refresh_token: str, context: RequestContext) -> IssuedSession:
        parsed = self._tokens.parse(encoded_refresh_token)
        if parsed is None:
            raise AuthenticationRequired
        token_id, secret = parsed
        now = self._clock.now()
        async with self._uow() as uow:
            token = await uow.get_refresh_token(token_id, for_update=True)
            if token is None or not self._tokens.verify(token.token_hash, secret):
                raise AuthenticationRequired
            session = await uow.get_session(token.session_id, for_update=True)
            if session is None:
                raise AuthenticationRequired
            if not token.is_active(now) or not session.is_active(now):
                session.revoked_at = now
                await uow.save_session(session)
                await uow.revoke_refresh_family(session.id, now)
                await self._audit(
                    uow,
                    "auth.refresh_reuse",
                    "denied",
                    context,
                    subject_user_id=session.user_id,
                    session_id=session.id,
                )
                await uow.commit()
                raise AuthenticationRequired

            access = self._tokens.issue_for_id(session.id)
            refresh = self._tokens.issue()
            csrf = self._tokens.issue()
            token.used_at = now
            token.replaced_by_token_id = refresh.id
            await uow.add_refresh_token(
                RefreshToken(
                    id=refresh.id,
                    session_id=session.id,
                    token_hash=refresh.digest,
                    parent_token_id=token.id,
                    issued_at=now,
                    expires_at=session.expires_at,
                )
            )
            await uow.save_refresh_token(token)
            session.access_token_hash = access.digest
            session.csrf_token_hash = csrf.digest
            session.access_expires_at = min(
                now + timedelta(seconds=self._policy.access_ttl_seconds),
                session.expires_at - timedelta(microseconds=1),
            )
            session.last_seen_at = now
            await uow.save_session(session)
            await self._audit(
                uow,
                "auth.refresh",
                "success",
                context,
                actor_user_id=session.user_id,
                subject_user_id=session.user_id,
                session_id=session.id,
            )
            await uow.commit()
            return IssuedSession(
                principal=AuthenticatedPrincipal(
                    user_id=session.user_id,
                    session_id=session.id,
                    authenticated_at=session.authenticated_at,
                    auth_method=session.auth_method,
                ),
                access_token=access.encoded,
                refresh_token=refresh.encoded,
                csrf_token=csrf.encoded,
                expires_at=session.expires_at,
            )

    async def logout(self, principal: AuthenticatedPrincipal, context: RequestContext) -> None:
        now = self._clock.now()
        async with self._uow() as uow:
            session = await uow.get_session(principal.session_id, for_update=True)
            if session is not None and session.user_id == principal.user_id:
                session.revoked_at = now
                await uow.save_session(session)
                await uow.revoke_refresh_family(session.id, now)
            await self._audit(
                uow,
                "auth.logout",
                "success",
                context,
                actor_user_id=principal.user_id,
                subject_user_id=principal.user_id,
                session_id=principal.session_id,
            )
            await uow.commit()

    async def logout_all(self, principal: AuthenticatedPrincipal, context: RequestContext) -> None:
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.revoke_user_sessions(principal.user_id, now)
            await self._audit(
                uow,
                "auth.logout_all",
                "success",
                context,
                actor_user_id=principal.user_id,
                subject_user_id=principal.user_id,
                session_id=principal.session_id,
            )
            await uow.commit()

    async def forgot_password(self, email: str, context: RequestContext) -> None:
        normalized = self._email_normalizer.normalize(email)
        await self._limit("forgot_password", normalized, 3, context)
        now = self._clock.now()
        delivery: EmailMessage | None = None
        async with self._uow() as uow:
            user = await uow.get_user_by_email(normalized, for_update=True)
            if (
                user is not None
                and user.status is UserStatus.ACTIVE
                and user.password_hash is not None
            ):
                delivery = await self._issue_email_token(
                    uow, user, TokenPurpose.RESET_PASSWORD, now
                )
                await self._audit(
                    uow,
                    "auth.password_reset_requested",
                    "accepted",
                    context,
                    subject_user_id=user.id,
                )
            await uow.commit()
        if delivery is not None:
            await self._send_enumeration_safe(delivery)

    async def reset_password(
        self, encoded_token: str, new_password: str, context: RequestContext
    ) -> None:
        parsed = self._tokens.parse(encoded_token)
        if parsed is None:
            raise InvalidOrExpiredToken
        token_id, secret = parsed
        await self._limit("reset_password", str(token_id), 5, context)
        password_hash = await self._passwords.hash(new_password)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_one_time_token(token_id, for_update=True)
            if record is None:
                raise InvalidOrExpiredToken
            user_id, purpose, digest, expires_at, consumed_at = record
            if (
                purpose is not TokenPurpose.RESET_PASSWORD
                or consumed_at is not None
                or expires_at <= now
                or not self._tokens.verify(digest, secret)
            ):
                raise InvalidOrExpiredToken
            user = await uow.get_user(user_id, for_update=True)
            if user is None or user.status is not UserStatus.ACTIVE:
                raise InvalidOrExpiredToken
            user.password_hash = password_hash
            user.auth_version += 1
            user.updated_at = now
            await uow.save_user(user)
            await uow.consume_one_time_token(token_id, now)
            await uow.revoke_user_sessions(user.id, now)
            await self._audit(
                uow,
                "auth.password_reset",
                "success",
                context,
                subject_user_id=user.id,
            )
            await uow.commit()

    async def change_password(
        self,
        principal: AuthenticatedPrincipal,
        *,
        current_password: str | None,
        new_password: str,
        context: RequestContext,
    ) -> None:
        """Replace a password after recent authentication and revoke every session."""

        self.require_recent_authentication(principal)
        await self._limit(
            "change_password",
            str(principal.user_id),
            5,
            context,
        )
        now = self._clock.now()
        async with self._uow() as uow:
            user = await uow.get_user(principal.user_id, for_update=True)
            if user is None or user.status is not UserStatus.ACTIVE:
                raise AuthenticationRequired
            if user.password_hash is not None and (
                current_password is None
                or not await self._passwords.verify(
                    user.password_hash,
                    current_password,
                )
            ):
                await self._audit(
                    uow,
                    "auth.password_change",
                    "denied",
                    context,
                    actor_user_id=user.id,
                    subject_user_id=user.id,
                    session_id=principal.session_id,
                )
                await uow.commit()
                raise CurrentPasswordRejected
            user.password_hash = await self._passwords.hash(new_password)
            user.auth_version += 1
            user.updated_at = now
            await uow.save_user(user)
            await uow.invalidate_one_time_tokens(
                user.id,
                TokenPurpose.RESET_PASSWORD,
                now,
            )
            await uow.revoke_user_sessions(user.id, now)
            await self._audit(
                uow,
                "auth.password_change",
                "success",
                context,
                actor_user_id=user.id,
                subject_user_id=user.id,
                session_id=principal.session_id,
            )
            await uow.commit()

    async def list_sessions(self, principal: AuthenticatedPrincipal) -> list[SessionSummary]:
        now = self._clock.now()
        async with self._uow() as uow:
            sessions = await uow.list_sessions(principal.user_id)
        return [
            SessionSummary(
                id=session.id,
                current=session.id == principal.session_id,
                auth_method=session.auth_method,
                device_label=session.device_label,
                created_at=session.created_at,
                last_seen_at=session.last_seen_at,
                expires_at=session.expires_at,
            )
            for session in sessions
            if session.is_active(now)
        ]

    async def revoke_session(
        self, principal: AuthenticatedPrincipal, session_id: UUID, context: RequestContext
    ) -> bool:
        now = self._clock.now()
        async with self._uow() as uow:
            session = await uow.get_session(session_id, for_update=True)
            if session is None or session.user_id != principal.user_id:
                raise ResourceNotFound
            session.revoked_at = now
            await uow.save_session(session)
            await uow.revoke_refresh_family(session.id, now)
            await self._audit(
                uow,
                "auth.session_revoked",
                "success",
                context,
                actor_user_id=principal.user_id,
                subject_user_id=principal.user_id,
                session_id=session.id,
            )
            await uow.commit()
            return session.id == principal.session_id

    async def get_current_user(self, principal: AuthenticatedPrincipal) -> CurrentUser:
        async with self._uow() as uow:
            user = await uow.get_user(principal.user_id)
            profile = await uow.get_profile(principal.user_id)
        if user is None or profile is None:
            raise AuthenticationRequired
        return self._current_user(user, profile)

    async def update_current_user(
        self,
        principal: AuthenticatedPrincipal,
        *,
        expected_version: int,
        updates: dict[str, str | None],
        context: RequestContext,
    ) -> CurrentUser:
        now = self._clock.now()
        allowed = {
            "display_name",
            "locale",
            "timezone",
            "target_role",
            "preferred_location",
            "work_model",
            "seniority",
            "industry",
            "language",
            "writing_style",
        }
        async with self._uow() as uow:
            user = await uow.get_user(principal.user_id)
            profile = await uow.get_profile(principal.user_id, for_update=True)
            if user is None or profile is None:
                raise AuthenticationRequired
            if profile.version != expected_version:
                raise VersionConflict
            for key, value in updates.items():
                if key in allowed:
                    setattr(profile, key, value)
            profile.version += 1
            profile.updated_at = now
            await uow.save_profile(profile)
            await self._audit(
                uow,
                "account.profile_updated",
                "success",
                context,
                actor_user_id=principal.user_id,
                subject_user_id=principal.user_id,
            )
            await uow.commit()
            return self._current_user(user, profile)

    async def get_onboarding(self, principal: AuthenticatedPrincipal) -> OnboardingView:
        async with self._uow() as uow:
            progress = await uow.get_onboarding(principal.user_id)
            profile = await uow.get_profile(principal.user_id)
        if progress is None or profile is None:
            raise ResourceNotFound
        observation = await self._observe_resume(principal.user_id, progress)
        return self._onboarding_view(progress, profile, observation)

    async def update_onboarding(
        self,
        principal: AuthenticatedPrincipal,
        *,
        expected_version: int,
        current_step: OnboardingStep,
        skipped_steps: tuple[OnboardingStep, ...],
        profile_updates: dict[str, str | None],
        context: RequestContext,
    ) -> OnboardingView:
        now = self._clock.now()
        if len(set(skipped_steps)) != len(skipped_steps):
            raise ValueError("skipped onboarding steps must be unique")
        async with self._uow() as uow:
            progress = await uow.get_onboarding(principal.user_id, for_update=True)
            profile = await uow.get_profile(principal.user_id, for_update=True)
            if progress is None or profile is None:
                raise ResourceNotFound
            if progress.version != expected_version:
                raise VersionConflict
            observation = await self._observe_resume(principal.user_id, progress)
            self._validate_onboarding_advance(current_step, skipped_steps, observation)
            status = (
                OnboardingStatus.COMPLETED
                if current_step is OnboardingStep.COMPLETE
                else OnboardingStatus.IN_PROGRESS
            )
            progress.current_step = current_step
            progress.status = status
            progress.resume_handoff = (
                HandoffStatus.SKIPPED
                if OnboardingStep.RESUME in skipped_steps
                else progress.resume_handoff
            )
            progress.parsed_review_handoff = (
                HandoffStatus.SKIPPED
                if OnboardingStep.PARSED_REVIEW in skipped_steps
                else progress.parsed_review_handoff
            )
            progress.skipped_steps = skipped_steps
            progress.version += 1
            progress.updated_at = now
            progress.completed_at = now if status is OnboardingStatus.COMPLETED else None
            for key, value in profile_updates.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.version += 1
            profile.updated_at = now
            await uow.save_profile(profile)
            await uow.save_onboarding(progress)
            await self._audit(
                uow,
                "onboarding.progress_updated",
                "success",
                context,
                actor_user_id=principal.user_id,
                subject_user_id=principal.user_id,
            )
            await uow.commit()
            observation = await self._observe_resume(principal.user_id, progress)
            return self._onboarding_view(progress, profile, observation)

    async def list_consents(self, principal: AuthenticatedPrincipal) -> list[ConsentView]:
        async with self._uow() as uow:
            events = await uow.list_current_consents(principal.user_id)
        return [
            ConsentView(
                purpose=event.purpose,
                decision=event.decision,
                policy_version=event.policy_version,
                recorded_at=event.recorded_at,
            )
            for event in events
        ]

    async def get_account_security(
        self,
        principal: AuthenticatedPrincipal,
    ) -> AccountSecurityView:
        async with self._uow() as uow:
            user = await uow.get_user(principal.user_id)
            google = await uow.get_user_oauth_account(
                principal.user_id,
                "google",
            )
        if user is None:
            raise AuthenticationRequired
        return AccountSecurityView(
            has_password=user.password_hash is not None,
            google_connected=google is not None,
        )

    async def disconnect_google(
        self,
        principal: AuthenticatedPrincipal,
        context: RequestContext,
    ) -> None:
        self.require_recent_authentication(principal)
        async with self._uow() as uow:
            user = await uow.get_user(principal.user_id, for_update=True)
            account = await uow.get_user_oauth_account(
                principal.user_id,
                "google",
            )
            if user is None:
                raise AuthenticationRequired
            if account is None:
                raise ResourceNotFound
            if user.password_hash is None:
                raise IdentityConflict
            await uow.delete_oauth_account(user.id, "google")
            await self._audit(
                uow,
                "auth.google_disconnected",
                "success",
                context,
                actor_user_id=user.id,
                subject_user_id=user.id,
                session_id=principal.session_id,
                target_type="oauth_account",
                target_id=account.id,
            )
            await uow.commit()

    async def list_security_activity(
        self,
        principal: AuthenticatedPrincipal,
        *,
        limit: int = 50,
    ) -> list[SecurityActivityView]:
        bounded_limit = min(max(limit, 1), 100)
        async with self._uow() as uow:
            events = await uow.list_audit_events(
                principal.user_id,
                limit=bounded_limit,
            )
        return [
            SecurityActivityView(
                id=event.id,
                event_type=event.event_type,
                outcome=event.outcome,
                occurred_at=event.occurred_at,
                current_session=event.session_id == principal.session_id,
            )
            for event in events
        ]

    async def record_consent(
        self,
        principal: AuthenticatedPrincipal,
        purpose: str,
        granted: bool,
        context: RequestContext,
    ) -> ConsentView:
        now = self._clock.now()
        event = ConsentEvent(
            id=uuid4(),
            user_id=principal.user_id,
            purpose=purpose,
            decision=ConsentDecision.GRANTED if granted else ConsentDecision.WITHDRAWN,
            policy_version=self._policy.consent_policy_version,
            request_id=context.request_id,
            trace_id=context.trace_id,
            recorded_at=now,
        )
        async with self._uow() as uow:
            await uow.add_consent_event(event)
            await self._audit(
                uow,
                "account.consent_recorded",
                "success",
                context,
                actor_user_id=principal.user_id,
                subject_user_id=principal.user_id,
                target_type="consent",
                target_id=event.id,
                metadata={"purpose": purpose, "decision": event.decision.value},
            )
            await uow.commit()
        return ConsentView(
            purpose=event.purpose,
            decision=event.decision,
            policy_version=event.policy_version,
            recorded_at=event.recorded_at,
        )

    async def start_google_oauth(
        self, return_to: str, principal: AuthenticatedPrincipal | None = None
    ) -> OAuthStart:
        if not self._google.enabled:
            raise OAuthUnavailable
        if principal is not None:
            self.require_recent_authentication(principal)
        return await self._google.start(
            return_to,
            link_user_id=principal.user_id if principal is not None else None,
        )

    async def complete_google_oauth(
        self,
        code: str,
        state: str,
        context: RequestContext,
        principal: AuthenticatedPrincipal | None = None,
    ) -> OAuthCompletion:
        if not self._google.enabled:
            raise OAuthUnavailable
        identity = await self._google.complete(code, state)
        if not identity.email_verified:
            raise OAuthFlowRejected
        normalized = self._email_normalizer.normalize(identity.email)
        now = self._clock.now()
        async with self._uow() as uow:
            account = await uow.get_oauth_account("google", identity.subject)
            user: User | None
            if identity.link_user_id is not None:
                if principal is None or principal.user_id != identity.link_user_id:
                    raise OAuthFlowRejected
                self.require_recent_authentication(principal)
                if account is not None and account.user_id != principal.user_id:
                    raise OAuthCollision
                existing_for_user = await uow.get_user_oauth_account(principal.user_id, "google")
                if (
                    existing_for_user is not None
                    and existing_for_user.provider_subject != identity.subject
                ):
                    raise OAuthCollision
                user = await uow.get_user(principal.user_id)
                if user is None:
                    raise OAuthFlowRejected
                if account is None:
                    account = OAuthAccount(
                        id=uuid4(),
                        user_id=user.id,
                        provider="google",
                        provider_subject=identity.subject,
                        provider_email_normalized=normalized,
                        created_at=now,
                        last_login_at=now,
                    )
                    await uow.add_oauth_account(account)
            elif account is not None:
                user = await uow.get_user(account.user_id)
                account.last_login_at = now
                await uow.save_oauth_account(account)
            else:
                existing_user = await uow.get_user_by_email(normalized)
                if existing_user is not None:
                    raise OAuthCollision
                user = User(
                    id=uuid4(),
                    email_normalized=normalized,
                    password_hash=None,
                    status=UserStatus.ACTIVE,
                    email_verified_at=now,
                    auth_version=1,
                    created_at=now,
                    updated_at=now,
                )
                await uow.add_user(user)
                await uow.add_profile(self._new_profile(user.id, identity.display_name, now))
                await uow.add_onboarding(self._new_onboarding(user.id, now))
                await uow.add_oauth_account(
                    OAuthAccount(
                        id=uuid4(),
                        user_id=user.id,
                        provider="google",
                        provider_subject=identity.subject,
                        provider_email_normalized=normalized,
                        created_at=now,
                        last_login_at=now,
                    )
                )
            if user is None or user.status is not UserStatus.ACTIVE:
                raise OAuthFlowRejected
            issued = await self._create_session(uow, user, AuthMethod.GOOGLE, context, now)
            await self._audit(
                uow,
                "auth.google_completed",
                "success",
                context,
                actor_user_id=user.id,
                subject_user_id=user.id,
                session_id=issued.principal.session_id,
            )
            await uow.commit()
        return OAuthCompletion(session=issued, return_to=identity.return_to)

    def require_recent_authentication(self, principal: AuthenticatedPrincipal) -> None:
        if not principal.was_recently_authenticated(
            self._clock.now(), self._policy.recent_auth_ttl_seconds
        ):
            raise RecentAuthenticationRequired

    async def _create_session(
        self,
        uow: IdentityUnitOfWork,
        user: User,
        auth_method: AuthMethod,
        context: RequestContext,
        now: datetime,
    ) -> IssuedSession:
        access = self._tokens.issue()
        refresh = self._tokens.issue()
        csrf = self._tokens.issue()
        session_expires_at = now + timedelta(seconds=self._policy.refresh_ttl_seconds)
        session = Session(
            id=access.id,
            user_id=user.id,
            access_token_hash=access.digest,
            csrf_token_hash=csrf.digest,
            auth_method=auth_method,
            device_label=context.device_label,
            created_at=now,
            authenticated_at=now,
            last_seen_at=now,
            access_expires_at=now + timedelta(seconds=self._policy.access_ttl_seconds),
            expires_at=session_expires_at,
        )
        await uow.add_session(session)
        await uow.add_refresh_token(
            RefreshToken(
                id=refresh.id,
                session_id=session.id,
                token_hash=refresh.digest,
                issued_at=now,
                expires_at=session_expires_at,
            )
        )
        return IssuedSession(
            principal=AuthenticatedPrincipal(
                user_id=user.id,
                session_id=session.id,
                authenticated_at=now,
                auth_method=auth_method,
            ),
            access_token=access.encoded,
            refresh_token=refresh.encoded,
            csrf_token=csrf.encoded,
            expires_at=session_expires_at,
        )

    async def _issue_email_token(
        self,
        uow: IdentityUnitOfWork,
        user: User,
        purpose: TokenPurpose,
        now: datetime,
    ) -> EmailMessage:
        await uow.invalidate_one_time_tokens(user.id, purpose, now)
        issued = self._tokens.issue()
        ttl = (
            self._policy.verification_ttl_seconds
            if purpose is TokenPurpose.VERIFY_EMAIL
            else self._policy.reset_ttl_seconds
        )
        await uow.add_one_time_token(
            issued.id,
            user.id,
            purpose,
            issued.digest,
            now,
            now + timedelta(seconds=ttl),
        )
        if purpose is TokenPurpose.VERIFY_EMAIL:
            path = f"/verify-email#token={issued.encoded}"
            subject = "Verify your Rezumi email"
            action = "Verify email"
        else:
            path = f"/reset-password#token={issued.encoded}"
            subject = "Reset your Rezumi password"
            action = "Reset password"
        url = f"{self._policy.public_app_url.rstrip('/')}{path}"
        escaped_url = escape(url, quote=True)
        return EmailMessage(
            recipient=user.email_normalized,
            subject=subject,
            text_body=f"{action}: {url}\n\nIf you did not request this, ignore this email.",
            html_body=(
                f'<p><a href="{escaped_url}">{escape(action)}</a></p>'
                "<p>If you did not request this, ignore this email.</p>"
            ),
        )

    async def _send_enumeration_safe(self, message: EmailMessage) -> None:
        try:
            await self._emails.send(message)
        except Exception:
            # The public response must not reveal account existence or provider state.
            return

    async def _limit(self, action: str, subject: str, limit: int, context: RequestContext) -> None:
        await self._limiter.check(
            action,
            f"identity:{subject}",
            limit,
            self._policy.rate_limit_window_seconds,
        )
        await self._limiter.check(
            action,
            f"source:{context.source_key}",
            max(limit * 20, 100),
            self._policy.rate_limit_window_seconds,
        )

    async def _audit(
        self,
        uow: IdentityUnitOfWork,
        event_type: str,
        outcome: str,
        context: RequestContext,
        *,
        actor_user_id: UUID | None = None,
        subject_user_id: UUID | None = None,
        session_id: UUID | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        await uow.add_audit_event(
            AuditEvent(
                id=uuid4(),
                event_type=event_type,
                outcome=outcome,
                request_id=context.request_id,
                trace_id=context.trace_id,
                occurred_at=self._clock.now(),
                actor_user_id=actor_user_id,
                subject_user_id=subject_user_id,
                session_id=session_id,
                target_type=target_type,
                target_id=target_id,
                metadata=dict(metadata or {}),
            )
        )

    @staticmethod
    def _new_profile(user_id: UUID, display_name: str, now: datetime) -> Profile:
        return Profile(
            user_id=user_id,
            display_name=display_name,
            locale="en",
            timezone="UTC",
            target_role=None,
            preferred_location=None,
            work_model=None,
            seniority=None,
            industry=None,
            language="en",
            writing_style="balanced",
            version=1,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _new_onboarding(user_id: UUID, now: datetime) -> OnboardingProgress:
        return OnboardingProgress(
            user_id=user_id,
            status=OnboardingStatus.IN_PROGRESS,
            current_step=OnboardingStep.PROFILE,
            resume_handoff=HandoffStatus.NOT_STARTED,
            parsed_review_handoff=HandoffStatus.NOT_STARTED,
            skipped_steps=(),
            version=1,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _current_user(user: User, profile: Profile) -> CurrentUser:
        return CurrentUser(
            id=user.id,
            email=user.email_normalized,
            display_name=profile.display_name,
            email_verified=user.email_verified_at is not None,
            locale=profile.locale,
            timezone=profile.timezone,
            target_role=profile.target_role,
            preferred_location=profile.preferred_location,
            work_model=profile.work_model,
            seniority=profile.seniority,
            industry=profile.industry,
            language=profile.language,
            writing_style=profile.writing_style,
            version=profile.version,
        )

    async def _observe_resume(
        self, owner_user_id: UUID, progress: OnboardingProgress
    ) -> OnboardingResumeObservation:
        if self._onboarding_resume_source is None:
            return OnboardingResumeObservation(
                resume_status=ObservedResumeStatus(progress.resume_handoff.value),
                parsed_review_status=ObservedResumeStatus(progress.parsed_review_handoff.value),
            )
        observed = await self._onboarding_resume_source.observe(owner_user_id)
        return OnboardingResumeObservation(
            resume_status=(
                ObservedResumeStatus.SKIPPED
                if observed.resume_status is ObservedResumeStatus.NOT_STARTED
                and progress.resume_handoff is HandoffStatus.SKIPPED
                else observed.resume_status
            ),
            parsed_review_status=(
                ObservedResumeStatus.SKIPPED
                if observed.parsed_review_status is ObservedResumeStatus.NOT_STARTED
                and progress.parsed_review_handoff is HandoffStatus.SKIPPED
                else observed.parsed_review_status
            ),
            document_id=observed.document_id,
            safe_error_code=observed.safe_error_code,
        )

    @staticmethod
    def _validate_onboarding_advance(
        current_step: OnboardingStep,
        skipped_steps: tuple[OnboardingStep, ...],
        observation: OnboardingResumeObservation,
    ) -> None:
        if current_step in {
            OnboardingStep.PARSED_REVIEW,
            OnboardingStep.PREFERENCES,
            OnboardingStep.COMPLETE,
        } and (
            observation.resume_status
            not in {
                ObservedResumeStatus.REVIEW_REQUIRED,
                ObservedResumeStatus.REVIEWED,
                ObservedResumeStatus.ANALYSIS_READY,
            }
            and OnboardingStep.RESUME not in skipped_steps
        ):
            raise ValueError("resume must be observed or explicitly skipped")
        if current_step in {OnboardingStep.PREFERENCES, OnboardingStep.COMPLETE} and (
            observation.parsed_review_status
            not in {
                ObservedResumeStatus.REVIEWED,
                ObservedResumeStatus.ANALYSIS_READY,
            }
            and OnboardingStep.PARSED_REVIEW not in skipped_steps
        ):
            raise ValueError("parsed review must be observed or explicitly skipped")

    @staticmethod
    def _onboarding_view(
        progress: OnboardingProgress,
        profile: Profile,
        observation: OnboardingResumeObservation,
    ) -> OnboardingView:
        current_step = progress.current_step
        if progress.status is not OnboardingStatus.COMPLETED:
            if (
                current_step is OnboardingStep.RESUME
                and observation.resume_status is ObservedResumeStatus.REVIEW_REQUIRED
            ):
                current_step = OnboardingStep.PARSED_REVIEW
            elif current_step in {
                OnboardingStep.RESUME,
                OnboardingStep.PARSED_REVIEW,
            } and observation.parsed_review_status in {
                ObservedResumeStatus.REVIEWED,
                ObservedResumeStatus.ANALYSIS_READY,
            }:
                current_step = OnboardingStep.PREFERENCES
        return OnboardingView(
            status=progress.status,
            current_step=current_step,
            resume_handoff=observation.resume_status,
            parsed_review_handoff=observation.parsed_review_status,
            latest_resume_document_id=observation.document_id,
            resume_safe_error_code=observation.safe_error_code,
            skipped_steps=progress.skipped_steps,
            version=progress.version,
            display_name=profile.display_name,
            target_role=profile.target_role,
            preferred_location=profile.preferred_location,
            work_model=profile.work_model,
            seniority=profile.seniority,
            industry=profile.industry,
            language=profile.language,
            writing_style=profile.writing_style,
        )
