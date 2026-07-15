"""Operational endpoint and request-correlation tests."""

from uuid import UUID

from fastapi.testclient import TestClient

from careeros_api.config import Settings
from careeros_api.constants import SCORING_DISCLAIMER
from careeros_api.main import create_app
from conftest import FakeDatabase


def test_health_is_live_without_calling_dependencies(
    client: TestClient, fake_database: FakeDatabase
) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "careeros-api",
        "version": "0.1.0",
    }
    assert fake_database.ping_count == 0


def test_ready_reports_healthy_database(client: TestClient, fake_database: FakeDatabase) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"] == {"database": {"status": "ok"}}
    assert fake_database.ping_count == 1


def test_ready_fails_closed_without_leaking_exception_details(settings: Settings) -> None:
    database = FakeDatabase(RuntimeError("password=do-not-leak"))

    with TestClient(create_app(settings, database=database)) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {"database": {"status": "unavailable"}}
    assert "do-not-leak" not in response.text


def test_request_id_is_echoed_when_safe(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace_123.safe"})

    assert response.headers["X-Request-ID"] == "trace_123.safe"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "line-one\nline-two"})

    assert UUID(response.headers["X-Request-ID"])


def test_valid_w3c_trace_id_is_propagated(client: TestClient) -> None:
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    response = client.get(
        "/health",
        headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"},
    )

    assert response.headers["X-Trace-ID"] == trace_id


def test_invalid_traceparent_starts_a_new_trace(client: TestClient) -> None:
    response = client.get("/health", headers={"traceparent": "00-invalid"})

    assert len(response.headers["X-Trace-ID"]) == 32
    assert int(response.headers["X-Trace-ID"], 16) > 0


def test_metadata_is_non_sensitive_and_contains_disclaimer(client: TestClient) -> None:
    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "service": "careeros-api",
        "version": "0.1.0",
        "api_version": "v1",
        "environment": "test",
        "scoring_disclaimer": SCORING_DISCLAIMER,
    }
    assert "database" not in response.text.lower()


def test_openapi_operation_ids_are_stable(client: TestClient) -> None:
    operations = client.get("/openapi.json").json()["paths"]

    assert operations["/health"]["get"]["operationId"] == "health"
    assert operations["/ready"]["get"]["operationId"] == "readiness"
    assert operations["/api/v1/meta"]["get"]["operationId"] == "metadata"


def test_dependency_is_disposed_after_lifespan(settings: Settings) -> None:
    database = FakeDatabase()

    with TestClient(create_app(settings, database=database)):
        assert not database.disposed

    assert database.disposed
