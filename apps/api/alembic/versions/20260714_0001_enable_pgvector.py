"""Enable the pgvector extension.

Revision ID: 20260714_0001
Revises:
Create Date: 2026-07-14 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260714_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make vector columns available to later semantic-retrieval migrations."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Retain a potentially shared extension when rolling back this service."""
    # Extensions can be shared by other schemas and DROP ... CASCADE is unsafe.
