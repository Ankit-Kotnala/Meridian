"""Authenticated Phase 3 HTTP workflow and ownership contract tests."""

import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import create_autospec
from uuid import uuid4

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.career_record.application import (
    AttachmentWorkflowService,
    CareerRecordService,
    ValidatedResumeSource,
)
from careeros.modules.career_record.domain import (
    CareerEntity,
    CareerEntityKind,
    EmploymentType,
    PartialDate,
    SemanticCandidateKind,
    SemanticImportAnchor,
    SemanticImportField,
    SemanticImportFieldState,
    ValidatedSemanticCandidate,
    exact_claim_sha256,
)
from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.application.models import CurrentUser
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.identity.domain.errors import AuthenticationRequired
from careeros.modules.resume_health.application import ResumeHealthService
from fastapi.testclient import TestClient

from careeros_api.career_record_routes import _matches_accepted_proposal
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


def _services(owner_id, sources: FakeResumeSourceQuery | None = None):
    identity = create_autospec(IdentityService, instance=True)
    principal = _principal(owner_id)
    identity.authenticate.return_value = principal
    identity.get_current_user.return_value = _user(owner_id)
    state = MemoryCareerRecord()
    career = CareerRecordService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        resume_sources=sources or FakeResumeSourceQuery(),
    )
    return identity, career, state, principal


def _semantic_candidate(document_id, snapshot_id) -> ValidatedSemanticCandidate:
    def field(
        name: str,
        value: str,
        *,
        field_type: str = "text",
        date_precision: str | None = None,
    ) -> SemanticImportField:
        return SemanticImportField(
            semantic_field_id=uuid4(),
            name=name,
            field_type=field_type,
            value=value,
            review_state=SemanticImportFieldState.CONFIRMED,
            confidence_basis_points=9_000,
            date_precision=date_precision,
            anchors=(
                SemanticImportAnchor(
                    block_id=uuid4(),
                    page=1,
                    start_offset=10,
                    end_offset=10 + len(value),
                    source_sha256=exact_claim_sha256("reviewed resume"),
                    source_excerpt=value,
                ),
            ),
        )

    return ValidatedSemanticCandidate(
        document_id=document_id,
        snapshot_id=snapshot_id,
        snapshot_revision=2,
        schema_version="canonical-semantics/1.0.0",
        parser_version="local-semantic/1",
        semantic_entity_id=uuid4(),
        kind=SemanticCandidateKind.EXPERIENCE,
        fields=(
            field("title", "Software Engineer"),
            field("employer", "Example Corp"),
            field(
                "start_date",
                "2024-01",
                field_type="date",
                date_precision="month",
            ),
        ),
    )


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
        assert skill.json()["userConfirmed"] is False
        skill_id = skill.json()["id"]
        confirmed_skill = client.post(
            f"/api/v1/skills/{skill_id}/confirm",
            headers=_write_headers(version=skill.json()["version"]),
        )
        assert confirmed_skill.status_code == 200
        assert confirmed_skill.json()["userConfirmed"] is True

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
        assert experience.json()["userConfirmed"] is False
        experience_id = experience.json()["id"]
        confirmed_experience = client.post(
            f"/api/v1/experiences/{experience_id}/confirm",
            headers=_write_headers(version=experience.json()["version"]),
        )
        assert confirmed_experience.status_code == 200
        assert confirmed_experience.json()["userConfirmed"] is True
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
        hidden_confirmation = client.post(
            f"/api/v1/experiences/{experience_id}/confirm",
            headers=_write_headers(version=3),
        )
        assert hidden.status_code == 404
        assert hidden_confirmation.status_code == 404

    assert len(state.entity_skill_links) == 1
    assert principal.user_id == owner_id


def test_semantic_import_http_flow_is_typed_idempotent_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    sources = FakeResumeSourceQuery()
    candidate = _semantic_candidate(document_id, snapshot_id)
    sources.add_semantic(owner_id, document_id, snapshot_id, (candidate,))
    identity, career, state, _ = _services(owner_id, sources)

    with _authenticated_client(settings, fake_database, identity, career) as client:
        assert client.get("/api/v1/career-profile").status_code == 200
        created = client.post(
            "/api/v1/career-profile/semantic-import-proposals",
            json={
                "documentId": str(document_id),
                "snapshotId": str(snapshot_id),
            },
            headers=_write_headers(),
        )
        assert created.status_code == 201
        body = created.json()
        assert body["questions"] == []
        proposal = body["proposals"][0]
        assert proposal["target"] == "entity"
        assert proposal["status"] == "pending"
        assert proposal["sourceAvailable"] is True
        assert proposal["fields"][0]["anchors"][0]["digest"].startswith("sha256:")
        assert (
            proposal["fields"][0]["anchors"][0]["excerpt"] == proposal["fields"][0]["proposedValue"]
        )
        assert state.entities == {}

        proposal_id = proposal["id"]
        values = {item["id"]: item["proposedValue"] for item in proposal["fields"]}
        missing_idempotency = client.post(
            f"/api/v1/career-profile/semantic-import-proposals/{proposal_id}/accept",
            json={"values": values},
            headers=_write_headers(version=proposal["version"]),
        )
        assert missing_idempotency.status_code == 422

        accepted = client.post(
            f"/api/v1/career-profile/semantic-import-proposals/{proposal_id}/accept",
            json={"values": values},
            headers=_write_headers(version=proposal["version"], idempotency=True),
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"
        assert len(state.entities) == 1
        imported = client.get("/api/v1/experiences")
        assert imported.status_code == 200
        assert imported.json()["data"][0]["userConfirmed"] is True
        assert imported.json()["data"][0]["provenance"]
        replay = client.post(
            f"/api/v1/career-profile/semantic-import-proposals/{proposal_id}/accept",
            json={"values": values},
            headers=_write_headers(version=proposal["version"], idempotency=True),
        )
        assert replay.status_code == 200
        assert len(state.entities) == 1

        identity.authenticate.return_value = _principal(uuid4())
        denied = client.get(f"/api/v1/career-profile/semantic-import-proposals/{proposal_id}")
        assert denied.status_code == 404


def test_personal_fact_http_flow_requires_confirmation_and_owner_scope(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, career, _state, _ = _services(owner_id)
    with _authenticated_client(settings, fake_database, identity, career) as client:
        assert client.get("/api/v1/career-profile").status_code == 200
        invalid = client.post(
            "/api/v1/personal-facts",
            json={
                "kind": "email",
                "value": "not-an-email",
                "label": None,
                "isPrimary": True,
            },
            headers=_write_headers(),
        )
        assert invalid.status_code == 422
        created = client.post(
            "/api/v1/personal-facts",
            json={
                "kind": "email",
                "value": "alex@example.test",
                "label": "Work",
                "isPrimary": True,
            },
            headers=_write_headers(),
        )
        assert created.status_code == 201
        assert created.json()["confirmation"] == "needs_review"
        fact_id = created.json()["id"]
        confirmed = client.post(
            f"/api/v1/personal-facts/{fact_id}/confirm",
            headers=_write_headers(version=created.json()["version"]),
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["confirmation"] == "confirmed"
        edited = client.patch(
            f"/api/v1/personal-facts/{fact_id}",
            json={
                "value": "alex.updated@example.test",
                "label": "Work",
                "isPrimary": True,
            },
            headers=_write_headers(version=confirmed.json()["version"]),
        )
        assert edited.status_code == 200
        assert edited.json()["confirmation"] == "needs_review"

        identity.authenticate.return_value = _principal(uuid4())
        hidden = client.post(
            f"/api/v1/personal-facts/{fact_id}/confirm",
            headers=_write_headers(version=edited.json()["version"]),
        )
        assert hidden.status_code == 404
        identity.authenticate.return_value = _principal(owner_id)
        deleted = client.delete(
            f"/api/v1/personal-facts/{fact_id}",
            headers=_write_headers(version=edited.json()["version"]),
        )
        assert deleted.status_code == 204
        assert client.get("/api/v1/personal-facts").json()["data"] == []


def test_experience_project_relationship_is_explicit_and_owner_scoped(
    settings: Settings, fake_database: FakeDatabase
) -> None:
    owner_id = uuid4()
    identity, career, _state, _ = _services(owner_id)
    with _authenticated_client(settings, fake_database, identity, career) as client:
        assert client.get("/api/v1/career-profile").status_code == 200
        experience = client.post(
            "/api/v1/experiences",
            json={
                "employer": "Example Corp",
                "officialTitle": "Engineer",
                "startDate": "2024-01",
                "current": True,
            },
            headers=_write_headers(),
        )
        project = client.post(
            "/api/v1/career-items",
            json={
                "kind": "project",
                "title": "Fictional project",
                "organization": None,
                "description": "",
                "startDate": None,
                "endDate": None,
                "url": None,
            },
            headers=_write_headers(),
        )
        assert experience.status_code == 201
        assert project.status_code == 201
        linked = client.post(
            "/api/v1/career-relationships",
            json={
                "experienceId": experience.json()["id"],
                "projectId": project.json()["id"],
                "kind": "experience_project",
            },
            headers=_write_headers(),
        )
        assert linked.status_code == 201
        assert client.get("/api/v1/career-relationships").json()["data"] == [linked.json()]

        identity.authenticate.return_value = _principal(uuid4())
        hidden = client.delete(
            f"/api/v1/career-relationships/{linked.json()['id']}",
            headers=_write_headers(),
        )
        assert hidden.status_code == 404
        identity.authenticate.return_value = _principal(owner_id)
        deleted = client.delete(
            f"/api/v1/career-relationships/{linked.json()['id']}",
            headers=_write_headers(),
        )
        assert deleted.status_code == 204
        assert client.get("/api/v1/career-relationships").json()["data"] == []


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


def test_resume_source_evidence_binds_the_exact_claim_before_persistence(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    owner_id = uuid4()
    identity = create_autospec(IdentityService, instance=True)
    principal = _principal(owner_id)
    identity.authenticate.return_value = principal
    identity.get_current_user.return_value = _user(owner_id)
    state = MemoryCareerRecord()
    sources = FakeResumeSourceQuery()
    document_id, snapshot_id, block_id = (uuid4() for _ in range(3))
    statement = "Built a deterministic fictional reporting workflow."
    sources.add(
        owner_id,
        ValidatedResumeSource(
            document_id=document_id,
            snapshot_id=snapshot_id,
            snapshot_revision=1,
            schema_version="canonical-resume/1.0.0",
            parser_version="local/1",
            block_id=block_id,
            page=1,
            start_offset=10,
            end_offset=62,
            source_sha256=exact_claim_sha256(statement),
            review_excerpt=statement,
        ),
    )
    career = CareerRecordService(
        unit_of_work=state,
        clock=FixedClock(),
        identifiers=UuidFactory(),
        resume_sources=sources,
    )
    source_payload = {
        "sourceType": "resume",
        "documentId": str(document_id),
        "snapshotId": str(snapshot_id),
        "blockId": str(block_id),
        "page": 1,
        "start": 10,
        "end": 62,
        "url": None,
    }
    with _authenticated_client(settings, fake_database, identity, career) as client:
        exact = client.post(
            "/api/v1/evidence",
            json={
                "type": "resume_statement",
                "title": "Client-controlled label",
                "description": statement,
                "source": source_payload,
                "metrics": [],
                "experienceIds": [],
                "skillIds": [],
                "attachmentIds": [],
            },
            headers=_write_headers(),
        )
        evidence_count = len(state.evidence)
        audit_count = len(state.audits)
        spoofed = client.post(
            "/api/v1/evidence",
            json={
                "type": "resume_statement",
                "title": "Kubernetes",
                "description": "Led an unrelated Kubernetes migration.",
                "source": source_payload,
                "metrics": [],
                "experienceIds": [],
                "skillIds": [],
                "attachmentIds": [],
            },
            headers=_write_headers(),
        )

    assert exact.status_code == 201
    assert exact.json()["title"] == statement
    assert exact.json()["state"] == "supported"
    assert exact.json()["factualEligible"] is True
    assert spoofed.status_code == 409
    assert spoofed.json()["code"] == "career_record_source_unavailable"
    assert len(state.evidence) == evidence_count
    assert len(state.audits) == audit_count


def test_legacy_import_context_is_removed_after_a_factual_entity_edit() -> None:
    owner_id, profile_id, entity_id = (uuid4() for _ in range(3))
    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    accepted = CareerEntity(
        id=entity_id,
        owner_user_id=owner_id,
        profile_id=profile_id,
        kind=CareerEntityKind.EXPERIENCE,
        title="Fictional Engineer",
        organization="Example Corp",
        description="Built a fictional workflow.",
        official_title="Fictional Engineer",
        display_title=None,
        employment_type=EmploymentType.FULL_TIME,
        location=None,
        external_url=None,
        start_date=PartialDate(2024, 1),
        end_date=None,
        is_current=True,
        sort_order=0,
        group_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )

    assert _matches_accepted_proposal(accepted, accepted)
    assert not _matches_accepted_proposal(
        replace(accepted, title="Edited title", version=2),
        accepted,
    )


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
