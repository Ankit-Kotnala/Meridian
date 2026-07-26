"""Alembic revision graph tests that do not require PostgreSQL."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

EXPECTED_HEAD = "20260727_0019"


def test_migration_graph_has_one_expected_head() -> None:
    package_root = Path(__file__).resolve().parents[2]
    config = Config(package_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == [EXPECTED_HEAD]
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        EXPECTED_HEAD,
        "20260727_0018",
        "20260727_0017",
        "20260726_0016",
        "20260726_0015",
        "20260726_0014",
        "20260726_0013",
        "20260726_0012",
        "20260726_0011",
        "20260724_0010",
        "20260724_0009",
        "20260719_0008",
        "20260719_0007",
        "20260719_0006",
        "20260719_0005",
        "20260715_0004",
        "20260715_0003",
        "20260715_0002",
        "20260714_0001",
    ]
