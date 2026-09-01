"""Identity policy tests across registration, sessions, recovery, OAuth, and ownership."""

# ruff: noqa: S105, S106, S107 -- explicit non-production credentials exercise auth policy.

from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from identity_memory import MemoryIdentityUnitOfWork, MemoryIdentityUnitOfWorkFactory

from rezumi.modules.identity.application.models import (
    OnboardingResumeObservation,
    RequestContext,
)
from rezumi.modules.identity.application.service import IdentityPolicy, IdentityService
from rezumi.modules.identity.domain import (
    ConsentDecision,
    ObservedResumeStatus,
    OnboardingStep,
)
from rezumi.modules.identity.domain.errors import (
    AuthenticationRequired,
    CurrentPasswordRejected,
    EmailVerificationRequired,
    InvalidCredentials,
    InvalidOrExpiredToken,
    OAuthCollision,
    RateLimited,
    RecentAuthenticationRequired,
    ResourceNotFound,
    VersionConflict,
)
from rezumi.modules.identity.infrastructure.fakes import (
    CapturingEmailSender,
    DeterministicGoogleOAuthProvider,
    FakeOAuthUser,
    FrozenClock,
    InMemoryAbuseLimiter,
    utc_test_clock,
)
from rezumi.modules.identity.infrastructure.security import (
    HmacTokenManager,
    NormalizedEmailValidator,
)


class FastPasswordHasher:
    """Deterministic test double; Argon2id itself is tested separately."""

    async def hash(self, password: str) -> str:
        return f"test-password-hash::{password}"

    async def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == await self.hash(password)

    async def verify_dummy(self, password: str) -> None:
        del password


@dataclass(slots=True)
class MutableOnboardingResumeSource:
    observation: OnboardingResumeObservation
    observed_owner_ids: list[UUID] = field(default_factory=list)

    async def observe(self, owner_user_id: UUID) -> OnboardingResumeObservation:
        self.observed_owner_ids.append(owner_user_id)
        return self.observation


@dataclass(slots=True)
class Harness:
    service: IdentityService
    store: MemoryIdentityUnitOfWork
    emails: CapturingEmailSender
    clock: FrozenClock


def _harness(
    *,
    oauth_email: str = "oauth@example.com",
    onboarding_source: MutableOnboardingResumeSource | None = None,
) -> Harness:
    store = MemoryIdentityUnitOfWork()
    emails = CapturingEmailSender()
    clock = utc_test_clock()
    service = IdentityService(
        unit_of_work=MemoryIdentityUnitOfWorkFactory(store),
        clock=clock,
        passwords=FastPasswordHasher(),
        tokens=HmacTokenManager("test-pepper-that-is-at-least-thirty-two-bytes"),
        emails=emails,
        email_normalizer=NormalizedEmailValidator(),
        limiter=InMemoryAbuseLimiter(),
        google=DeterministicGoogleOAuthProvider(FakeOAuthUser(email=oauth_email)),
        policy=IdentityPolicy(public_app_url="https://app.example.test"),
        onboarding_resume_source=onboarding_source,
    )
    return Harness(service=service, store=store, emails=emails, clock=clock)


def _context(device: str = "Firefox on Linux", source: str = "198.51.100.8") -> RequestContext:
    return RequestContext(
        request_id="request-safe-1",
        trace_id="1" * 32,
        device_label=device,
        source_key=source,
    )


def _token_from_latest_email(harness: Harness) -> str:
    body = harness.emails.messages[-1].text_body
    return body.split("#token=", 1)[1].splitlines()[0]


async def _register_verify_login(
    harness: Harness,
    email: str = "alex@example.com",
    password: str = "correct horse battery staple",
):
    await harness.service.register(email, password, "Alex Example", _context())
    token = _token_from_latest_email(harness)
    await harness.service.verify_email(token, _context())
    return await harness.service.login(email, password, _context())


@pytest.mark.asyncio
async def test_registration_verification_and_login_use_single_use_hashed_tokens() -> None:
    harness = _harness()

    await harness.service.register(
        "  ALEX@example.com ", "correct horse battery staple", "Alex Example", _context()
    )
    assert len(harness.store.users) == 1
    user = next(iter(harness.store.users.values()))
    assert user.email_normalized == "alex@example.com"
    assert user.password_hash != "correct horse battery staple"
    assert "alex@example.com" not in repr(harness.store.audit_events)

    with pytest.raises(EmailVerificationRequired):
        await harness.service.login("alex@example.com", "correct horse battery staple", _context())

    verification_token = _token_from_latest_email(harness)
    assert verification_token not in repr(harness.store.one_time_tokens)
    await harness.service.verify_email(verification_token, _context())
    with pytest.raises(InvalidOrExpiredToken):
        await harness.service.verify_email(verification_token, _context())

    issued = await harness.service.login(
        "alex@example.com", "correct horse battery staple", _context()
    )
    principal = await harness.service.authenticate(issued.access_token)
    assert principal.user_id == user.id
    await harness.service.verify_csrf(principal, issued.csrf_token)


@pytest.mark.asyncio
async def test_refresh_rotates_all_browser_secrets_and_replay_revokes_the_family() -> None:
    harness = _harness()
    first = await _register_verify_login(harness)

    rotated = await harness.service.refresh(first.refresh_token, _context())
    assert rotated.access_token != first.access_token
    assert rotated.refresh_token != first.refresh_token
    assert rotated.csrf_token != first.csrf_token
    assert rotated.principal.session_id == first.principal.session_id
    assert await harness.service.authenticate(rotated.access_token) == rotated.principal
    with pytest.raises(AuthenticationRequired):
        await harness.service.authenticate(first.access_token)

    with pytest.raises(AuthenticationRequired):
        await harness.service.refresh(first.refresh_token, _context())
    with pytest.raises(AuthenticationRequired):
        await harness.service.authenticate(rotated.access_token)
    assert harness.store.sessions[first.principal.session_id].revoked_at is not None


@pytest.mark.asyncio
async def test_password_recovery_is_enumeration_safe_single_use_and_revokes_sessions() -> None:
    harness = _harness()
    session = await _register_verify_login(harness)
    message_count = len(harness.emails.messages)

    await harness.service.forgot_password("missing@example.com", _context())
    assert len(harness.emails.messages) == message_count
    await harness.service.forgot_password("alex@example.com", _context())
    reset_token = _token_from_latest_email(harness)

    await harness.service.reset_password(reset_token, "a new long password value", _context())
    with pytest.raises(AuthenticationRequired):
        await harness.service.authenticate(session.access_token)
    with pytest.raises(InvalidOrExpiredToken):
        await harness.service.reset_password(reset_token, "another long password", _context())
    with pytest.raises(InvalidCredentials):
        await harness.service.login("alex@example.com", "correct horse battery staple", _context())
    await harness.service.login("alex@example.com", "a new long password value", _context())


@pytest.mark.asyncio
async def test_password_change_requires_current_secret_and_revokes_every_session() -> None:
    harness = _harness()
    issued = await _register_verify_login(harness)

    with pytest.raises(CurrentPasswordRejected):
        await harness.service.change_password(
            issued.principal,
            current_password="incorrect current password",
            new_password="a replacement long password",
            context=_context(),
        )
    assert await harness.service.authenticate(issued.access_token) == issued.principal

    await harness.service.change_password(
        issued.principal,
        current_password="correct horse battery staple",
        new_password="a replacement long password",
        context=_context(),
    )
    with pytest.raises(AuthenticationRequired):
        await harness.service.authenticate(issued.access_token)
    await harness.service.login(
        "alex@example.com",
        "a replacement long password",
        _context(),
    )
    events = await harness.service.list_security_activity(
        issued.principal,
        limit=100,
    )
    password_change = next(
        event
        for event in events
        if event.event_type == "auth.password_change" and event.outcome == "success"
    )
    assert password_change.current_session
    audit_text = repr(harness.store.audit_events)
    assert "correct horse battery staple" not in audit_text
    assert "a replacement long password" not in audit_text


@pytest.mark.asyncio
async def test_session_management_never_reveals_or_mutates_another_users_session() -> None:
    harness = _harness()
    alex = await _register_verify_login(harness)
    sam = await _register_verify_login(harness, "sam@example.com", "a different long password")

    alex_sessions = await harness.service.list_sessions(alex.principal)
    assert [item.id for item in alex_sessions] == [alex.principal.session_id]
    with pytest.raises(ResourceNotFound):
        await harness.service.revoke_session(alex.principal, sam.principal.session_id, _context())
    assert await harness.service.authenticate(sam.access_token) == sam.principal


@pytest.mark.asyncio
async def test_onboarding_concurrency_and_consent_history_are_owner_scoped() -> None:
    harness = _harness()
    issued = await _register_verify_login(harness)
    principal = issued.principal

    initial = await harness.service.get_onboarding(principal)
    updated = await harness.service.update_onboarding(
        principal,
        expected_version=initial.version,
        current_step=OnboardingStep.RESUME,
        skipped_steps=(OnboardingStep.RESUME,),
        profile_updates={"target_role": "Product Manager", "work_model": "hybrid"},
        context=_context(),
    )
    assert updated.version == initial.version + 1
    assert updated.target_role == "Product Manager"
    assert await harness.service.get_target_role_preference(principal.user_id) == "Product Manager"
    with pytest.raises(VersionConflict):
        await harness.service.update_onboarding(
            principal,
            expected_version=initial.version,
            current_step=OnboardingStep.PREFERENCES,
            skipped_steps=(),
            profile_updates={},
            context=_context(),
        )

    consent = await harness.service.record_consent(principal, "product_analytics", True, _context())
    assert consent.decision is ConsentDecision.GRANTED
    assert await harness.service.list_consents(principal) == [consent]


@pytest.mark.asyncio
async def test_onboarding_advancement_uses_observed_resume_state_or_explicit_skip() -> None:
    source = MutableOnboardingResumeSource(
        OnboardingResumeObservation(
            resume_status=ObservedResumeStatus.PROCESSING,
            parsed_review_status=ObservedResumeStatus.NOT_STARTED,
        )
    )
    harness = _harness(onboarding_source=source)
    issued = await _register_verify_login(harness)
    principal = issued.principal
    initial = await harness.service.get_onboarding(principal)

    with pytest.raises(ValueError, match="resume must be observed"):
        await harness.service.update_onboarding(
            principal,
            expected_version=initial.version,
            current_step=OnboardingStep.PARSED_REVIEW,
            skipped_steps=(),
            profile_updates={},
            context=_context(),
        )

    source.observation = OnboardingResumeObservation(
        resume_status=ObservedResumeStatus.REVIEW_REQUIRED,
        parsed_review_status=ObservedResumeStatus.REVIEW_REQUIRED,
    )
    observed = await harness.service.get_onboarding(principal)
    assert observed.resume_handoff is ObservedResumeStatus.REVIEW_REQUIRED
    assert observed.current_step is OnboardingStep.PROFILE

    resumed = await harness.service.update_onboarding(
        principal,
        expected_version=observed.version,
        current_step=OnboardingStep.PARSED_REVIEW,
        skipped_steps=(),
        profile_updates={},
        context=_context(),
    )
    assert resumed.current_step is OnboardingStep.PARSED_REVIEW

    source.observation = OnboardingResumeObservation(
        resume_status=ObservedResumeStatus.REVIEWED,
        parsed_review_status=ObservedResumeStatus.REVIEWED,
    )
    ready = await harness.service.get_onboarding(principal)
    assert ready.current_step is OnboardingStep.PREFERENCES
    assert source.observed_owner_ids
    assert set(source.observed_owner_ids) == {principal.user_id}


@pytest.mark.asyncio
async def test_oauth_collision_requires_explicit_recently_authenticated_linking() -> None:
    harness = _harness(oauth_email="alex@example.com")
    password_session = await _register_verify_login(harness)

    start = await harness.service.start_google_oauth("/dashboard")
    state = parse_qs(urlparse(start.authorization_url).query)["state"][0]
    with pytest.raises(OAuthCollision):
        await harness.service.complete_google_oauth("test-code", state, _context())

    link = await harness.service.start_google_oauth("/settings", password_session.principal)
    link_state = parse_qs(urlparse(link.authorization_url).query)["state"][0]
    linked = await harness.service.complete_google_oauth(
        "test-code", link_state, _context(), password_session.principal
    )
    assert linked.return_to == "/settings"
    assert linked.session.principal.user_id == password_session.principal.user_id
    account = await harness.service.get_account_security(password_session.principal)
    assert account.has_password
    assert account.google_connected
    await harness.service.disconnect_google(password_session.principal, _context())
    disconnected = await harness.service.get_account_security(password_session.principal)
    assert not disconnected.google_connected

    harness.clock.value += timedelta(seconds=601)
    with pytest.raises(RecentAuthenticationRequired):
        await harness.service.start_google_oauth("/settings", password_session.principal)


@pytest.mark.asyncio
async def test_login_abuse_limit_is_enforced_without_account_disclosure() -> None:
    harness = _harness()
    for _ in range(10):
        with pytest.raises(InvalidCredentials):
            await harness.service.login("missing@example.com", "wrong", _context())
    with pytest.raises(RateLimited):
        await harness.service.login("missing@example.com", "wrong", _context())
