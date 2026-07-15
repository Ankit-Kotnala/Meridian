"""Regression tests for deterministic OpenAPI export."""

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

EXPORTER_PATH = (
    Path(__file__).resolve().parents[3] / "packages" / "contracts" / "scripts" / "export_openapi.py"
)


def test_export_ignores_ambient_service_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAREEROS_SERVICE_VERSION", "9.9.9-audit")
    namespace = runpy.run_path(str(EXPORTER_PATH))
    render_schema = cast(Callable[[], str], namespace["render_schema"])

    schema = json.loads(render_schema())

    assert schema["info"]["version"] == "0.1.0"
