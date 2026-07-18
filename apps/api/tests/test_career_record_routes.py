"""Authenticated Phase 3 HTTP workflow and ownership contract tests."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import create_autospec
from uuid import uuid4

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.career_record.application import (
    AttachmentWorkflowService,
    CareerRecordService,
)
from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.application.models import CurrentUser
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.identity.domain.errors import AuthenticationRequired
from careeros.modules.resume_health.application import ResumeHealthService
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

# Reuse the backend's protocol-complete test adapter without shipping it in the
# runtime wheel. API and backend tests remain separate uv workspace members.
_BACKEND_TEST_SUPPORT = Path(__file__).resolve().parents[3] / "packages/backend/tests/unit"
sys.path.insert(0, str(_BACKEND_TEST_SUPPORT))
from career_record_memory import (  # noqa: E402
    FakeResumeSourceQuery,
    FixedClock,
    MemoryCareerRecord,
    UuidFactory,
)

_ORIGIN = "http://localhost:3000"


def _principal(user_id=None) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id or uuid4(),
        session_id=uuid4(),
        authenticated_at=datetime(2026, 7, 15, 12, tzinfo=UTC),
        auth_method=AuthMethod.PASSWORD,
    )


def _user(user_id) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email="career-owner@example.test",
        display_name="Career Owner",
        email_verified=True,
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
    )


def _services(owner_id):
    identity = create_autospec(IdentityService, instance=True)
    principal = _principal(owner_id)
    identity.authenticate.return_value = principal
    identity.get_current_user.return_value = _user(owner_id)
    state = MemoryCareerRecord()
    career = CareerRecordService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        resume_sources=FakeResumeSourceQuery(),
    )
    return identity, career, state, principal


def _write_headers(*, version: int | None = None, idempotency: bool = False):
    return {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        **({"If-Match": f'"{version}"'} if version is not None else {}),
        **({"Idempotency-Key": "test-key"} if idempotency else {}),
    }


def _authenticated_client(
    settings: Settings,
    fake_database: FakeDatabase,
    identity: IdentityService,
    career: CareerRecordService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            career_record=career,
        )
    )
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
    return client


def test_primary_career_evidence_achievement_workflow_is_real_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, career, state, principal = _services(owner_id)
    with _authenticated_client(settings, fake_database, identity, career) as client:
        profile = client.get("/api/v1/career-profile")
        assert profile.status_code == 200
        assert profile.json()["accountPreferences"]["displayName"] == "Career Owner"

        skill = client.post(
            "/api/v1/skills",
            json={"name": "User research", "category": None, "proficiency": "advanced"},
            headers=_write_headers(idempotency=True),
        )
        assert skill.status_code == 201
        skill_id = skill.json()["id"]

        experience = client.post(
            "/api/v1/experiences",
            json={
                "employer": "Fictional Products Ltd",
                "officialTitle": "Product Researcher",
                "displayTitle": None,
                "startDate": "2024-04",
                "endDate": None,
                "current": True,
                "location": None,
                "employmentType": "full_time",
                "description": "User-provided fictional experience.",
                "skillIds": [skill_id],
            },
            headers=_write_headers(idempotency=True),
        )
        assert experience.status_code == 201
        experience_id = experience.json()["id"]
        promoted = client.post(
            "/api/v1/experiences",
            json={
                "employer": "Fictional Products Ltd",
                "officialTitle": "Senior Product Researcher",
                "displayTitle": None,
                "startDate": "2025-04",
                "endDate": None,
                "current": True,
                "location": None,
                "employmentType": "full_time",
                "description": "User-confirmed fictional promotion.",
                "skillIds": [],
                "groupWithExperienceId": experience_id,
            },
            headers=_write_headers(idempotency=True),
        )
        assert promoted.status_code == 201
        listed = client.get("/api/v1/experiences")
        assert listed.status_code == 200
        assert listed.json()["data"][0]["skillIds"] == [skill_id]
        relationship_ids = {item["promotionGroupId"] for item in listed.json()["data"]}
        assert None not in relationship_ids
        assert len(relationship_ids) == 1

        evidence = client.post(
            "/api/v1/evidence",
            json={
                "type": "user_note",
                "title": "Onboarding study source note",
                "description": "The owner reports a fictional onboarding study.",
                "organizationOrProject": None,
                "startDate": None,
                "endDate": None,
                "source": {
                    "sourceType": "manual",
                    "documentId": None,
                    "snapshotId": None,
                    "blockId": None,
                    "page": None,
                    "start": None,
                    "end": None,
                    "url": None,
                },
                "metrics": [],
                "experienceIds": [experience_id],
                "skillIds": [skill_id],
                "attachmentIds": [],
            },
            headers=_write_headers(idempotency=True),
        )
        assert evidence.status_code == 201
        assert evidence.json()["state"] == "inferred"
        assert evidence.json()["factualEligible"] is False
        evidence_id = evidence.json()["id"]

        stale = client.post(
            f"/api/v1/evidence/{evidence_id}/confirm",
            headers=_write_headers(version=2, idempotency=True),
        )
        assert stale.status_code == 409
        confirmed = client.post(
            f"/api/v1/evidence/{evidence_id}/confirm",
            headers=_write_headers(version=1, idempotency=True),
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["state"] == "confirmed"
        assert confirmed.json()["factualEligible"] is True

        achievement = client.post(
            "/api/v1/achievements",
            json={
                "title": "Fictional release outcome",
                "answers": {
                    "delivered": "A fictional onboarding release",
                    "problem": "A user-reported onboarding problem",
                    "changed": "The owner reports a clearer flow",
                    "affected": "New users",
                    "measurement": "",
                    "collaboration": "",
                    "methods": "",
                },
                "metric": None,
                "employerId": None,
                "projectId": None,
            },
            headers=_write_headers(idempotency=True),
        )
        assert achievement.status_code == 201
        converted = client.post(
            f"/api/v1/achievements/{achievement.json()['id']}/confirm",
            headers=_write_headers(version=1, idempotency=True),
        )
        assert converted.status_code == 200
        assert converted.json()["status"] == "converted"
        assert converted.json()["evidenceId"] is not None

        identity.authenticate.return_value = _principal()
        hidden = client.get(f"/api/v1/evidence/{evidence_id}")
        assert hidden.status_code == 404

    assert len(state.entity_skill_links) == 1
    assert principal.user_id == owner_id


def test_career_mutation_requires_authenticated_session_and_csrf(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, career, _, _ = _services(owner_id)
    identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            settings,
            database=fake_database,
            identity=identity,
            career_record=career,
        )
    ) as client:
        anonymous = client.post(
            "/api/v1/skills",
            json={"name": "Research", "category": None, "proficiency": None},
            headers={"Origin": _ORIGIN},
        )
    assert anonymous.status_code == 401

    identity, career, _, _ = _services(owner_id)
    with _authenticated_client(settings, fake_database, identity, career) as client:
        missing_csrf = client.post(
            "/api/v1/skills",
            json={"name": "Research", "category": None, "proficiency": None},
            headers={"Origin": _ORIGIN},
        )
    assert missing_csrf.status_code == 403
    career_mock = identity.verify_csrf
    career_mock.assert_not_awaited()


def test_career_wire_validation_rejects_invented_dates_and_attachment_shortcuts(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, career, state, _ = _services(owner_id)
    with _authenticated_client(settings, fake_database, identity, career) as client:
        invented_day = client.post(
            "/api/v1/experiences",
            json={
                "employer": "Fictional Ltd",
                "officialTitle": "Researcher",
                "startDate": "2024-04-01",
                "current": True,
                "skillIds": [],
            },
            headers=_write_headers(),
        )
        shortcut = client.post(
            "/api/v1/evidence",
            json={
                "type": "supporting_document",
                "title": "Unsafe shortcut",
                "description": "Must use the private attachment workflow.",
                "source": {"sourceType": "attachment"},
                "metrics": [],
                "experienceIds": [],
                "skillIds": [],
                "attachmentIds": [str(uuid4())],
            },
            headers=_write_headers(),
        )
    assert invented_day.status_code == 422
    assert shortcut.status_code == 422
    assert not state.entities
    assert not state.evidence


def test_production_composition_builds_career_and_attachment_services(
    settings: Settings,
) -> None:
    database = Database(
        DatabaseOptions(
            url=settings.database_url.get_secret_value(),
            pool_size=1,
            max_overflow=0,
        )
    )
    identity = create_autospec(IdentityService, instance=True)
    resume_health = create_autospec(ResumeHealthService, instance=True)

    application = create_app(
        settings,
        database=database,
        identity=identity,
        resume_health=resume_health,
    )
    with TestClient(application):
        assert isinstance(application.state.career_record_service, CareerRecordService)
        assert isinstance(
            application.state.attachment_workflow_service,
            AttachmentWorkflowService,
        )
