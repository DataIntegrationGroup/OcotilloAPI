"""Merge minor trace alignment and field parameters heads.

Revision ID: 4f6b7c8d9e0f
Revises: 3a9c1f5b7d2e, c1d2e3f4a5b6
Create Date: 2026-01-31 12:15:00.000000
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "4f6b7c8d9e0f"
down_revision: Union[str, Sequence[str], None] = (
    "3a9c1f5b7d2e",
    "c1d2e3f4a5b6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads."""
    pass


def downgrade() -> None:
    """Split heads."""
    pass
