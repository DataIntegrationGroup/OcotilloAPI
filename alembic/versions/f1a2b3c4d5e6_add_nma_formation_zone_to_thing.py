"""Add nma_formation_zone to Thing.

Revision ID: f1a2b3c4d5e6
Revises: g4a5b6c7d8e9
Create Date: 2026-03-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "g4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("thing"):
        columns = {col["name"] for col in inspector.get_columns("thing")}
        if "nma_formation_zone" not in columns:
            op.add_column(
                "thing",
                sa.Column("nma_formation_zone", sa.String(length=25), nullable=True),
            )
    if inspector.has_table("thing_version"):
        columns = {col["name"] for col in inspector.get_columns("thing_version")}
        if "nma_formation_zone" not in columns:
            op.add_column(
                "thing_version",
                sa.Column("nma_formation_zone", sa.String(length=25), nullable=True),
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("thing_version"):
        columns = {col["name"] for col in inspector.get_columns("thing_version")}
        if "nma_formation_zone" in columns:
            op.drop_column("thing_version", "nma_formation_zone")
    if inspector.has_table("thing"):
        columns = {col["name"] for col in inspector.get_columns("thing")}
        if "nma_formation_zone" in columns:
            op.drop_column("thing", "nma_formation_zone")
