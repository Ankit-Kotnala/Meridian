"""Regression tests for deterministic OpenAPI export."""

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

EXPORTER_PATH = (
    Path(__file__).resolve().parents[3] / "shared" / "contracts" / "scripts" / "export_openapi.py"
)


def test_export_ignores_all_hostile_ambient_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REZUMI_SERVICE_VERSION", "9.9.9-audit")
    monkeypatch.setenv("REZUMI_DATABASE_URL", "not-a-database-url")
    monkeypatch.setenv("REZUMI_ALLOWED_ORIGINS", "not-json")
    monkeypatch.setenv("CORS_ORIGINS", "also-not-json")
    monkeypatch.setenv("REZUMI_AUTH_TOKEN_PEPPER", "short")
    namespace = runpy.run_path(str(EXPORTER_PATH))
    render_schema = cast(Callable[[], str], namespace["render_schema"])

    schema = json.loads(render_schema())

    assert schema["info"]["version"] == "0.1.0"
    assert "/api/v1/auth/register" in schema["paths"]
