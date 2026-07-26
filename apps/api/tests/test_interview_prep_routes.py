"""Authenticated Phase 9 Interview Prep HTTP contract tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.interview_prep.application import (
    DefenseMap,
    DefenseMapEntry,
    FollowUpDraftReadView,
    GroundingAssessment,
    GroundingStatus,
    InterviewPrepService,
    Page,
    PagedResult,
    QuestionReadView,
    SessionReadView,
    SessionView,
    StoryReadView,
)
from careeros.modules.interview_prep.domain import (
    DefenseStatus,
    EvidenceRevisionPin,
    FollowUpDraft,
    InterviewPrepNotFound,
    InterviewPrepQuotaExceeded,
    InterviewPrepVersionConflict,
    InterviewQuestion,
    InterviewSession,
    InterviewSessionKind,
    InterviewSessionNote,
    QuestionKind,
    SessionContextClaim,
    SessionContextRequirement,
    SessionContextSnapshot,
    SessionNoteKind,
    StarStory,
    StoryClaimPin,
    StoryField,
    StoryOrigin,
    StoryStatus,
)
from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.main import create_app
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_NOW = datetime(2026, 7, 25, 3, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class InterviewPrepSample:
    owner_id: UUID
    other_id: UUID
    application_id: UUID
    story: StarStory
    defense_map: DefenseMap
    session: SessionView
    question: InterviewQuestion
    note: InterviewSessionNote
    draft: FollowUpDraft


def _principal(user_id: UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _context_digest(
    *,
    application_id: UUID,
    job_id: UUID,
    job_version: int,
    job_title: str,
    company: str | None,
    resume_version_id: UUID,
    resume_version_number: int,
    claims: tuple[SessionContextClaim, ...],
    requirements: tuple[SessionContextRequirement, ...],
) -> str:
    payload = {
        "applicationId": str(application_id),
        "jobId": str(job_id),
        "jobVersion": job_version,
        "jobTitle": job_title,
        "company": company,
        "resumeVersionId": str(resume_version_id),
        "resumeVersionNumber": resume_version_number,
        "claims": [
            {
                "id": str(claim.source_claim_id),
                "sha256": claim.text_sha256,
                "requirements": [str(item) for item in claim.requirement_ids],
                "evidence": [
                    {
                        "id": str(pin.evidence_id),
                        "revisionId": str(pin.evidence_revision_id),
                        "revision": pin.revision_number,
                        "sha256": pin.statement_sha256,
                    }
                    for pin in claim.evidence_pins
                ],
            }
            for claim in claims
        ],
        "requirements": [
            {
                "id": str(item.requirement_id),
                "text": item.text,
                "importance": item.importance,
            }
            for item in requirements
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sample() -> InterviewPrepSample:
    owner_id = uuid4()
    other_id = uuid4()
    application_id = uuid4()
    story_id = uuid4()
    session_id = uuid4()
    requirement_id = uuid4()
    claim_id = uuid4()
    statement = "Led a cross-functional launch with verified ownership."
    pin = EvidenceRevisionPin(
        evidence_id=uuid4(),
        evidence_revision_id=uuid4(),
        revision_number=4,
        statement=statement,
        statement_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        strength="verified",
        has_numeric_claim=False,
    )
    claim_pin = StoryClaimPin(
        source_claim_id=claim_id,
        claim_text=statement,
        claim_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        strong=True,
        field_names=(
            StoryField.SITUATION,
            StoryField.TASK,
            StoryField.ACTION,
            StoryField.RESULT,
            StoryField.PERSONAL_CONTRIBUTION,
        ),
        evidence_pins=(pin,),
    )
    story = StarStory(
        id=story_id,
        owner_user_id=owner_id,
        application_id=application_id,
        title="Cross-functional launch",
        situation="A launch required coordinated ownership.",
        task="Lead the cross-functional work.",
        action="I coordinated the launch and its decisions.",
        result="The launch completed with verified ownership.",
        personal_contribution="I led coordination and decision tracking.",
        metric_explanation=None,
        confidence=4,
        follow_up_questions=("How did you resolve trade-offs?",),
        status=StoryStatus.READY,
        origin=StoryOrigin.USER_AUTHORED,
        claim_pins=(claim_pin,),
        version=3,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defense_map = DefenseMap(
        application_id=application_id,
        entries=(
            DefenseMapEntry(
                claim_id=claim_id,
                claim_text=statement,
                strong=True,
                status=DefenseStatus.DEFENDED,
                story_ids=(story_id,),
                evidence_revision_ids=(pin.evidence_revision_id,),
                warning=None,
            ),
        ),
        defended_count=1,
        partial_count=0,
        undefended_count=0,
        strong_claim_warning_count=0,
    )
    session_claim = SessionContextClaim(
        source_claim_id=claim_id,
        text=statement,
        text_sha256=hashlib.sha256(statement.encode()).hexdigest(),
        strong=True,
        requirement_ids=(requirement_id,),
        evidence_pins=(pin,),
    )
    requirement = SessionContextRequirement(
        requirement_id=requirement_id,
        text="Lead cross-functional product delivery.",
        importance="mandatory",
    )
    job_id = uuid4()
    resume_version_id = uuid4()
    context = SessionContextSnapshot(
        application_id=application_id,
        job_id=job_id,
        job_version=2,
        job_title="Principal Product Engineer",
        company="Example Co",
        resume_version_id=resume_version_id,
        resume_version_number=5,
        claims=(session_claim,),
        requirements=(requirement,),
        snapshot_sha256=_context_digest(
            application_id=application_id,
            job_id=job_id,
            job_version=2,
            job_title="Principal Product Engineer",
            company="Example Co",
            resume_version_id=resume_version_id,
            resume_version_number=5,
            claims=(session_claim,),
            requirements=(requirement,),
        ),
    )
    session_record = InterviewSession(
        id=session_id,
        owner_user_id=owner_id,
        application_id=application_id,
        title="Hiring manager preparation",
        kind=InterviewSessionKind.HIRING_MANAGER,
        scheduled_at=datetime(2026, 8, 1, 10, tzinfo=UTC),
        context=context,
        version=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session = SessionView(
        session=session_record,
        question_count=1,
        note_count=1,
        follow_up_draft_count=1,
    )
    question = InterviewQuestion(
        id=uuid4(),
        owner_user_id=owner_id,
        session_id=session_id,
        ordinal=1,
        prompt="How did you lead cross-functional product delivery?",
        kind=QuestionKind.ROLE_SPECIFIC,
        source_requirement_ids=(requirement_id,),
        source_claim_ids=(claim_id,),
        generated=True,
        created_at=_NOW,
    )
    note = InterviewSessionNote(
        id=uuid4(),
        owner_user_id=owner_id,
        session_id=session_id,
        kind=SessionNoteKind.REFLECTION,
        body="Clarify how decisions were made.",
        version=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    subject = "Thank you - Principal Product Engineer"
    body = f"Thank you. A grounded point from my background: {statement}"
    draft = FollowUpDraft(
        id=uuid4(),
        owner_user_id=owner_id,
        session_id=session_id,
        subject=subject,
        body=body,
        source_claims=(session_claim,),
        content_sha256=hashlib.sha256(f"{subject}\n{body}".encode()).hexdigest(),
        created_at=_NOW,
    )
    return InterviewPrepSample(
        owner_id=owner_id,
        other_id=other_id,
        application_id=application_id,
        story=story,
        defense_map=defense_map,
        session=session,
        question=question,
        note=note,
        draft=draft,
    )


def _services(
    sample: InterviewPrepSample,
) -> tuple[IdentityService, InterviewPrepService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal(sample.owner_id)
    service = create_autospec(InterviewPrepService, instance=True)
    current = GroundingAssessment(GroundingStatus.CURRENT)
    service.list_story_reads.return_value = PagedResult(
        data=(StoryReadView(sample.story, current),),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_story.return_value = sample.story
    service.get_story_read.return_value = StoryReadView(sample.story, current)
    service.update_story.return_value = sample.story
    service.delete_story.return_value = None
    service.defense_map.return_value = sample.defense_map
    service.list_session_reads.return_value = PagedResult(
        data=(SessionReadView(sample.session, current),),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_session.return_value = sample.session
    service.get_session_read.return_value = SessionReadView(sample.session, current)
    service.update_session.return_value = sample.session
    service.delete_session.return_value = None
    service.list_question_reads.return_value = PagedResult(
        data=(QuestionReadView(sample.question, current),),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.get_question_read.return_value = QuestionReadView(sample.question, current)
    service.create_question.return_value = sample.question
    service.generate_question_bank.return_value = (sample.question,)
    service.list_notes.return_value = PagedResult(
        data=(sample.note,),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.create_note.return_value = sample.note
    service.update_note.return_value = sample.note
    service.delete_note.return_value = None
    service.list_follow_up_draft_reads.return_value = PagedResult(
        data=(FollowUpDraftReadView(sample.draft, current),),
        page=Page(limit=25, has_more=False, next_cursor=None),
    )
    service.get_follow_up_draft_read.return_value = FollowUpDraftReadView(
        sample.draft,
        current,
    )
    service.generate_follow_up_draft.return_value = sample.draft
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
    service: InterviewPrepService,
) -> TestClient:
    app = create_app(
        settings,
        database=database,
        identity=identity,
        interview_prep=service,
    )
    client = TestClient(app)
    client.cookies.set("careeros_session", "opaque-session")
    client.cookies.set("careeros_csrf", "opaque-csrf")
    return client


def _story_payload(sample: InterviewPrepSample) -> dict[str, object]:
    claim = sample.story.claim_pins[0]
    return {
        "applicationId": str(sample.application_id),
        "title": sample.story.title,
        "situation": sample.story.situation,
        "task": sample.story.task,
        "action": sample.story.action,
        "result": sample.story.result,
        "personalContribution": sample.story.personal_contribution,
        "metricExplanation": sample.story.metric_explanation,
        "confidence": sample.story.confidence,
        "followUpQuestions": list(sample.story.follow_up_questions),
        "status": sample.story.status.value,
        "claimSelections": [
            {
                "claimId": str(claim.source_claim_id),
                "fieldNames": [field.value for field in claim.field_names],
            }
        ],
    }


def _session_payload(sample: InterviewPrepSample) -> dict[str, object]:
    return {
        "applicationId": str(sample.application_id),
        "title": sample.session.session.title,
        "kind": sample.session.session.kind.value,
        "scheduledAt": sample.session.session.scheduled_at.isoformat()
        if sample.session.session.scheduled_at is not None
        else None,
    }


def test_interview_prep_complete_owner_scoped_http_workflow(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        stories = client.get(
            "/api/v1/interview-prep/stories",
            params={
                "applicationId": str(sample.application_id),
                "status": "ready",
                "cursor": "eyJvZmZzZXQiOjI1fQ",
                "limit": 25,
            },
        )
        assert stories.status_code == 200
        assert stories.headers["Cache-Control"] == "no-store"
        assert stories.json()["page"] == {
            "limit": 25,
            "hasMore": False,
            "nextCursor": None,
        }
        assert stories.json()["data"][0]["claimCount"] == 1
        assert stories.json()["data"][0]["groundingStatus"] == "current"
        story_filter = service.list_story_reads.await_args.args[1]
        assert story_filter.application_id == sample.application_id
        assert story_filter.status is StoryStatus.READY
        assert service.list_story_reads.await_args.kwargs == {
            "cursor": "eyJvZmZzZXQiOjI1fQ",
            "limit": 25,
        }

        created_story = client.post(
            "/api/v1/interview-prep/stories",
            json=_story_payload(sample),
            headers=_write_headers(idempotency="interview-story-create"),
        )
        assert created_story.status_code == 201
        assert created_story.headers["ETag"] == '"3"'
        assert "ownerUserId" not in created_story.json()
        story_command = service.create_story.await_args.args[1]
        assert story_command.origin is StoryOrigin.USER_AUTHORED
        assert story_command.claim_selections[0].field_names[0] is StoryField.SITUATION
        assert service.create_story.await_args.kwargs["idempotency_key"] == (
            "interview-story-create"
        )

        story_detail = client.get(f"/api/v1/interview-prep/stories/{sample.story.id}")
        assert story_detail.status_code == 200
        assert story_detail.headers["ETag"] == '"3"'
        assert story_detail.json()["origin"] == "user_authored"

        update_payload = _story_payload(sample)
        update_payload.pop("applicationId")
        story_updated = client.patch(
            f"/api/v1/interview-prep/stories/{sample.story.id}",
            json=update_payload,
            headers=_write_headers(version=3),
        )
        assert story_updated.status_code == 200
        assert service.update_story.await_args.kwargs["expected_version"] == 3

        defense = client.get(
            f"/api/v1/interview-prep/applications/{sample.application_id}/defense-map"
        )
        assert defense.status_code == 200
        assert defense.json()["entries"][0]["status"] == "defended"
        assert defense.json()["entries"][0]["evidenceRevisionIds"]

        sessions = client.get(
            "/api/v1/interview-prep/sessions",
            params={"applicationId": str(sample.application_id), "limit": 25},
        )
        assert sessions.status_code == 200
        assert sessions.json()["data"][0]["questionCount"] == 1
        assert sessions.json()["data"][0]["jobTitle"] == sample.session.session.context.job_title
        assert sessions.json()["data"][0]["groundingStatus"] == "current"
        assert {"notes", "questions", "followUpDrafts"}.isdisjoint(sessions.json()["data"][0])

        created_session = client.post(
            "/api/v1/interview-prep/sessions",
            json=_session_payload(sample),
            headers=_write_headers(idempotency="interview-session-create"),
        )
        assert created_session.status_code == 201
        assert created_session.headers["ETag"] == '"2"'
        assert service.create_session.await_args.args[1].kind is (
            InterviewSessionKind.HIRING_MANAGER
        )

        session_detail = client.get(f"/api/v1/interview-prep/sessions/{sample.session.session.id}")
        assert session_detail.status_code == 200
        assert session_detail.json()["context"]["claims"][0]["evidencePins"]

        session_update = _session_payload(sample)
        session_update.pop("applicationId")
        updated_session = client.patch(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}",
            json=session_update,
            headers=_write_headers(version=2),
        )
        assert updated_session.status_code == 200
        assert service.update_session.await_args.kwargs["expected_version"] == 2

        questions = client.get(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}/questions"
        )
        assert questions.status_code == 200
        assert questions.json()["data"][0]["generated"] is True
        assert questions.json()["data"][0]["sourceClaimCount"] == 1
        question_detail = client.get(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}"
            f"/questions/{sample.question.id}"
        )
        assert question_detail.status_code == 200
        assert question_detail.json()["sourceClaimIds"]
        question_created = client.post(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}/questions",
            json={
                "prompt": sample.question.prompt,
                "kind": "role_specific",
                "sourceRequirementIds": [str(sample.question.source_requirement_ids[0])],
                "sourceClaimIds": [str(sample.question.source_claim_ids[0])],
            },
            headers=_write_headers(idempotency="interview-question-create"),
        )
        assert question_created.status_code == 201
        assert service.create_question.await_args.args[2].kind is QuestionKind.ROLE_SPECIFIC
        generated_questions = client.post(
            (f"/api/v1/interview-prep/sessions/{sample.session.session.id}/questions/generate"),
            headers=_write_headers(idempotency="interview-question-bank"),
        )
        assert generated_questions.status_code == 201
        assert generated_questions.json()["data"][0]["sourceClaimIds"]

        notes = client.get(f"/api/v1/interview-prep/sessions/{sample.session.session.id}/notes")
        assert notes.status_code == 200
        assert notes.json()["data"][0]["kind"] == "reflection"
        created_note = client.post(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}/notes",
            json={"kind": "reflection", "body": sample.note.body},
            headers=_write_headers(idempotency="interview-note-create"),
        )
        assert created_note.status_code == 201
        assert created_note.headers["ETag"] == '"2"'
        updated_note = client.patch(
            (f"/api/v1/interview-prep/sessions/{sample.session.session.id}/notes/{sample.note.id}"),
            json={"kind": "private_note", "body": "Keep this owner-private."},
            headers=_write_headers(version=2),
        )
        assert updated_note.status_code == 200
        assert service.update_note.await_args.args[3].kind is SessionNoteKind.PRIVATE_NOTE
        assert service.update_note.await_args.kwargs["expected_version"] == 2

        drafts = client.get(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}/follow-up-drafts"
        )
        assert drafts.status_code == 200
        assert drafts.json()["data"][0]["sourceClaimCount"] == 1
        draft_detail = client.get(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}"
            f"/follow-up-drafts/{sample.draft.id}"
        )
        assert draft_detail.status_code == 200
        assert draft_detail.json()["sourceClaims"][0]["evidencePins"]
        generated_draft = client.post(
            (
                f"/api/v1/interview-prep/sessions/{sample.session.session.id}"
                "/follow-up-drafts/generate"
            ),
            json={"sourceClaimIds": [str(sample.question.source_claim_ids[0])]},
            headers=_write_headers(idempotency="interview-follow-up-draft"),
        )
        assert generated_draft.status_code == 201
        assert generated_draft.json()["contentSha256"] == sample.draft.content_sha256
        assert (
            service.generate_follow_up_draft.await_args.args[2].source_claim_ids
            == sample.question.source_claim_ids
        )

        deleted_note = client.delete(
            (f"/api/v1/interview-prep/sessions/{sample.session.session.id}/notes/{sample.note.id}"),
            headers=_write_headers(version=2),
        )
        assert deleted_note.status_code == 204
        assert deleted_note.content == b""

        deleted_session = client.delete(
            f"/api/v1/interview-prep/sessions/{sample.session.session.id}",
            headers=_write_headers(version=2),
        )
        assert deleted_session.status_code == 204

        deleted_story = client.delete(
            f"/api/v1/interview-prep/stories/{sample.story.id}",
            headers=_write_headers(version=3),
        )
        assert deleted_story.status_code == 204
        service.delete_story.assert_awaited_once_with(
            sample.owner_id,
            sample.story.id,
            expected_version=3,
            context=service.delete_story.await_args.kwargs["context"],
        )


def test_interview_prep_mutations_require_csrf_and_fail_safely(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)

    with _client(settings, fake_database, identity, service) as client:
        missing_csrf = client.post(
            "/api/v1/interview-prep/stories",
            json=_story_payload(sample),
            headers={"Idempotency-Key": "interview-story-create"},
        )
        assert missing_csrf.status_code == 403
        service.create_story.assert_not_awaited()

        duplicate_claim_payload = _story_payload(sample)
        selection = duplicate_claim_payload["claimSelections"]
        assert isinstance(selection, list)
        selection.append(selection[0])
        duplicate_claim = client.post(
            "/api/v1/interview-prep/stories",
            json=duplicate_claim_payload,
            headers=_write_headers(idempotency="interview-story-duplicate"),
        )
        assert duplicate_claim.status_code == 422
        service.create_story.assert_not_awaited()

        invalid_schedule = _session_payload(sample)
        invalid_schedule["scheduledAt"] = "2026-08-01T10:00:00"
        invalid_session = client.post(
            "/api/v1/interview-prep/sessions",
            json=invalid_schedule,
            headers=_write_headers(idempotency="interview-session-invalid"),
        )
        assert invalid_session.status_code == 422
        service.create_session.assert_not_awaited()

        invalid_if_match = client.patch(
            f"/api/v1/interview-prep/stories/{sample.story.id}",
            json={
                key: value
                for key, value in _story_payload(sample).items()
                if key != "applicationId"
            },
            headers={
                **_write_headers(),
                "If-Match": "3",
            },
        )
        assert invalid_if_match.status_code == 422
        assert invalid_if_match.json()["code"] == "interview_prep_validation_failed"
        assert invalid_if_match.headers["Cache-Control"] == "no-store"
        service.update_story.assert_not_awaited()

        service.update_story.side_effect = InterviewPrepVersionConflict
        stale = client.patch(
            f"/api/v1/interview-prep/stories/{sample.story.id}",
            json={
                key: value
                for key, value in _story_payload(sample).items()
                if key != "applicationId"
            },
            headers=_write_headers(version=2),
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "interview_prep_version_conflict"
        assert "2" not in stale.json()["detail"]

        service.create_story.side_effect = InterviewPrepQuotaExceeded("story limit reached")
        quota = client.post(
            "/api/v1/interview-prep/stories",
            json=_story_payload(sample),
            headers=_write_headers(idempotency="interview-story-quota"),
        )
        assert quota.status_code == 429
        assert quota.json()["code"] == "interview_prep_quota_exceeded"
        assert "story" not in quota.json()["detail"].casefold()

        identity.authenticate.return_value = _principal(sample.other_id)
        service.get_story_read.side_effect = InterviewPrepNotFound
        hidden = client.get(f"/api/v1/interview-prep/stories/{sample.story.id}")
        assert hidden.status_code == 404
        assert hidden.json()["code"] == "interview_prep_not_found"
        service.get_story_read.assert_awaited_with(sample.other_id, sample.story.id)


def test_interview_prep_openapi_is_complete_and_has_no_delivery_surface(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    sample = _sample()
    identity, service = _services(sample)
    with _client(settings, fake_database, identity, service) as client:
        document = client.get("/openapi.json").json()

    paths = document["paths"]
    required = {
        "/api/v1/interview-prep/stories",
        "/api/v1/interview-prep/stories/{story_id}",
        "/api/v1/interview-prep/applications/{application_id}/defense-map",
        "/api/v1/interview-prep/sessions",
        "/api/v1/interview-prep/sessions/{session_id}",
        "/api/v1/interview-prep/sessions/{session_id}/questions",
        "/api/v1/interview-prep/sessions/{session_id}/questions/generate",
        "/api/v1/interview-prep/sessions/{session_id}/notes",
        "/api/v1/interview-prep/sessions/{session_id}/notes/{note_id}",
        "/api/v1/interview-prep/sessions/{session_id}/follow-up-drafts",
        ("/api/v1/interview-prep/sessions/{session_id}/follow-up-drafts/generate"),
    }
    assert required.issubset(paths)
    assert "429" in paths["/api/v1/interview-prep/stories"]["post"]["responses"]
    assert "413" in paths["/api/v1/interview-prep/stories"]["post"]["responses"]
    interview_paths = {path.lower() for path in paths if path.startswith("/api/v1/interview-prep")}
    prohibited = ("send", "email", "calendar", "scrape", "submit", "import")
    assert all(all(word not in path for word in prohibited) for path in interview_paths)
    operation_ids = [
        operation["operationId"]
        for path, methods in paths.items()
        if path.startswith("/api/v1/interview-prep")
        for method, operation in methods.items()
        if method != "parameters"
    ]
    assert len(operation_ids) == len(set(operation_ids))
    schemas = document["components"]["schemas"]
    assert "origin" not in schemas["StarStoryCreateRequest"]["properties"]
    assert {"ownerUserId", "actorUserId"}.isdisjoint(schemas["StarStoryResponse"]["properties"])
    assert {"statementSha256", "evidenceRevisionId"}.issubset(
        schemas["EvidenceRevisionPinResponse"]["properties"]
    )
