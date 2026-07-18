"""Alembic revision graph tests that do not require PostgreSQL."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

EXPECTED_HEAD = "20260715_0004"


def test_migration_graph_has_one_expected_head() -> None:
    package_root = Path(__file__).resolve().parents[2]
    config = Config(package_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == [EXPECTED_HEAD]
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        EXPECTED_HEAD,
        "20260715_0003",
        "20260715_0002",
        "20260714_0001",
    ]
