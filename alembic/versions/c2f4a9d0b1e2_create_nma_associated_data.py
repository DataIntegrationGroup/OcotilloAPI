"""Create legacy NMA_AssociatedData table.

Revision ID: c2f4a9d0b1e2
Revises: a7b8c9d0e1f2
Create Date: 2026-03-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2f4a9d0b1e2"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy associated data table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_AssociatedData"):
        op.create_table(
            "NMA_AssociatedData",
            sa.Column("LocationId", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("PointID", sa.String(length=10), nullable=True),
            sa.Column(
                "AssocID",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                primary_key=True,
            ),
            sa.Column("Notes", sa.String(length=255), nullable=True),
            sa.Column("Formation", sa.String(length=15), nullable=True),
            sa.Column("OBJECTID", sa.Integer(), nullable=True, unique=True),
            sa.Column(
                "thing_id",
                sa.Integer(),
                sa.ForeignKey("thing.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.UniqueConstraint("LocationId", name="AssociatedData$LocationId"),
        )
        op.create_index("AssociatedData$PointID", "NMA_AssociatedData", ["PointID"])


def downgrade() -> None:
    """Drop the legacy associated data table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_AssociatedData"):
        op.drop_table("NMA_AssociatedData")
