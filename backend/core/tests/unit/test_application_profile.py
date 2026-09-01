"""Unit tests for owner-scoped application profiles and assisted apply handoff."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from application_workspace_memory import (
    JOB_ID,
    NOW,
    OWNER_ID,
    RESUME_VERSION_ID,
    FixedClock,
    MemoryApplicationWorkspace,
    StaticEvidenceProvider,
    StaticJobProvider,
    StaticResumeProvider,
    UuidFactory,
)
from rezumi.modules.application_workspace.application import (
    ApplicationWorkspaceService,
    CreateApplication,
    GenerateApplicationPack,
    RequestContext,
    UpsertApplicationProfile,
)
from rezumi.modules.application_workspace.domain import (
    ApplicationDocumentKind,
    ApplicationProfile,
    ApplicationProfileLink,
    ApplicationWorkspaceIdempotencyConflict,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceUnavailable,
    ApplicationWorkspaceValidationError,
)


def _context(user_id: UUID = OWNER_ID) -> RequestContext:
    return RequestContext(
        actor_user_id=user_id,
        request_id="req-profile-test",
        trace_id="trace-profile-test",
    )


def _service(state: MemoryApplicationWorkspace) -> ApplicationWorkspaceService:
    return ApplicationWorkspaceService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        jobs=StaticJobProvider(),
        resumes=StaticResumeProvider(),
        evidence=StaticEvidenceProvider(),
    )


@pytest.mark.asyncio
async def test_application_profile_upsert_is_owner_scoped_and_idempotent() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    command = UpsertApplicationProfile(
        work_authorization="Authorized to work in the US",
        notice_period_days=30,
        compensation_min=180_000,
        compensation_max=220_000,
        preferred_locations=("Remote",),
        profile_links=(
            ApplicationProfileLink(
                label="Portfolio",
                url="https://example.test/profile",
            ),
        ),
        voluntary_disclosures={"veteran_status": "prefer_not_to_say"},
    )
    created = await service.upsert_application_profile(
        OWNER_ID,
        command,
        idempotency_key="profile-upsert-001",
        context=_context(),
    )
    assert created.version == 1
    assert created.owner_user_id == OWNER_ID

    updated = await service.upsert_application_profile(
        OWNER_ID,
        UpsertApplicationProfile(
            work_authorization="Authorized to work in the US",
            notice_period_days=14,
            compensation_min=180_000,
            compensation_max=220_000,
            preferred_locations=("Remote",),
            profile_links=command.profile_links,
            voluntary_disclosures=command.voluntary_disclosures,
        ),
        idempotency_key="profile-upsert-002",
        context=_context(),
    )
    assert updated.version == 2
    assert updated.notice_period_days == 14

    replay = await service.upsert_application_profile(
        OWNER_ID,
        command,
        idempotency_key="profile-upsert-001",
        context=_context(),
    )
    assert replay.id == created.id
    assert replay.notice_period_days == 14

    with pytest.raises(ApplicationWorkspaceIdempotencyConflict):
        await service.upsert_application_profile(
            OWNER_ID,
            UpsertApplicationProfile(notice_period_days=7),
            idempotency_key="profile-upsert-001",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_application_profile_get_denies_cross_user_lookup() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    await service.upsert_application_profile(
        OWNER_ID,
        UpsertApplicationProfile(work_authorization="US citizen"),
        idempotency_key="profile-owner",
        context=_context(),
    )
    other = uuid4()
    with pytest.raises(ApplicationWorkspaceNotFound):
        await service.upsert_application_profile(
            OWNER_ID,
            UpsertApplicationProfile(work_authorization="US citizen"),
            idempotency_key="profile-cross-user",
            context=_context(other),
        )


@pytest.mark.asyncio
async def test_generate_pack_includes_assisted_apply_handoff_when_profile_exists() -> None:
    state = MemoryApplicationWorkspace()
    service = _service(state)
    application = await service.create_application(
        OWNER_ID,
        CreateApplication(
            job_id=JOB_ID,
            resume_version_id=RESUME_VERSION_ID,
        ),
        idempotency_key="application-for-handoff",
        context=_context(),
    )
    await service.upsert_application_profile(
        OWNER_ID,
        UpsertApplicationProfile(
            work_authorization="Authorized to work in the US",
            notice_period_days=30,
            voluntary_disclosures={
                "questionnaire_ack": "acknowledged",
                "disability_status": (
                    "Yes, I have a disability, or have a history/record of having a disability"
                ),
            },
        ),
        idempotency_key="profile-for-handoff",
        context=_context(),
    )
    pack = await service.generate_pack(
        OWNER_ID,
        application.application.id,
        GenerateApplicationPack(include_kinds=()),
        idempotency_key="pack-with-handoff",
        context=_context(),
    )
    handoff = next(
        document
        for document in pack.documents
        if document.kind is ApplicationDocumentKind.ASSISTED_APPLY_HANDOFF
    )
    assert "Assisted apply handoff" in handoff.title
    assert application.application.job_title in handoff.body
    assert "https://example.test/jobs/principal-product-engineer" in handoff.body
    assert "Work authorization" in handoff.body
    assert "questionnaire_ack" not in handoff.body
    assert "disability status:" in handoff.body.lower()


class _RecordingProfileStore:
    def __init__(self) -> None:
        self.owner_ids: list = []

    async def upsert(self, profile) -> None:
        self.owner_ids.append(profile.owner_user_id)

    async def ping(self) -> None:
        return None

    async def dispose(self) -> None:
        return None


class _FailingProfileStore:
    async def upsert(self, profile) -> None:
        del profile
        raise ApplicationWorkspaceUnavailable

    async def ping(self) -> None:
        return None

    async def dispose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_application_profile_upsert_dual_writes_owner_scoped_document() -> None:
    state = MemoryApplicationWorkspace()
    store = _RecordingProfileStore()
    service = ApplicationWorkspaceService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        jobs=StaticJobProvider(),
        resumes=StaticResumeProvider(),
        evidence=StaticEvidenceProvider(),
        document_store=store,
    )
    created = await service.upsert_application_profile(
        OWNER_ID,
        UpsertApplicationProfile(
            work_authorization="Authorized to work in the US",
            voluntary_disclosures={"veteran_status": "I am not a protected veteran"},
        ),
        idempotency_key="profile-mongo-001",
        context=_context(),
    )
    replay = await service.upsert_application_profile(
        OWNER_ID,
        UpsertApplicationProfile(
            work_authorization="Authorized to work in the US",
            voluntary_disclosures={"veteran_status": "I am not a protected veteran"},
        ),
        idempotency_key="profile-mongo-001",
        context=_context(),
    )
    assert created.owner_user_id == OWNER_ID
    assert replay.id == created.id
    assert store.owner_ids == [OWNER_ID, OWNER_ID]


@pytest.mark.asyncio
async def test_application_profile_document_store_failure_is_unavailable() -> None:
    state = MemoryApplicationWorkspace()
    service = ApplicationWorkspaceService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        jobs=StaticJobProvider(),
        resumes=StaticResumeProvider(),
        evidence=StaticEvidenceProvider(),
        document_store=_FailingProfileStore(),
    )
    with pytest.raises(ApplicationWorkspaceUnavailable):
        await service.upsert_application_profile(
            OWNER_ID,
            UpsertApplicationProfile(work_authorization="Authorized to work in the US"),
            idempotency_key="profile-mongo-fail",
            context=_context(),
        )
    saved = await service.get_application_profile(OWNER_ID, context=_context())
    assert saved is not None
    assert saved.work_authorization == "Authorized to work in the US"


def test_application_profile_rejects_too_many_disclosures() -> None:
    with pytest.raises(ApplicationWorkspaceValidationError):
        ApplicationProfile(
            id=uuid4(),
            owner_user_id=OWNER_ID,
            work_authorization=None,
            notice_period_days=None,
            compensation_min=None,
            compensation_max=None,
            compensation_currency="USD",
            preferred_locations=(),
            profile_links=(),
            voluntary_disclosures={f"key_{index:02d}": "value" for index in range(101)},
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
