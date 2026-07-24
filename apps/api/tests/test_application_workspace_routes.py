"""Authenticated Phase 8 application-workspace HTTP contract tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from careeros.modules.application_workspace.application import (
    UNSET,
    ApplicationCalendarEntry,
    ApplicationPackView,
    ApplicationSummary,
    ApplicationWorkspaceService,
    Page,
    PagedResult,
    UnsetType,
)
from careeros.modules.application_workspace.domain import (
    ApplicationClaimEvidenceLink,
    ApplicationDocument,
    ApplicationDocumentClaim,
    ApplicationDocumentKind,
    ApplicationDocumentStatus,
    ApplicationEvent,
    ApplicationEventKind,
    ApplicationEvidencePin,
    ApplicationNote,
    ApplicationPack,
    ApplicationPackStatus,
    ApplicationRecord,
    ApplicationRequirementSnapshot,
    ApplicationStage,
    ApplicationTask,
    ApplicationWorkspaceNotFound,
    ApplicationWorkspaceVersionConflict,
    ConsistencyStatus,
    OutcomeStatus,
    ReferralStatus,
)
from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_NOW = datetime(2026, 7, 24, 18, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SampleApplication:
    owner_id: UUID
    other_id: UUID
    application_id: UUID
    task_id: UUID
    note_id: UUID
    event_id: UUID
    pack_id: UUID
    document_id: UUID
    summary: ApplicationSummary
    task: ApplicationTask
    note: ApplicationNote
    event: ApplicationEvent
    pack: ApplicationPackView
    deleted_document: ApplicationDocument
    calendar: ApplicationCalendarEntry


def _principal(user_id: UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _sample() -> SampleApplication:
    owner_id = uuid4()
    other_id = uuid4()
    application_id = uuid4()
    task_id = uuid4()
    note_id = uuid4()
    event_id = uuid4()
    pack_id = uuid4()
    document_id = uuid4()
    requirement = ApplicationRequirementSnapshot(
        id=uuid4(),
        requirement_type="responsibility",
        importance="mandatory",
        text="Lead a cross-functional product program.",
        source_start=0,
        source_end=40,
    )
    statement = "Led a cross-functional product program."
    pin = ApplicationEvidencePin(
        evidence_id=uuid4(),
        evidence_revision_id=uuid4(),
        revision_number=2,
        statement=statement,
        statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        strength="confirmed",
        has_numeric_claim=False,
    )
    claim = ApplicationDocumentClaim(
        id=uuid4(),
        text=statement,
        evidence_links=(
            ApplicationClaimEvidenceLink(
                evidence_id=pin.evidence_id,
                evidence_revision_id=pin.evidence_revision_id,
            ),
        ),
        requirement_ids=(requirement.id,),
    )
    record = ApplicationRecord(
        id=application_id,
        owner_user_id=owner_id,
        job_id=uuid4(),
        job_version=3,
        job_title="Principal Product Engineer",
        company="Example Co",
        location="Remote",
        job_analysis_id=uuid4(),
        job_source_sha256="a" * 64,
        job_requirements=(requirement,),
        requirement_support=(),
        resume_id=uuid4(),
        resume_version_id=uuid4(),
        resume_version_number=4,
        resume_title="Product engineering resume",
        resume_evidence_ids=(pin.evidence_id,),
        evidence_pins=(pin,),
        resume_claims=(claim,),
        source="referral",
        industry="Software",
        stage=ApplicationStage.PREPARING,
        application_deadline=date(2026, 8, 15),
        follow_up_at=date(2026, 8, 5),
        contacts=(),
        referral_status=ReferralStatus.REQUESTED,
        outcome_status=OutcomeStatus.NONE,
        rejection_reason=None,
        offer_summary=None,
        version=7,
        created_at=_NOW,
        updated_at=_NOW,
    )
    task = ApplicationTask(
        id=task_id,
        owner_user_id=owner_id,
        application_id=application_id,
        title="Ask for referral",
        due_at=date(2026, 8, 3),
        completed_at=None,
        version=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    note = ApplicationNote(
        id=note_id,
        owner_user_id=owner_id,
        application_id=application_id,
        body="Recruiter prefers a concise portfolio.",
        created_at=_NOW,
    )
    event = ApplicationEvent(
        id=event_id,
        owner_user_id=owner_id,
        application_id=application_id,
        event_kind=ApplicationEventKind.CONTACT,
        occurred_at=_NOW,
        title="Spoke with recruiter",
        description=None,
        metadata={"channel": "email"},
        created_at=_NOW,
    )
    document = ApplicationDocument(
        id=document_id,
        owner_user_id=owner_id,
        application_id=application_id,
        pack_id=pack_id,
        kind=ApplicationDocumentKind.COVER_LETTER,
        title="Grounded cover letter",
        body=statement,
        source_evidence_ids=(pin.evidence_id,),
        source_requirement_ids=(requirement.id,),
        claims=(claim,),
        status=ApplicationDocumentStatus.GENERATED,
        consistency_status=ConsistencyStatus.PASSED,
        consistency_findings=(),
        content_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        created_at=_NOW,
    )
    pack_record = ApplicationPack(
        id=pack_id,
        owner_user_id=owner_id,
        application_id=application_id,
        job_id=record.job_id,
        job_version=record.job_version,
        resume_version_id=record.resume_version_id,
        resume_version_number=record.resume_version_number,
        application_version=record.version,
        evidence_revision_ids=(pin.evidence_revision_id,),
        requirement_ids=(requirement.id,),
        status=ApplicationPackStatus.GENERATED,
        consistency_status=ConsistencyStatus.PASSED,
        consistency_findings=(),
        idempotency_key="pack-create-key",
        idempotency_fingerprint="b" * 64,
        created_at=_NOW,
    )
    pack = ApplicationPackView(pack=pack_record, documents=(document,))
    summary = ApplicationSummary(
        application=record,
        task_count=1,
        open_task_count=1,
        note_count=1,
        event_count=1,
        pack_count=1,
    )
    deleted_document = replace(
        document,
        title="[deleted]",
        body="[deleted]",
        content_sha256=hashlib.sha256(b"[deleted]").hexdigest(),
        source_evidence_ids=(),
        source_requirement_ids=(),
        claims=(),
        status=ApplicationDocumentStatus.DELETED,
        consistency_status=ConsistencyStatus.PASSED,
        consistency_findings=(),
        deleted_at=_NOW,
    )
    calendar = ApplicationCalendarEntry(
        id=task.id,
        application_id=application_id,
        kind="task",
        title=task.title,
        on_date=task.due_at or date(2026, 8, 3),
        completed=False,
    )
    return SampleApplication(
        owner_id=owner_id,
        other_id=other_id,
        application_id=application_id,
        task_id=task_id,
        note_id=note_id,
        event_id=event_id,
        pack_id=pack_id,
        document_id=document_id,
        summary=summary,
        task=task,
        note=note,
        event=event,
        pack=pack,
        deleted_document=deleted_document,
        calendar=calendar,
    )


def _services(
    sample: SampleApplication,
) -> tuple[IdentityService, ApplicationWorkspaceService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(sample.owner_id)
    service = create_autospec(ApplicationWorkspaceService, instance=True)
    service.list_applications.return_value = PagedResult(
        data=(sample.summary,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.list_calendar.return_value = (sample.calendar,)
    service.get_application.return_value = sample.summary
    service.create_application.return_value = sample.summary
    service.update_application.return_value = sample.summary
    service.delete_application.return_value = None
    service.create_task.return_value = sample.task
    service.update_task.return_value = sample.task
    service.list_tasks.return_value = PagedResult(
        data=(sample.task,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_note.return_value = sample.note
    service.list_notes.return_value = PagedResult(
        data=(sample.note,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.record_event.return_value = sample.event
    service.list_events.return_value = PagedResult(
        data=(sample.event,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.generate_pack.return_value = sample.pack
    service.list_packs.return_value = PagedResult(
        data=(sample.pack.pack,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.get_pack.return_value = sample.pack
    service.delete_document.return_value = sample.deleted_document
    return identity, service


def _write_headers(
    *,
    version: int | None = None,
    idempotency: str | None = None,
) -> dict[str, str]:
    return {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        **({"If-Match": f'"{version}"'} if version is not None else {}),
        **({"Idempotency-Key": idempotency} if idempotency is not None else {}),
    }


def _client(
    settings: Settings,
    database: FakeDatabase,
    identity: IdentityService,
    service: ApplicationWorkspaceService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=database,
            identity=identity,
            application_workspace=service,
        )
    )
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
    return client


def test_application_workspace_complete_owner_scoped_http_workflow(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        listed = client.get(
            "/api/v1/applications",
            params={
                "q": " product ",
                "stage": "preparing",
                "outcome": "none",
                "source": "referral",
                "industry": "Software",
                "sort": "deadline_asc",
            },
        )
        assert listed.status_code == 200
        assert listed.headers["Cache-Control"] == "no-store"
        assert listed.json()["data"][0]["taskCount"] == 1
        list_filter = service.list_applications.await_args.args[1]
        assert list_filter.query == "product"
        assert list_filter.stage == ApplicationStage.PREPARING
        assert list_filter.outcome == OutcomeStatus.NONE
        assert list_filter.source == "referral"

        created = client.post(
            "/api/v1/applications",
            json={
                "jobId": str(sample.summary.application.job_id),
                "resumeVersionId": str(sample.summary.application.resume_version_id),
                "stage": "preparing",
                "source": "referral",
                "industry": "Software",
            },
            headers=_write_headers(idempotency="application-create-key"),
        )
        assert created.status_code == 201
        assert created.headers["ETag"] == '"7"'
        created_body = created.json()
        assert created_body["jobSourceSha256"] == "a" * 64
        assert created_body["jobRequirements"][0]["importance"] == "mandatory"
        assert created_body["evidencePins"][0]["strength"] == "confirmed"
        assert created_body["resumeClaims"][0]["evidenceLinks"][0]["evidenceRevisionId"]
        create_command = service.create_application.await_args.args[1]
        assert create_command.source == "referral"
        assert service.create_application.await_args.kwargs["idempotency_key"] == (
            "application-create-key"
        )

        detail = client.get(f"/api/v1/applications/{sample.application_id}")
        assert detail.status_code == 200
        assert detail.headers["ETag"] == '"7"'
        assert detail.json()["eventCount"] == 1
        assert {"tasks", "notes", "events", "packs"}.isdisjoint(detail.json())
        service.get_application.assert_awaited_with(sample.owner_id, sample.application_id)

        updated = client.patch(
            f"/api/v1/applications/{sample.application_id}",
            json={
                "applicationDeadline": None,
                "contacts": [],
                "source": None,
            },
            headers=_write_headers(version=7),
        )
        assert updated.status_code == 200
        update_command = service.update_application.await_args.args[2]
        assert update_command.application_deadline is None
        assert update_command.contacts == ()
        assert update_command.source is None
        assert update_command.industry is UNSET
        assert isinstance(update_command.resume_version_id, UnsetType)
        assert service.update_application.await_args.kwargs["expected_version"] == 7

        moved = client.patch(
            f"/api/v1/applications/{sample.application_id}/stage",
            json={"stage": "applied"},
            headers=_write_headers(version=7),
        )
        assert moved.status_code == 200
        stage_command = service.update_application.await_args.args[2]
        assert stage_command.stage == ApplicationStage.APPLIED
        assert stage_command.outcome_status is UNSET

        tasks = client.get(
            f"/api/v1/applications/{sample.application_id}/tasks",
            params={"limit": 25},
        )
        assert tasks.status_code == 200
        assert tasks.json()["data"][0]["title"] == "Ask for referral"
        assert tasks.json()["page"] == {
            "limit": 25,
            "hasMore": False,
            "nextCursor": None,
        }
        service.list_tasks.assert_awaited_with(
            sample.owner_id,
            sample.application_id,
            cursor=None,
            limit=25,
        )
        task_created = client.post(
            f"/api/v1/applications/{sample.application_id}/tasks",
            json={"title": "Ask for referral", "dueAt": "2026-08-03"},
            headers=_write_headers(idempotency="application-task-key"),
        )
        assert task_created.status_code == 201
        assert task_created.headers["ETag"] == '"2"'
        task_updated = client.patch(
            f"/api/v1/applications/{sample.application_id}/tasks/{sample.task_id}",
            json={"dueAt": None, "completed": True},
            headers=_write_headers(version=2),
        )
        assert task_updated.status_code == 200
        task_command = service.update_task.await_args.args[3]
        assert task_command.due_at is None
        assert task_command.completed is True
        assert task_command.title is UNSET
        assert service.update_task.await_args.args[1:3] == (
            sample.application_id,
            sample.task_id,
        )

        notes = client.get(f"/api/v1/applications/{sample.application_id}/notes")
        assert notes.status_code == 200
        assert notes.json()["data"][0]["body"].startswith("Recruiter")
        note_created = client.post(
            f"/api/v1/applications/{sample.application_id}/notes",
            json={"body": "Recruiter prefers a concise portfolio."},
            headers=_write_headers(idempotency="application-note-key"),
        )
        assert note_created.status_code == 201

        events = client.get(f"/api/v1/applications/{sample.application_id}/events")
        assert events.status_code == 200
        assert events.json()["page"]["limit"] == 25
        event_created = client.post(
            f"/api/v1/applications/{sample.application_id}/events",
            json={
                "eventKind": "contact",
                "occurredAt": "2026-07-24T18:00:00Z",
                "title": "Spoke with recruiter",
                "metadata": {"channel": "email"},
            },
            headers=_write_headers(idempotency="application-event-key"),
        )
        assert event_created.status_code == 201

        generated = client.post(
            f"/api/v1/applications/{sample.application_id}/application-packs",
            json={"includeKinds": ["cover_letter"]},
            headers=_write_headers(idempotency="application-pack-key"),
        )
        assert generated.status_code == 201
        generated_body = generated.json()
        assert generated_body["applicationVersion"] == 7
        assert generated_body["evidenceRevisionIds"]
        assert generated_body["documents"][0]["sourceRequirementIds"]
        packs = client.get(
            f"/api/v1/applications/{sample.application_id}/application-packs",
            params={"limit": 25},
        )
        assert packs.status_code == 200
        assert packs.json()["data"][0]["id"] == str(sample.pack_id)
        assert "documents" not in packs.json()["data"][0]
        pack = client.get(f"/api/v1/application-packs/{sample.pack_id}")
        assert pack.status_code == 200
        consistency = client.get(f"/api/v1/application-packs/{sample.pack_id}/consistency")
        assert consistency.status_code == 200
        assert consistency.json()["status"] == "passed"

        calendar = client.get(
            "/api/v1/applications/calendar",
            params={"start": "2026-08-01", "end": "2026-08-31"},
        )
        assert calendar.status_code == 200
        assert calendar.json()["data"] == [
            {
                "id": str(sample.task_id),
                "applicationId": str(sample.application_id),
                "kind": "task",
                "title": "Ask for referral",
                "onDate": "2026-08-03",
                "completed": False,
            }
        ]

        deleted_document = client.delete(
            (f"/api/v1/applications/{sample.application_id}/documents/{sample.document_id}"),
            headers=_write_headers(),
        )
        assert deleted_document.status_code == 204
        assert deleted_document.content == b""
        assert service.delete_document.await_args.args[1:3] == (
            sample.application_id,
            sample.document_id,
        )

        deleted = client.delete(
            f"/api/v1/applications/{sample.application_id}",
            headers=_write_headers(version=7),
        )
        assert deleted.status_code == 204
        service.delete_application.assert_awaited_once()

        identity.authenticate.return_value = _principal(sample.other_id)
        service.get_application.side_effect = ApplicationWorkspaceNotFound
        hidden = client.get(f"/api/v1/applications/{sample.application_id}")
        assert hidden.status_code == 404
        assert hidden.json()["code"] == "application_workspace_not_found"
        service.get_application.assert_awaited_with(sample.other_id, sample.application_id)


def test_application_workspace_mutations_require_csrf_and_fail_safely(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        missing_csrf = client.post(
            "/api/v1/applications",
            json={
                "jobId": str(sample.summary.application.job_id),
                "resumeVersionId": str(sample.summary.application.resume_version_id),
            },
            headers={"Idempotency-Key": "application-create-key"},
        )
        assert missing_csrf.status_code == 403
        service.create_application.assert_not_awaited()

        invalid_patch = client.patch(
            f"/api/v1/applications/{sample.application_id}",
            json={},
            headers=_write_headers(version=7),
        )
        assert invalid_patch.status_code == 422

        invalid_calendar = client.get(
            "/api/v1/applications/calendar",
            params={"start": "2026-01-01", "end": "2027-02-01"},
        )
        assert invalid_calendar.status_code == 422
        assert invalid_calendar.headers["Cache-Control"] == "no-store"

        forged_system_event = client.post(
            f"/api/v1/applications/{sample.application_id}/events",
            json={
                "eventKind": "stage_changed",
                "title": "Forged lifecycle event",
            },
            headers=_write_headers(idempotency="forged-system-event"),
        )
        assert forged_system_event.status_code == 422
        service.record_event.assert_not_awaited()

        service.update_application.side_effect = ApplicationWorkspaceVersionConflict
        stale = client.patch(
            f"/api/v1/applications/{sample.application_id}/stage",
            json={"stage": "applied"},
            headers=_write_headers(version=6),
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "application_workspace_version_conflict"
        assert "6" not in stale.json()["detail"]
        assert stale.headers["Cache-Control"] == "no-store"


def test_application_workspace_openapi_is_complete_and_has_no_submission_surface(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    with _client(settings, fake_database, identity, service) as client:
        document = client.get("/openapi.json").json()

    paths = document["paths"]
    required = {
        "/api/v1/applications",
        "/api/v1/applications/calendar",
        "/api/v1/applications/{application_id}",
        "/api/v1/applications/{application_id}/stage",
        "/api/v1/applications/{application_id}/tasks",
        "/api/v1/applications/{application_id}/tasks/{task_id}",
        "/api/v1/applications/{application_id}/notes",
        "/api/v1/applications/{application_id}/events",
        "/api/v1/applications/{application_id}/application-packs",
        "/api/v1/application-packs/{pack_id}",
        "/api/v1/application-packs/{pack_id}/consistency",
        "/api/v1/applications/{application_id}/documents/{document_id}",
    }
    assert required.issubset(paths)
    application_paths = {path.lower() for path in paths if "application" in path.lower()}
    assert all("submit" not in path and "send" not in path for path in application_paths)
    operation_ids = [
        operation["operationId"]
        for methods in paths.values()
        for method, operation in methods.items()
        if method != "parameters"
    ]
    assert len(operation_ids) == len(set(operation_ids))
    schemas = document["components"]["schemas"]
    assert {
        "ApplicationTaskPageResponse",
        "ApplicationNotePageResponse",
        "ApplicationEventPageResponse",
        "ApplicationPackPageResponse",
        "ApplicationPackSummaryResponse",
    }.issubset(schemas)
    assert {"tasks", "notes", "events", "packs"}.isdisjoint(
        schemas["ApplicationResponse"]["properties"]
    )
    assert set(schemas["ApplicationEventCreateRequest"]["properties"]["eventKind"]["enum"]) == {
        "interview",
        "contact",
        "custom",
    }
