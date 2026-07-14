"""Alembic revision graph tests that do not require PostgreSQL."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

EXPECTED_HEAD = "20260714_0001"


def test_migration_graph_has_one_expected_head() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = Config(project_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == [EXPECTED_HEAD]
    assert [revision.revision for revision in scripts.walk_revisions()] == [EXPECTED_HEAD]
