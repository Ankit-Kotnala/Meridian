"""Executable dependency rules for the modular-monolith backend."""

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BACKEND_SOURCE = REPOSITORY_ROOT / "packages" / "backend" / "src"
API_SOURCE = REPOSITORY_ROOT / "apps" / "api" / "src"
WORKER_SOURCE = REPOSITORY_ROOT / "apps" / "worker" / "src"

DOMAIN_FORBIDDEN = {
    "aioboto3",
    "alembic",
    "anthropic",
    "asyncpg",
    "boto3",
    "botocore",
    "celery",
    "fastapi",
    "openai",
    "redis",
    "sqlalchemy",
    "starlette",
}
APPLICATION_FORBIDDEN = DOMAIN_FORBIDDEN
DEPLOYABLE_PERSISTENCE = {"alembic", "asyncpg", "sqlalchemy"}


@dataclass(frozen=True, slots=True)
class ImportViolation:
    path: Path
    line: int
    imported: str
    reason: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: {self.imported} ({self.reason})"


def imported_modules(source: str) -> list[tuple[int, str]]:
    """Return fully qualified static imports, including relative import levels."""
    tree = ast.parse(source)
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            module = f"{prefix}{node.module or ''}"
            separator = "." if node.module else ""
            imported.extend(
                (node.lineno, f"{module}{separator}{alias.name}") for alias in node.names
            )
    return imported


def violations_for_source(path: Path, source: str) -> list[ImportViolation]:
    """Evaluate dependency rules for one repository-relative source path."""
    imports = imported_modules(source)
    parts = path.parts
    violations: list[ImportViolation] = []

    def forbid(packages: set[str], reason: str) -> None:
        for line, imported_module in imports:
            imported_root = imported_module.lstrip(".").split(".", 1)[0]
            if imported_root in packages:
                violations.append(ImportViolation(path, line, imported_root, reason))

    normalized = path.as_posix()
    if normalized.startswith("packages/backend/src/"):
        forbid({"careeros_api", "careeros_worker"}, "backend must not import deployables")
    if normalized.startswith("apps/api/src/"):
        forbid({"careeros_worker"}, "API must not import worker")
        forbid(DEPLOYABLE_PERSISTENCE, "persistence belongs in packages/backend")
    if normalized.startswith("apps/worker/src/"):
        forbid({"careeros_api"}, "worker must not import API")
        forbid(DEPLOYABLE_PERSISTENCE, "persistence belongs in packages/backend")
    if "foundation" in parts:
        for line, imported_module in imports:
            normalized_import = imported_module.lstrip(".")
            if normalized_import.startswith(
                ("modules.", "integrations.", "careeros.modules.", "careeros.integrations.")
            ) or normalized_import in {
                "modules",
                "integrations",
                "careeros.modules",
                "careeros.integrations",
            }:
                violations.append(
                    ImportViolation(
                        path,
                        line,
                        normalized_import,
                        "foundation must not depend on product modules or integrations",
                    )
                )
    if "domain" in parts:
        forbid(DOMAIN_FORBIDDEN, "domain must remain framework and SDK independent")
    if "application" in parts:
        forbid(APPLICATION_FORBIDDEN, "application must depend on inward-facing ports")
    return violations


def repository_violations() -> list[ImportViolation]:
    violations: list[ImportViolation] = []
    for source_root in (BACKEND_SOURCE, API_SOURCE, WORKER_SOURCE):
        for source_path in source_root.rglob("*.py"):
            relative_path = source_path.relative_to(REPOSITORY_ROOT)
            violations.extend(
                violations_for_source(relative_path, source_path.read_text(encoding="utf-8"))
            )
    return violations


def test_repository_respects_backend_dependency_direction() -> None:
    violations = repository_violations()

    assert not violations, "\n".join(violation.describe() for violation in violations)


@pytest.mark.parametrize(
    ("path", "source", "expected_package"),
    [
        (
            Path("packages/backend/src/careeros/modules/evidence/domain/entities.py"),
            "from sqlalchemy.orm import DeclarativeBase",
            "sqlalchemy",
        ),
        (
            Path("packages/backend/src/careeros/modules/evidence/application/handler.py"),
            "from fastapi import Depends",
            "fastapi",
        ),
        (
            Path("apps/worker/src/careeros_worker/consumer.py"),
            "from careeros_api.main import app",
            "careeros_api",
        ),
        (
            Path("apps/api/src/careeros_api/query.py"),
            "from sqlalchemy import select",
            "sqlalchemy",
        ),
        (
            Path("packages/backend/src/careeros/foundation/config/settings.py"),
            "from ...modules.evidence.domain import Evidence",
            "modules.evidence.domain.Evidence",
        ),
    ],
)
def test_negative_fixtures_prove_rules_are_active(
    path: Path,
    source: str,
    expected_package: str,
) -> None:
    violations = violations_for_source(path, source)

    assert any(violation.imported == expected_package for violation in violations)


def test_workspace_members_depend_on_shared_backend() -> None:
    root_configuration = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert set(root_configuration["tool"]["uv"]["workspace"]["members"]) == {
        "apps/api",
        "apps/worker",
        "packages/backend",
    }

    for deployable in ("api", "worker"):
        configuration = tomllib.loads(
            (REPOSITORY_ROOT / "apps" / deployable / "pyproject.toml").read_text(encoding="utf-8")
        )
        dependencies = configuration["project"]["dependencies"]
        assert any(dependency.startswith("careeros-backend") for dependency in dependencies)
        direct_dependency_names = {
            dependency.partition("[")[0].partition("==")[0] for dependency in dependencies
        }
        assert direct_dependency_names.isdisjoint(DEPLOYABLE_PERSISTENCE)
        assert configuration["tool"]["uv"]["sources"]["careeros-backend"] == {"workspace": True}
