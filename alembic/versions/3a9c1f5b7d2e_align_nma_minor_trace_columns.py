"""Align NMA_MinorTraceChemistry columns with legacy schema.

Revision ID: 3a9c1f5b7d2e
Revises: c1d2e3f4a5b6
Create Date: 2026-01-31 12:00:00.000000

NOTE: This migration is now a no-op because the Integer PK refactor
(migration 3cb924ca51fd) handles all column changes for NMA tables.
This migration exists only to preserve the alembic revision chain.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "3a9c1f5b7d2e"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: schema changes handled by Integer PK refactor migration."""
    pass


def downgrade() -> None:
    """No-op: schema changes handled by Integer PK refactor migration."""
    pass
