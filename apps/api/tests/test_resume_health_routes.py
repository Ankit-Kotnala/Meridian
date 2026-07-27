"""Phase 2 HTTP contract, ownership dependency, and guest-cookie tests."""

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, call, create_autospec
from uuid import UUID, uuid4

from careeros.modules.identity.application import IdentityService
from careeros.modules.identity.domain import AuthenticatedPrincipal, AuthMethod
from careeros.modules.identity.domain.errors import AuthenticationRequired, RateLimited
from careeros.modules.identity.infrastructure.redis_security import RedisSecurityStore
from careeros.modules.resume_health.application import ResumeHealthService
from careeros.modules.resume_health.application.models import (
    AnalysisView,
    CanonicalSnapshotView,
    ClaimGuestDocument,
    CorrectSemanticField,
    DocumentView,
    FeatureContributionView,
    FinalizedUpload,
    FindingView,
    IssuedGuestSession,
    ProcessingJobView,
    ScoreComponentView,
    StorageUploadTarget,
    UploadIntentView,
)
from careeros.modules.resume_health.domain import (
    AnalysisStatus,
    CanonicalResume,
    DocumentStatus,
    FindingSeverity,
    JobKind,
    JobStatus,
    MalwareStatus,
    OwnerScope,
    ProcessingStage,
    ResumeMediaType,
)
from fastapi.testclient import TestClient
from pydantic import SecretStr

from careeros_api.config import Settings
from careeros_api.constants import SCORING_DISCLAIMER
from careeros_api.main import create_app
from careeros_api.modules.resume_health.schemas import ResumeHealthComponentResponse
from conftest import FakeDatabase

_ORIGIN = "http://localhost:3000"
_PRE_AUTH_CSRF = "00000000-0000-4000-8000-000000000001.test-csrf-secret"
_BFF_SIGNAL_CONTEXT = b"careeros-bff-client-v1\0"


def _identity() -> IdentityService:
    service = create_autospec(IdentityService, instance=True)
    service.issue_pre_auth_csrf.return_value = _PRE_AUTH_CSRF
    return service


def _resume() -> ResumeHealthService:
    return create_autospec(ResumeHealthService, instance=True)


def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        authenticated_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        auth_method=AuthMethod.PASSWORD,
    )


def _document(*, status: DocumentStatus = DocumentStatus.READY) -> DocumentView:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    return DocumentView(
        id=uuid4(),
        display_filename="fictional-resume.pdf",
        media_type=ResumeMediaType.PDF,
        size_bytes=1_305,
        status=status,
        malware_status=MalwareStatus.CLEAN,
        page_count=1,
        safe_error_code=None,
        retention_expires_at=None,
        version=2,
        created_at=now,
        updated_at=now,
        current_snapshot_id=uuid4(),
        latest_analysis_id=uuid4(),
    )


def _processing_job(document_id: UUID, *, kind: JobKind = JobKind.DELETE) -> ProcessingJobView:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    return ProcessingJobView(
        id=uuid4(),
        document_id=document_id,
        kind=kind,
        status=JobStatus.QUEUED,
        stage=ProcessingStage.QUEUED,
        progress=0,
        attempts=0,
        max_attempts=3,
        safe_error_code=None,
        retryable=False,
        cancellation_requested=False,
        created_at=now,
        updated_at=now,
        result_id=None,
    )


def _canonical_snapshot(document_id: UUID) -> CanonicalSnapshotView:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    resume = CanonicalResume(schema_version="canonical-resume/1.0.0", sections=(), warnings=())
    return CanonicalSnapshotView(
        id=uuid4(),
        document_id=document_id,
        revision=3,
        resume=resume,
        original_resume=resume,
        parser_version="test/1",
        corrected_by_user=True,
        created_at=now,
        based_on_snapshot_id=uuid4(),
    )


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "environment": "test",
            "trusted_hosts": ["testserver"],
            "allowed_origins": [_ORIGIN],
            "resume_max_upload_bytes": 5_242_880,
            "resume_max_pages": 8,
        }
    )


def _bff_client_signal(address: str, key_material: str) -> str:
    encoded = base64.urlsafe_b64encode(address.encode("ascii")).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        key_material.encode("utf-8"),
        _BFF_SIGNAL_CONTEXT + address.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"v1.{encoded}.{signature}"


def test_upload_policy_is_real_configuration_not_sample_metrics() -> None:
    with TestClient(create_app(_settings(), database=FakeDatabase())) as client:
        response = client.get("/api/v1/guest/resume-health/upload-policy")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "acceptedMediaTypes": [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        "maxBytes": 5_242_880,
        "maxPages": 8,
        "guestRetentionHours": 24,
        "uploadIntentTtlSeconds": 300,
    }


def test_guest_upload_issues_http_only_capability_and_scoped_intent() -> None:
    identity = _identity()
    resume = _resume()
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    guest_id = uuid4()
    upload_id = uuid4()
    resume.begin_guest_session.return_value = IssuedGuestSession(
        session_id=guest_id,
        capability_token=f"{guest_id}.opaque-guest-secret-value-that-is-long-enough",
        expires_at=now + timedelta(hours=24),
    )
    resume.create_upload_intent.return_value = UploadIntentView(
        id=upload_id,
        display_filename="fictional-resume.pdf",
        media_type=ResumeMediaType.PDF,
        expected_size=1_305,
        expires_at=now + timedelta(minutes=5),
        target=StorageUploadTarget(
            method="PUT",
            url="http://localhost:9000/careeros-documents/staging/signed",
            headers={"Content-Type": "application/pdf"},
            expires_at=now + timedelta(minutes=5),
        ),
    )
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrfToken"]
        response = client.post(
            "/api/v1/guest/uploads/presign",
            json={
                "displayFilename": "fictional-resume.pdf",
                "expectedSizeBytes": 1_305,
                "mediaType": "application/pdf",
                "purpose": "resume_health",
            },
            headers={"Origin": _ORIGIN, "X-CSRF-Token": csrf},
        )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["uploadId"] == str(upload_id)
    cookies = response.headers.get_list("set-cookie")
    assert any(
        "careeros_guest_capability=" in cookie and "HttpOnly" in cookie for cookie in cookies
    )
    assert "opaque-guest-secret" not in str(response.json())
    scope = resume.create_upload_intent.await_args.args[0]
    assert scope == OwnerScope(guest_session_id=guest_id)
    identity.validate_pre_auth_csrf.assert_called_once_with(csrf)


def test_staging_guest_admission_requires_a_bff_authenticated_client_signal() -> None:
    identity = _identity()
    resume = _resume()
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    guest_id = uuid4()
    key_material = "staging-bff-signal-secret-that-is-at-least-32-bytes"
    resume.begin_guest_session.return_value = IssuedGuestSession(
        session_id=guest_id,
        capability_token=f"{guest_id}.opaque-guest-secret-value-that-is-long-enough",
        expires_at=now + timedelta(hours=24),
    )
    resume.create_upload_intent.return_value = UploadIntentView(
        id=uuid4(),
        display_filename="fictional-resume.pdf",
        media_type=ResumeMediaType.PDF,
        expected_size=1_305,
        expires_at=now + timedelta(minutes=5),
        target=StorageUploadTarget(
            method="PUT",
            url="http://localhost:9000/careeros-documents/staging/signed",
            headers={"Content-Type": "application/pdf"},
            expires_at=now + timedelta(minutes=5),
        ),
    )
    settings = _settings().model_copy(
        update={"environment": "staging", "bff_client_signal_secret": SecretStr(key_material)}
    )
    payload = {
        "displayFilename": "fictional-resume.pdf",
        "expectedSizeBytes": 1_305,
        "mediaType": "application/pdf",
        "purpose": "resume_health",
    }

    with TestClient(
        create_app(
            settings,
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrfToken"]
        headers = {"Origin": _ORIGIN, "X-CSRF-Token": csrf}
        missing = client.post("/api/v1/guest/uploads/presign", json=payload, headers=headers)
        forged = client.post(
            "/api/v1/guest/uploads/presign",
            json=payload,
            headers={
                **headers,
                "X-CareerOS-Client-Signal": _bff_client_signal(
                    "203.0.113.42", "forged-bff-key-material-that-is-at-least-32-bytes"
                ),
            },
        )
        accepted = client.post(
            "/api/v1/guest/uploads/presign",
            json=payload,
            headers={
                **headers,
                "X-CareerOS-Client-Signal": _bff_client_signal("203.0.113.42", key_material),
            },
        )

    assert missing.status_code == 403
    assert forged.status_code == 403
    assert accepted.status_code == 201
    assert resume.begin_guest_session.await_count == 1


def test_guest_upload_intents_are_rate_limited_without_exposing_the_subject() -> None:
    identity = _identity()
    resume = _resume()
    limiter = create_autospec(RedisSecurityStore, instance=True)
    limiter.check.side_effect = [None, RateLimited(23)]
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    guest_id = uuid4()
    scope = OwnerScope(guest_session_id=guest_id)
    resume.begin_guest_session.return_value = IssuedGuestSession(
        session_id=guest_id,
        capability_token=f"{guest_id}.opaque-guest-secret-value-that-is-long-enough",
        expires_at=now + timedelta(hours=24),
    )
    resume.authenticate_guest.return_value = scope
    resume.create_upload_intent.return_value = UploadIntentView(
        id=uuid4(),
        display_filename="fictional-resume.pdf",
        media_type=ResumeMediaType.PDF,
        expected_size=1_305,
        expires_at=now + timedelta(minutes=5),
        target=StorageUploadTarget(
            method="PUT",
            url="http://localhost:9000/careeros-documents/staging/signed",
            headers={"Content-Type": "application/pdf"},
            expires_at=now + timedelta(minutes=5),
        ),
    )
    settings = _settings().model_copy(update={"resume_upload_rate_limit": 1})
    payload = {
        "displayFilename": "fictional-resume.pdf",
        "expectedSizeBytes": 1_305,
        "mediaType": "application/pdf",
        "purpose": "resume_health",
    }

    with TestClient(
        create_app(
            settings,
            database=FakeDatabase(),
            identity=identity,
            security_store=limiter,
            resume_health=resume,
        )
    ) as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrfToken"]
        first = client.post(
            "/api/v1/guest/uploads/presign",
            json=payload,
            headers={"Origin": _ORIGIN, "X-CSRF-Token": csrf},
        )
        second = client.post(
            "/api/v1/guest/uploads/presign",
            json=payload,
            headers={"Origin": _ORIGIN, "X-CSRF-Token": csrf},
        )

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "23"
    assert "guest:" not in second.text
    assert resume.create_upload_intent.await_count == 1


def test_account_finalize_preserves_the_caller_idempotency_key() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    upload_id = uuid4()
    document_id = uuid4()
    job = _processing_job(document_id, kind=JobKind.PARSE)
    identity.authenticate.return_value = principal
    resume.finalize_upload.return_value = FinalizedUpload(
        document_id=document_id,
        job_id=job.id,
        document_status=DocumentStatus.QUARANTINED,
        job_status=JobStatus.QUEUED,
    )
    resume.get_job.return_value = job

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        response = client.post(
            f"/api/v1/uploads/{upload_id}/finalize",
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "Idempotency-Key": "finalize-client-0001",
            },
        )

    assert response.status_code == 202
    assert response.json()["documentId"] == str(document_id)
    resume.finalize_upload.assert_awaited_once_with(
        OwnerScope(user_id=principal.user_id),
        upload_id,
        "finalize-client-0001",
        ANY,
    )
    resume.get_job.assert_awaited_once_with(
        OwnerScope(user_id=principal.user_id),
        job.id,
    )


def test_account_correction_and_analysis_mutations_are_rate_limited() -> None:
    identity = _identity()
    resume = _resume()
    limiter = create_autospec(RedisSecurityStore, instance=True)
    limiter.check.side_effect = [None, RateLimited(17), None, RateLimited(19)]
    principal = _principal()
    document = _document()
    snapshot = _canonical_snapshot(document.id)
    job = _processing_job(document.id, kind=JobKind.ANALYZE)
    identity.authenticate.return_value = principal
    resume.correct_canonical_resume.return_value = snapshot
    resume.start_analysis.return_value = job
    settings = _settings().model_copy(
        update={
            "resume_correction_rate_limit": 1,
            "resume_analysis_rate_limit": 1,
        }
    )
    mutation_headers = {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
    }
    correction_payload = {"fields": [{"id": str(uuid4()), "value": "Verified text"}]}
    analysis_payload = {"documentId": str(document.id)}

    with TestClient(
        create_app(
            settings,
            database=FakeDatabase(),
            identity=identity,
            security_store=limiter,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        first_correction = client.patch(
            f"/api/v1/documents/{document.id}/canonical-resume",
            json=correction_payload,
            headers={**mutation_headers, "If-Match": '"2"'},
        )
        limited_correction = client.patch(
            f"/api/v1/documents/{document.id}/canonical-resume",
            json=correction_payload,
            headers={**mutation_headers, "If-Match": '"2"'},
        )
        first_analysis = client.post(
            "/api/v1/resume-health",
            json=analysis_payload,
            headers={**mutation_headers, "Idempotency-Key": "analysis-0001"},
        )
        limited_analysis = client.post(
            "/api/v1/resume-health",
            json=analysis_payload,
            headers={**mutation_headers, "Idempotency-Key": "analysis-0002"},
        )

    assert first_correction.status_code == 200
    assert limited_correction.status_code == 429
    assert limited_correction.headers["Retry-After"] == "17"
    assert first_analysis.status_code == 202
    assert limited_analysis.status_code == 429
    assert limited_analysis.headers["Retry-After"] == "19"
    assert resume.correct_canonical_resume.await_count == 1
    assert resume.start_analysis.await_count == 1
    subject = f"user:{principal.user_id}"
    assert limiter.check.await_args_list == [
        call("resume_correction", subject, 1, settings.resume_correction_rate_window_seconds),
        call("resume_correction", subject, 1, settings.resume_correction_rate_window_seconds),
        call("resume_analysis", subject, 1, settings.resume_analysis_rate_window_seconds),
        call("resume_analysis", subject, 1, settings.resume_analysis_rate_window_seconds),
    ]


def test_account_semantic_review_uses_typed_operation_contract() -> None:
    identity = _identity()
    resume = _resume()
    limiter = create_autospec(RedisSecurityStore, instance=True)
    principal = _principal()
    document = _document()
    snapshot = _canonical_snapshot(document.id)
    field_id = uuid4()
    identity.authenticate.return_value = principal
    resume.review_canonical_semantics.return_value = snapshot

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            security_store=limiter,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        response = client.patch(
            f"/api/v1/documents/{document.id}/canonical-resume",
            json={
                "semanticOperations": [
                    {
                        "operation": "correctField",
                        "fieldId": str(field_id),
                        "value": "Verified fictional title",
                    }
                ]
            },
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "If-Match": '"2"',
            },
        )

    assert response.status_code == 200
    resume.review_canonical_semantics.assert_awaited_once_with(
        OwnerScope(user_id=principal.user_id),
        document.id,
        expected_revision=2,
        operations=(CorrectSemanticField(field_id, "Verified fictional title"),),
        confirm_no_changes=False,
        context=ANY,
    )


def test_canonical_block_correction_rejects_non_uuid_identifiers_at_transport() -> None:
    identity = _identity()
    resume = _resume()
    limiter = create_autospec(RedisSecurityStore, instance=True)
    principal = _principal()
    document = _document()
    identity.authenticate.return_value = principal

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            security_store=limiter,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        response = client.patch(
            f"/api/v1/documents/{document.id}/canonical-resume",
            json={"fields": [{"id": "not-a-uuid", "value": "Verified fictional text"}]},
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "If-Match": '"2"',
            },
        )

    assert response.status_code == 422
    resume.correct_canonical_resume.assert_not_awaited()


def test_guest_correction_and_analysis_mutations_are_rate_limited() -> None:
    identity = _identity()
    resume = _resume()
    limiter = create_autospec(RedisSecurityStore, instance=True)
    limiter.check.side_effect = [None, RateLimited(13), None, RateLimited(11)]
    guest_id = uuid4()
    capability = f"{guest_id}.opaque-guest-secret-value-that-is-long-enough"
    scope = OwnerScope(guest_session_id=guest_id)
    document = _document()
    snapshot = _canonical_snapshot(document.id)
    job = _processing_job(document.id, kind=JobKind.ANALYZE)
    resume.authenticate_guest.return_value = scope
    resume.correct_canonical_resume.return_value = snapshot
    resume.start_analysis.return_value = job
    settings = _settings().model_copy(
        update={
            "resume_correction_rate_limit": 1,
            "resume_analysis_rate_limit": 1,
        }
    )
    mutation_headers = {
        "Origin": _ORIGIN,
        "X-Guest-CSRF": "opaque-guest-csrf",
    }
    correction_payload = {"fields": [{"id": str(uuid4()), "value": "Verified text"}]}
    analysis_payload = {"documentId": str(document.id)}

    with TestClient(
        create_app(
            settings,
            database=FakeDatabase(),
            identity=identity,
            security_store=limiter,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_guest_capability", capability, path="/api/v1/guest")
        client.cookies.set("careeros_guest_csrf", "opaque-guest-csrf")
        first_correction = client.patch(
            f"/api/v1/guest/documents/{document.id}/canonical-resume",
            json=correction_payload,
            headers={**mutation_headers, "If-Match": '"2"'},
        )
        limited_correction = client.patch(
            f"/api/v1/guest/documents/{document.id}/canonical-resume",
            json=correction_payload,
            headers={**mutation_headers, "If-Match": '"2"'},
        )
        first_analysis = client.post(
            "/api/v1/guest/resume-health",
            json=analysis_payload,
            headers={**mutation_headers, "Idempotency-Key": "analysis-guest-0001"},
        )
        limited_analysis = client.post(
            "/api/v1/guest/resume-health",
            json=analysis_payload,
            headers={**mutation_headers, "Idempotency-Key": "analysis-guest-0002"},
        )

    assert first_correction.status_code == 200
    assert limited_correction.status_code == 429
    assert limited_correction.headers["Retry-After"] == "13"
    assert first_analysis.status_code == 202
    assert limited_analysis.status_code == 429
    assert limited_analysis.headers["Retry-After"] == "11"
    assert resume.authenticate_guest.await_count == 4
    assert resume.correct_canonical_resume.await_count == 1
    assert resume.start_analysis.await_count == 1
    subject = f"guest:{guest_id}"
    assert limiter.check.await_args_list == [
        call("resume_correction", subject, 1, settings.resume_correction_rate_window_seconds),
        call("resume_correction", subject, 1, settings.resume_correction_rate_window_seconds),
        call("resume_analysis", subject, 1, settings.resume_analysis_rate_window_seconds),
        call("resume_analysis", subject, 1, settings.resume_analysis_rate_window_seconds),
    ]


def test_account_documents_require_auth_and_scope_to_principal() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    document = _document()
    resume.list_documents.return_value = (document,)
    identity.authenticate.return_value = principal
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        response = client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json()["data"][0]["latestAnalysisId"] == str(document.latest_analysis_id)
    resume.list_documents.assert_awaited_once_with(OwnerScope(user_id=principal.user_id))

    denied_identity = _identity()
    denied_identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=denied_identity,
            resume_health=resume,
        )
    ) as client:
        denied = client.get("/api/v1/documents")
    assert denied.status_code == 401


def test_guest_claim_requires_both_authorizations_and_clears_guest_cookies() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    document = _document()
    capability = f"{uuid4()}.opaque-guest-secret-value-that-is-long-enough"
    identity.authenticate.return_value = principal
    resume.claim_guest_document.return_value = document

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        client.cookies.set(
            "careeros_guest_capability",
            capability,
            path="/api/v1/guest",
        )
        response = client.post(
            f"/api/v1/guest/documents/{document.id}/claim",
            json={"consent": True},
            headers={"Origin": _ORIGIN, "X-CSRF-Token": "opaque-csrf"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "documentId": str(document.id),
        "accessMode": "account",
    }
    identity.verify_csrf.assert_awaited_once_with(principal, "opaque-csrf")
    resume.claim_guest_document.assert_awaited_once_with(
        principal.user_id,
        capability,
        document.id,
        ClaimGuestDocument(policy_version="2026-07-15", consent=True),
        ANY,
    )
    cookies = response.headers.get_list("set-cookie")
    assert any(
        "careeros_guest_capability=" in cookie and "Max-Age=0" in cookie for cookie in cookies
    )
    assert any("careeros_guest_csrf=" in cookie and "Max-Age=0" in cookie for cookie in cookies)


def test_guest_claim_rejects_missing_account_or_guest_authorization() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    document = _document()
    capability = f"{uuid4()}.opaque-guest-secret-value-that-is-long-enough"

    identity.authenticate.side_effect = AuthenticationRequired
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_guest_capability", capability, path="/api/v1/guest")
        no_account = client.post(
            f"/api/v1/guest/documents/{document.id}/claim",
            json={"consent": True},
            headers={"Origin": _ORIGIN, "X-CSRF-Token": "opaque-csrf"},
        )

    assert no_account.status_code == 401
    resume.claim_guest_document.assert_not_awaited()

    identity.authenticate.side_effect = None
    identity.authenticate.return_value = principal
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        no_guest = client.post(
            f"/api/v1/guest/documents/{document.id}/claim",
            json={"consent": True},
            headers={"Origin": _ORIGIN, "X-CSRF-Token": "opaque-csrf"},
        )

    assert no_guest.status_code == 404
    resume.claim_guest_document.assert_not_awaited()

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        client.cookies.set("careeros_guest_capability", capability, path="/api/v1/guest")
        missing_consent = client.post(
            f"/api/v1/guest/documents/{document.id}/claim",
            json={},
            headers={"Origin": _ORIGIN, "X-CSRF-Token": "opaque-csrf"},
        )

    assert missing_consent.status_code == 422
    resume.claim_guest_document.assert_not_awaited()


def test_delete_accepts_eight_character_idempotency_key_boundary() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    document = _document()
    job = _processing_job(document.id)
    identity.authenticate.return_value = principal
    resume.request_delete.return_value = job

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        response = client.delete(
            f"/api/v1/documents/{document.id}",
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "If-Match": '"1"',
                "Idempotency-Key": "key-0001",
            },
        )

    assert response.status_code == 202
    call = resume.request_delete.await_args
    assert call.args[0] == OwnerScope(user_id=principal.user_id)
    assert call.args[1] == document.id
    assert call.args[2] == 1
    assert call.args[3] == "key-0001"


def test_delete_rejects_invalid_or_oversized_idempotency_key_before_service() -> None:
    identity = _identity()
    resume = _resume()
    identity.authenticate.return_value = _principal()
    document = _document()
    base_headers = {
        "Origin": _ORIGIN,
        "X-CSRF-Token": "opaque-csrf",
        "If-Match": '"1"',
    }

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        invalid_character = client.delete(
            f"/api/v1/documents/{document.id}",
            headers={**base_headers, "Idempotency-Key": "key 0001"},
        )
        oversized = client.delete(
            f"/api/v1/documents/{document.id}",
            headers={**base_headers, "Idempotency-Key": "a" * 129},
        )

    assert invalid_character.status_code == 422
    assert oversized.status_code == 422
    resume.request_delete.assert_not_awaited()


def test_delete_rejects_if_match_above_signed_integer_before_service() -> None:
    identity = _identity()
    resume = _resume()
    identity.authenticate.return_value = _principal()
    document = _document()

    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_session", "opaque-access")
        client.cookies.set("careeros_csrf", "opaque-csrf")
        response = client.delete(
            f"/api/v1/documents/{document.id}",
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "If-Match": '"2147483648"',
                "Idempotency-Key": "key-0001",
            },
        )

    assert response.status_code == 422
    resume.request_delete.assert_not_awaited()


def test_guest_resource_uses_capability_cookie_not_resource_id() -> None:
    identity = _identity()
    resume = _resume()
    guest_id = uuid4()
    capability = f"{guest_id}.opaque-guest-secret-value-that-is-long-enough"
    scope = OwnerScope(guest_session_id=guest_id)
    document = _document(status=DocumentStatus.QUARANTINED)
    resume.authenticate_guest.return_value = scope
    resume.get_document.return_value = document
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_guest_capability", capability, path="/api/v1/guest")
        response = client.get(f"/api/v1/guest/documents/{document.id}")

    assert response.status_code == 200
    resume.authenticate_guest.assert_awaited_once_with(capability)
    resume.get_document.assert_awaited_once_with(scope, document.id)


def test_report_exposes_ordered_fixed_point_feature_trace() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    identity.authenticate.return_value = principal
    document = _document()
    analysis = AnalysisView(
        id=require_uuid(document.latest_analysis_id),
        document_id=document.id,
        snapshot_id=require_uuid(document.current_snapshot_id),
        status=AnalysisStatus.SUCCEEDED,
        engine_version="resume-health/1.0.0",
        configuration_version="resume-health-default/1",
        feature_schema_version="resume-health-features/1",
        feature_values={
            "average_confidence_basis_points": 9_000,
            "image_only": False,
            "page_count": 1,
            "text_characters": 612,
        },
        feature_set_hash=bytes.fromhex("12" * 32),
        raw_score_basis_points=8_000,
        display_score=80,
        components=(
            ScoreComponentView(
                code="machine_readability",
                weight_basis_points=2_500,
                score_basis_points=8_536,
                contribution_basis_points=2_134,
                explanation="Measures observable document readability.",
            ),
        ),
        feature_contributions=(
            FeatureContributionView(
                component_code="machine_readability",
                feature_code="recognized_section_ratio",
                feature_value_basis_points=10_000,
                weight_basis_points=2_000,
                contribution_basis_points=2_000,
            ),
            FeatureContributionView(
                component_code="machine_readability",
                feature_code="searchable_text",
                feature_value_basis_points=6_120,
                weight_basis_points=3_000,
                contribution_basis_points=1_836,
            ),
        ),
        findings=(),
        computed_at=datetime(2026, 7, 15, 12, 5, tzinfo=UTC),
    )
    resume.get_analysis.return_value = analysis
    resume.get_document.return_value = document
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        response = client.get(f"/api/v1/resume-health/{analysis.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["featureSchemaVersion"] == "resume-health-features/1"
    assert body["featureValues"] == [
        {
            "key": "text_characters",
            "label": "Extractable characters",
            "kind": "count",
            "rawValue": 612,
            "displayValue": "612",
        },
        {
            "key": "page_count",
            "label": "Pages",
            "kind": "count",
            "rawValue": 1,
            "displayValue": "1",
        },
        {
            "key": "image_only",
            "label": "Image-only document",
            "kind": "boolean",
            "rawValue": False,
            "displayValue": "No",
        },
        {
            "key": "average_confidence_basis_points",
            "label": "Parser confidence",
            "kind": "percentage",
            "rawValue": 9_000,
            "displayValue": "90%",
        },
    ]
    component = body["components"][0]
    assert component["contribution"] == 21
    assert component["rawContributionBasisPoints"] == 2_134
    assert [item["key"] for item in component["featureContributions"]] == [
        "searchable_text",
        "recognized_section_ratio",
    ]
    assert component["featureContributions"][0] == {
        "key": "searchable_text",
        "label": "Searchable text",
        "score": 61,
        "rawScoreBasisPoints": 6_120,
        "weight": 30,
        "rawWeightBasisPoints": 3_000,
        "contribution": 18,
        "rawContributionBasisPoints": 1_836,
    }
    resume.get_analysis.assert_awaited_once_with(OwnerScope(user_id=principal.user_id), analysis.id)


def test_report_schema_accepts_complete_version_two_consistency_trace() -> None:
    contribution = {
        "label": "Measured feature",
        "score": 80,
        "rawScoreBasisPoints": 8_000,
        "weight": 10,
        "rawWeightBasisPoints": 1_000,
        "contribution": 8,
        "rawContributionBasisPoints": 800,
    }
    component = ResumeHealthComponentResponse.model_validate(
        {
            "key": "consistency_truth",
            "label": "Consistency and Truth",
            "score": 80,
            "rawScoreBasisPoints": 8_000,
            "weight": 10,
            "contribution": 8,
            "rawContributionBasisPoints": 800,
            "explanation": "Seven deterministic v2 factors are exposed.",
            "featureContributions": [
                contribution | {"key": key}
                for key in (
                    "parser_confidence",
                    "parser_warning_integrity",
                    "duplicate_content_integrity",
                    "chronology_coverage",
                    "source_anchor_coverage",
                    "semantic_review_coverage",
                    "date_precision_coverage",
                )
            ],
        }
    )

    assert len(component.feature_contributions) == 7


def test_report_includes_versions_hash_and_canonical_disclaimer_without_false_zero() -> None:
    identity = _identity()
    resume = _resume()
    principal = _principal()
    identity.authenticate.return_value = principal
    document = _document()
    analysis = AnalysisView(
        id=require_uuid(document.latest_analysis_id),
        document_id=document.id,
        snapshot_id=require_uuid(document.current_snapshot_id),
        status=AnalysisStatus.INSUFFICIENT_DATA,
        engine_version="resume-health/1.0.0",
        configuration_version="resume-health-default/1",
        feature_schema_version="resume-health-features/1",
        feature_values={"image_only": True, "text_characters": 0},
        feature_set_hash=bytes.fromhex("12" * 32),
        raw_score_basis_points=None,
        display_score=None,
        components=(),
        feature_contributions=(),
        findings=(),
        computed_at=datetime(2026, 7, 15, 12, 5, tzinfo=UTC),
    )
    resume.get_analysis.return_value = analysis
    resume.get_document.return_value = document
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        response = client.get(f"/api/v1/resume-health/{analysis.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficientData"
    assert body["score"] is None
    assert body["rawScoreBasisPoints"] is None
    assert body["featureSetHash"] == f"sha256:{'12' * 32}"
    assert body["disclaimer"] == SCORING_DISCLAIMER


def test_guest_report_keeps_limited_findings_and_capability_scoping() -> None:
    identity = _identity()
    resume = _resume()
    guest_id = uuid4()
    capability = f"{guest_id}.opaque-guest-secret-value-that-is-long-enough"
    scope = OwnerScope(guest_session_id=guest_id)
    document = _document()
    analysis = AnalysisView(
        id=require_uuid(document.latest_analysis_id),
        document_id=document.id,
        snapshot_id=require_uuid(document.current_snapshot_id),
        status=AnalysisStatus.INSUFFICIENT_DATA,
        engine_version="resume-health/1.0.0",
        configuration_version="resume-health-default/1",
        feature_schema_version="resume-health-features/1",
        feature_values={"text_characters": 120, "image_only": False},
        feature_set_hash=bytes.fromhex("34" * 32),
        raw_score_basis_points=None,
        display_score=None,
        components=(),
        feature_contributions=(),
        findings=tuple(
            FindingView(
                code=f"finding_{index}",
                severity=FindingSeverity.INFO,
                component_code="structure",
                message=f"Fictional finding {index}",
                quick_win=False,
                sort_order=index,
            )
            for index in range(4)
        ),
        computed_at=datetime(2026, 7, 15, 12, 5, tzinfo=UTC),
    )
    resume.authenticate_guest.return_value = scope
    resume.get_analysis.return_value = analysis
    resume.get_document.return_value = document
    with TestClient(
        create_app(
            _settings(),
            database=FakeDatabase(),
            identity=identity,
            resume_health=resume,
        )
    ) as client:
        client.cookies.set("careeros_guest_capability", capability, path="/api/v1/guest")
        response = client.get(f"/api/v1/guest/resume-health/{analysis.id}")

    assert response.status_code == 200
    assert len(response.json()["findings"]) == 3
    assert response.json()["featureValues"][0]["rawValue"] == 120
    resume.authenticate_guest.assert_awaited_once_with(capability)
    resume.get_analysis.assert_awaited_once_with(scope, analysis.id)


def require_uuid(value: UUID | None) -> UUID:
    assert value is not None
    return value
