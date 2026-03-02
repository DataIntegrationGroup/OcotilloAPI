"""add missing legacy fields

Revision ID: b12e3919077e
Revises: 263109252fb1
Create Date: 2026-01-29 16:50:57.568476

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b12e3919077e"
down_revision: Union[str, Sequence[str], None] = "263109252fb1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "NMA_SurfaceWaterData",
        sa.Column("LocationId", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.alter_column(
        "location",
        "nma_notes_location",
        new_column_name="nma_location_notes",
    )
    op.alter_column(
        "location_version",
        "nma_notes_location",
        new_column_name="nma_location_notes",
    )
    op.add_column(
        "location",
        sa.Column(
            "nma_data_reliability",
            sa.String(length=100),
            sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "location_version",
        sa.Column(
            "nma_data_reliability",
            sa.String(length=100),
            sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "location_version",
        "nma_location_notes",
        new_column_name="nma_notes_location",
    )
    op.alter_column(
        "location",
        "nma_location_notes",
        new_column_name="nma_notes_location",
    )
    op.drop_column("location_version", "nma_data_reliability")
    op.drop_column("location", "nma_data_reliability")
    op.drop_column("NMA_SurfaceWaterData", "LocationId")
