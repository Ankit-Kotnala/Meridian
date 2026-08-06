"""Authenticated HTTP contracts for private, correlation-only Career Analytics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import create_autospec
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from rezumi.modules.career_analytics.application import (
    ANALYTICS_INTERPRETATION,
    APPLICATION_COHORT_DEFINITION,
    METRIC_DEFINITION_VERSION,
    TIMESTAMP_SEMANTICS,
    AnalyticsRefreshView,
    AnalyticsReport,
    CareerAnalyticsService,
    metric_definitions_payload,
    suppression_policy_payload,
)
from rezumi.modules.career_analytics.domain import (
    AnalyticsJobStatus,
    AnalyticsScope,
    AnalyticsSnapshotStatus,
    CareerAnalyticsNotFound,
    CareerAnalyticsQuotaExceeded,
    CareerAnalyticsUnavailable,
    CareerAnalyticsValidationError,
)
from rezumi.modules.identity.application import IdentityService
from rezumi.modules.identity.domain import AuthenticatedPrincipal, AuthMethod

from conftest import FakeDatabase
from rezumi_api.config import Settings
from rezumi_api.main import create_app

_ORIGIN = "http://localhost:3000"
_NOW = datetime(2026, 7, 24, 20, tzinfo=UTC)
_OWNER_ID = UUID("00000000-0000-4000-8000-000000009001")


def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=_OWNER_ID,
        session_id=uuid4(),
        authenticated_at=_NOW,
        auth_method=AuthMethod.PASSWORD,
    )


def _refresh() -> AnalyticsRefreshView:
    return AnalyticsRefreshView(
        id=UUID("00000000-0000-4000-8000-000000009002"),
        scope=AnalyticsScope.APPLICATIONS,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
        timezone="Asia/Kolkata",
        status=AnalyticsJobStatus.COMPLETED,
        attempts=1,
        max_attempts=3,
        safe_error_code=None,
        version=3,
        created_at=_NOW,
        updated_at=_NOW,
        completed_at=_NOW,
    )


def _report(refresh: AnalyticsRefreshView) -> AnalyticsReport:
    watermark = {
        "source": "applications",
        "token": f"sha256:{'a' * 64}",
        "recordCount": 6,
        "maxUpdatedAt": _NOW.isoformat(),
    }
    payload: dict[str, object] = {
        "scope": "applications",
        "counts": {
            "applications": 6,
            "interviews": 2,
            "offers": 1,
            "responses": 4,
            "achievements": 1,
            "readinessAnalyses": 1,
        },
        "rates": {
            "responseRate": {
                "numerator": 4,
                "denominator": 6,
                "valueBasisPoints": 6667,
                "suppressed": False,
                "suppressionReason": None,
            },
            "offerRate": {
                "numerator": None,
                "denominator": None,
                "valueBasisPoints": None,
                "suppressed": True,
                "suppressionReason": (
                    "Not shown for privacy and reliability because this cohort "
                    "has fewer than 5 records."
                ),
            },
        },
        "breakdowns": {"stage": [{"key": "interview", "count": 2}]},
        "outcomesByResumeVersion": [],
        "requirementCoverageTrend": [],
        "timeBuckets": [
            {
                "start": "2026-01-01",
                "end": "2026-07-24",
                "applications": 6,
                "interviews": 2,
                "offers": 1,
                "achievements": 1,
            }
        ],
        "readinessHistory": [],
        "interpretation": ANALYTICS_INTERPRETATION,
        "metricDefinitionVersion": METRIC_DEFINITION_VERSION,
    }
    return AnalyticsReport(
        scope=AnalyticsScope.APPLICATIONS,
        status=AnalyticsSnapshotStatus.READY,
        freshness="current",
        metric_definition_version=METRIC_DEFINITION_VERSION,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 7, 24),
        timezone="Asia/Kolkata",
        cohort_definition=APPLICATION_COHORT_DEFINITION,
        metric_definitions=metric_definitions_payload(),
        suppression_policy=suppression_policy_payload(),
        timestamp_semantics=dict(TIMESTAMP_SEMANTICS),
        source_watermarks={"applications": watermark},
        payload=payload,
        generated_at=_NOW,
        refresh=refresh,
    )


def _services() -> tuple[IdentityService, CareerAnalyticsService]:
    identity = create_autospec(IdentityService, instance=True)
    identity.authenticate.return_value = _principal()
    analytics = create_autospec(CareerAnalyticsService, instance=True)
    refresh = _refresh()
    analytics.request_refresh.return_value = refresh
    analytics.get_refresh.return_value = refresh
    analytics.get_report.return_value = _report(refresh)
    return identity, analytics


def _client(
    settings: Settings,
    database: FakeDatabase,
    identity: IdentityService,
    analytics: CareerAnalyticsService,
) -> TestClient:
    client = TestClient(
        create_app(
            settings,
            database=database,
            identity=identity,
            career_analytics=analytics,
        )
    )
    client.cookies.set("rezumi_session", "opaque-session")
    client.cookies.set("rezumi_csrf", "opaque-csrf")
    return client


def test_career_analytics_private_refresh_and_report_contract(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity, analytics = _services()
    with _client(settings, fake_database, identity, analytics) as client:
        created = client.post(
            "/api/v1/analytics/refreshes",
            json={
                "scope": "applications",
                "windowStart": "2026-01-01",
                "windowEnd": "2026-07-24",
                "timezone": "Asia/Calcutta",
            },
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "Idempotency-Key": "analytics-refresh-001",
            },
        )
        assert created.status_code == 202
        assert created.headers["cache-control"] == "no-store"
        assert created.headers["etag"] == '"3"'
        assert created.headers["location"].endswith(str(_refresh().id))
        assert created.json()["windowStart"] == "2026-01-01"
        assert created.json()["windowEnd"] == "2026-12-31"
        command = analytics.request_refresh.await_args.args[1]
        assert command.timezone == "Asia/Calcutta"
        assert analytics.request_refresh.await_args.args[0] == _OWNER_ID

        status_response = client.get(f"/api/v1/analytics/refreshes/{_refresh().id}")
        assert status_response.status_code == 200
        assert status_response.headers["cache-control"] == "no-store"
        assert status_response.json()["windowStart"] == "2026-01-01"
        assert status_response.json()["windowEnd"] == "2026-12-31"

        report = client.get(
            "/api/v1/analytics/report",
            params={
                "scope": "applications",
                "windowStart": "2026-01-01",
                "windowEnd": "2026-07-24",
                "timezone": "Asia/Kolkata",
            },
        )
        assert report.status_code == 200
        body = report.json()
        assert body["interpretation"] == ANALYTICS_INTERPRETATION
        assert body["timezone"] == "Asia/Kolkata"
        assert body["cohortDefinition"] == APPLICATION_COHORT_DEFINITION
        assert body["suppressionPolicy"]["minimumDenominator"] == 5
        assert body["metricDefinitions"][0]["version"] == METRIC_DEFINITION_VERSION
        assert body["timestampSemantics"]["applicationCohort"]
        assert analytics.get_report.await_args.kwargs["timezone"] == "Asia/Kolkata"
        context = analytics.get_report.await_args.kwargs["context"]
        assert context.actor_user_id == _OWNER_ID
        assert context.request_id
        assert context.request_id != "analytics-report-read"
        assert len(context.trace_id) == 32
        assert context.trace_id != "0" * 32
        assert body["payload"]["interpretation"] == ANALYTICS_INTERPRETATION
        assert body["payload"]["rates"]["offerRate"] == {
            "numerator": None,
            "denominator": None,
            "valueBasisPoints": None,
            "suppressed": True,
            "suppressionReason": (
                "Not shown for privacy and reliability because this cohort "
                "has fewer than 5 records."
            ),
        }
        serialized = report.text.casefold()
        for restricted in (
            "contactemail",
            "contactname",
            "evidencestatement",
            "offersummary",
            "rawresume",
            "rejectionreason",
        ):
            assert restricted not in serialized


def test_career_analytics_csrf_validation_and_owner_safe_problems(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity, analytics = _services()
    analytics.get_refresh.side_effect = CareerAnalyticsNotFound
    with _client(settings, fake_database, identity, analytics) as client:
        missing_csrf = client.post(
            "/api/v1/analytics/refreshes",
            json={
                "scope": "overview",
                "windowStart": "2026-01-01",
                "windowEnd": "2026-07-24",
                "timezone": "Asia/Kolkata",
            },
            headers={"Idempotency-Key": "analytics-refresh-002"},
        )
        assert missing_csrf.status_code == 403
        analytics.request_refresh.assert_not_awaited()

        not_found = client.get(f"/api/v1/analytics/refreshes/{uuid4()}")
        assert not_found.status_code == 404
        assert not_found.json()["code"] == "career_analytics_not_found"
        assert "owner" not in not_found.text.casefold()

        analytics.request_refresh.side_effect = CareerAnalyticsValidationError(
            "timezone echoed secret"
        )
        rejected = client.post(
            "/api/v1/analytics/refreshes",
            json={
                "scope": "overview",
                "windowStart": "2026-07-24",
                "windowEnd": "2026-01-01",
            },
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "Idempotency-Key": "analytics-refresh-003",
            },
        )
        assert rejected.status_code == 422
        assert "echoed secret" not in rejected.text


def test_career_analytics_openapi_is_strict_and_worker_actions_are_not_public(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity, analytics = _services()
    application = create_app(
        settings,
        database=fake_database,
        identity=identity,
        career_analytics=analytics,
    )
    document = application.openapi()
    paths = document["paths"]
    assert "/api/v1/analytics/refreshes" in paths
    assert "/api/v1/analytics/report" in paths
    refresh_responses = paths["/api/v1/analytics/refreshes"]["post"]["responses"]
    assert "413" in refresh_responses
    assert "429" in refresh_responses
    refresh_schema = document["components"]["schemas"]["AnalyticsRefreshResponse"]
    assert {"windowStart", "windowEnd"} <= set(refresh_schema["required"])
    serialized = str(paths).casefold()
    for forbidden in ("claim_outbox", "mark_outbox", "process_refresh", "reconcile_expired"):
        assert forbidden not in serialized


def test_career_analytics_quota_is_a_safe_429(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity, analytics = _services()
    analytics.request_refresh.side_effect = CareerAnalyticsQuotaExceeded("internal quota details")
    with _client(settings, fake_database, identity, analytics) as client:
        response = client.post(
            "/api/v1/analytics/refreshes",
            json={
                "scope": "applications",
                "windowStart": "2026-01-01",
                "windowEnd": "2026-07-24",
                "timezone": "UTC",
            },
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "Idempotency-Key": "analytics-refresh-quota",
            },
        )

    assert response.status_code == 429
    assert response.json()["code"] == "career_analytics_quota_exceeded"
    assert "internal quota details" not in response.text


def test_career_analytics_source_failure_stays_a_safe_analytics_problem(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity, analytics = _services()
    analytics.get_report.side_effect = CareerAnalyticsUnavailable("provider details")
    with _client(settings, fake_database, identity, analytics) as client:
        response = client.get(
            "/api/v1/analytics/report",
            params={
                "scope": "overview",
                "windowStart": "2010-01-02",
                "windowEnd": "2019-12-31",
                "timezone": "UTC",
            },
        )

    assert response.status_code == 503
    assert response.json()["code"] == "career_analytics_unavailable"
    assert "provider details" not in response.text


def test_career_analytics_http_contract_accepts_the_public_maximum_window(
    settings: Settings,
    fake_database: FakeDatabase,
) -> None:
    identity, analytics = _services()
    start = date(2010, 1, 2)
    end = start.fromordinal(start.toordinal() + 3_650)
    with _client(settings, fake_database, identity, analytics) as client:
        response = client.post(
            "/api/v1/analytics/refreshes",
            json={
                "scope": "overview",
                "windowStart": start.isoformat(),
                "windowEnd": end.isoformat(),
                "timezone": "Pacific/Kiritimati",
            },
            headers={
                "Origin": _ORIGIN,
                "X-CSRF-Token": "opaque-csrf",
                "Idempotency-Key": "analytics-max-window",
            },
        )

    assert response.status_code == 202
    command = analytics.request_refresh.await_args.args[1]
    assert (command.window_end - command.window_start).days == 3_650
