"""Executable dependency rules for the modular-monolith backend."""

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "core" / "src"
API_SOURCE = REPOSITORY_ROOT / "backend" / "api" / "src"
WORKER_SOURCE = REPOSITORY_ROOT / "backend" / "worker" / "src"

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
BACKEND_MODULE_PREFIX = ("backend", "core", "src", "rezumi", "modules")


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


def _product_module_for_path(path: Path) -> str | None:
    parts = path.parts
    width = len(BACKEND_MODULE_PREFIX)
    for index in range(len(parts) - width):
        if parts[index : index + width] == BACKEND_MODULE_PREFIX:
            return parts[index + width]
    return None


def _source_package(path: Path) -> tuple[str, ...]:
    parts = path.parts
    try:
        source_index = parts.index("src")
    except ValueError:
        return ()
    module_parts = list(parts[source_index + 1 :])
    if not module_parts or not module_parts[-1].endswith(".py"):
        return ()
    filename = module_parts.pop()
    if filename == "__init__.py":
        return tuple(module_parts)
    return tuple(module_parts)


def resolved_imported_modules(path: Path, source: str) -> list[tuple[int, str]]:
    """Resolve absolute and relative imports to repository package paths."""

    tree = ast.parse(source)
    package = _source_package(path)
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level > 0:
            parents_to_remove = node.level - 1
            if parents_to_remove > len(package):
                continue
            prefix = package[: len(package) - parents_to_remove]
            module = tuple((node.module or "").split(".")) if node.module else ()
            base = ".".join((*prefix, *module))
        else:
            base = node.module or ""
        imported.extend(
            (
                node.lineno,
                f"{base}.{alias.name}" if base else alias.name,
            )
            for alias in node.names
        )
    return imported


def _cross_product_import(current_module: str, imported_module: str) -> tuple[str, str] | None:
    parts = imported_module.split(".")
    for index in range(len(parts) - 2):
        if parts[index : index + 2] != ["rezumi", "modules"]:
            continue
        target_module = parts[index + 2]
        if target_module == current_module:
            return None
        boundary = parts[index + 3] if len(parts) > index + 3 else None
        if boundary == "application":
            return None
        if boundary == "infrastructure" or "models" in parts[index + 3 :]:
            reason = "cross-product infrastructure/model access is forbidden"
        else:
            reason = "cross-product dependencies require an explicit application contract"
        return imported_module, reason
    return None


def direct_table_accesses(source: str) -> list[tuple[int, str]]:
    """Find table-object escape hatches that bypass module repositories."""

    accesses: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == "__table__":
            accesses.append((node.lineno, "__table__"))
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "tables"
            and isinstance(node.value.value, ast.Attribute)
            and node.value.value.attr == "metadata"
        ):
            accesses.append((node.lineno, "metadata.tables"))
    return accesses


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
    product_module = _product_module_for_path(path)
    if product_module is not None:
        for line, imported_module in resolved_imported_modules(path, source):
            cross_product = _cross_product_import(product_module, imported_module)
            if cross_product is not None:
                imported, reason = cross_product
                violations.append(ImportViolation(path, line, imported, reason))
        for line, access in direct_table_accesses(source):
            violations.append(
                ImportViolation(
                    path,
                    line,
                    access,
                    "product modules must not bypass repositories with direct table access",
                )
            )
    if normalized.startswith("backend/core/src/"):
        forbid({"rezumi_api", "rezumi_worker"}, "backend must not import deployables")
    if normalized.startswith("backend/api/src/"):
        forbid({"rezumi_worker"}, "API must not import worker")
        forbid(DEPLOYABLE_PERSISTENCE, "persistence belongs in backend/core")
    if normalized.startswith("backend/worker/src/"):
        forbid({"rezumi_api"}, "worker must not import API")
        forbid(DEPLOYABLE_PERSISTENCE, "persistence belongs in backend/core")
    if "foundation" in parts:
        for line, imported_module in imports:
            normalized_import = imported_module.lstrip(".")
            if normalized_import.startswith(
                ("modules.", "integrations.", "rezumi.modules.", "rezumi.integrations.")
            ) or normalized_import in {
                "modules",
                "integrations",
                "rezumi.modules",
                "rezumi.integrations",
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
            Path("backend/core/src/rezumi/modules/evidence/domain/entities.py"),
            "from sqlalchemy.orm import DeclarativeBase",
            "sqlalchemy",
        ),
        (
            Path("backend/core/src/rezumi/modules/evidence/application/handler.py"),
            "from fastapi import Depends",
            "fastapi",
        ),
        (
            Path("backend/worker/src/rezumi_worker/consumer.py"),
            "from rezumi_api.main import app",
            "rezumi_api",
        ),
        (
            Path("backend/api/src/rezumi_api/query.py"),
            "from sqlalchemy import select",
            "sqlalchemy",
        ),
        (
            Path("backend/core/src/rezumi/foundation/config/settings.py"),
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


@pytest.mark.parametrize(
    ("source", "expected_import"),
    [
        (
            "from rezumi.modules.resume_health.infrastructure.models "
            "import CanonicalResumeSnapshotModel",
            "rezumi.modules.resume_health.infrastructure.models.CanonicalResumeSnapshotModel",
        ),
        (
            "from ...resume_health.domain.entities import CanonicalSnapshot",
            "rezumi.modules.resume_health.domain.entities.CanonicalSnapshot",
        ),
        (
            "from rezumi.modules.resume_health import infrastructure",
            "rezumi.modules.resume_health.infrastructure",
        ),
    ],
)
def test_product_modules_cannot_reach_across_non_application_boundaries(
    source: str, expected_import: str
) -> None:
    path = Path("backend/core/src/rezumi/modules/evidence/application/handler.py")

    violations = violations_for_source(path, source)

    assert any(violation.imported == expected_import for violation in violations)


@pytest.mark.parametrize(
    ("source", "expected_access"),
    [
        ("table = EvidenceModel.__table__", "__table__"),
        ('table = Base.metadata.tables["evidence_items"]', "metadata.tables"),
    ],
)
def test_product_modules_cannot_bypass_repositories_with_table_objects(
    source: str, expected_access: str
) -> None:
    path = Path("backend/core/src/rezumi/modules/evidence/infrastructure/query.py")

    violations = violations_for_source(path, source)

    assert any(violation.imported == expected_access for violation in violations)


def test_product_modules_may_use_explicit_application_contracts() -> None:
    path = Path("backend/core/src/rezumi/modules/evidence/application/handler.py")
    source = "from rezumi.modules.resume_health.application.contracts import CanonicalResumeReader"

    violations = violations_for_source(path, source)

    assert not violations


def test_workspace_members_depend_on_shared_backend() -> None:
    root_configuration = tomllib.loads(
        (REPOSITORY_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert set(root_configuration["tool"]["uv"]["workspace"]["members"]) == {
        "api",
        "worker",
        "core",
    }

    for deployable in ("api", "worker"):
        pyproject_path = REPOSITORY_ROOT / "backend" / deployable / "pyproject.toml"
        configuration = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        dependencies = configuration["project"]["dependencies"]
        assert any(dependency.startswith("rezumi-backend") for dependency in dependencies)
        direct_dependency_names = {
            dependency.partition("[")[0].partition("==")[0] for dependency in dependencies
        }
        assert direct_dependency_names.isdisjoint(DEPLOYABLE_PERSISTENCE)
        assert configuration["tool"]["uv"]["sources"]["rezumi-backend"] == {"workspace": True}
