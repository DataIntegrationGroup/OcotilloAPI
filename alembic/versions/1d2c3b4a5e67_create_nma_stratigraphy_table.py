"""Create legacy NMA_Stratigraphy table.

Revision ID: 1d2c3b4a5e67
Revises: a7b8c9d0e1f2
Create Date: 2026-01-15 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1d2c3b4a5e67"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy stratigraphy table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_Stratigraphy"):
        return

    op.create_table(
        "NMA_Stratigraphy",
        sa.Column(
            "GlobalID",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("WellID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("PointID", sa.String(length=10), nullable=False),
        sa.Column(
            "thing_id",
            sa.Integer(),
            sa.ForeignKey("thing.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("StratTop", sa.Float(), nullable=True),
        sa.Column("StratBottom", sa.Float(), nullable=True),
        sa.Column("UnitIdentifier", sa.String(length=50), nullable=True),
        sa.Column("Lithology", sa.String(length=100), nullable=True),
        sa.Column("LithologicModifier", sa.String(length=100), nullable=True),
        sa.Column("ContributingUnit", sa.String(length=10), nullable=True),
        sa.Column("StratSource", sa.Text(), nullable=True),
        sa.Column("StratNotes", sa.Text(), nullable=True),
        sa.Column("OBJECTID", sa.Integer(), nullable=True, unique=True),
        sa.ForeignKeyConstraint(["thing_id"], ["thing.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_nma_stratigraphy_point_id",
        "NMA_Stratigraphy",
        ["PointID"],
    )
    op.create_index(
        "ix_nma_stratigraphy_thing_id",
        "NMA_Stratigraphy",
        ["thing_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_nma_stratigraphy_thing_id", table_name="NMA_Stratigraphy")
    op.drop_index("ix_nma_stratigraphy_point_id", table_name="NMA_Stratigraphy")
    op.drop_table("NMA_Stratigraphy")
