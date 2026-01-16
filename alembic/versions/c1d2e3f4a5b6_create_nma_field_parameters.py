"""Create legacy NMA_FieldParameters table.

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-03-01 03:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy field parameters table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_FieldParameters"):
        op.create_table(
            "NMA_FieldParameters",
            sa.Column(
                "GlobalID",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                primary_key=True,
            ),
            sa.Column(
                "SamplePtID",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(
                    "NMA_Chemistry_SampleInfo.SamplePtID",
                    onupdate="CASCADE",
                    ondelete="CASCADE",
                ),
                nullable=False,
            ),
            sa.Column("SamplePointID", sa.String(length=10), nullable=True),
            sa.Column("FieldParameter", sa.String(length=50), nullable=True),
            sa.Column(
                "SampleValue", sa.Float(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column("Units", sa.String(length=50), nullable=True),
            sa.Column("Notes", sa.String(length=255), nullable=True),
            sa.Column(
                "OBJECTID",
                sa.Integer(),
                sa.Identity(start=1),
                nullable=False,
            ),
            sa.Column("AnalysesAgency", sa.String(length=50), nullable=True),
            sa.Column("WCLab_ID", sa.String(length=25), nullable=True),
        )
        op.create_index(
            "FieldParameters$AnalysesAgency",
            "NMA_FieldParameters",
            ["AnalysesAgency"],
        )
        op.create_index(
            "FieldParameters$Chemistry SampleInfoFieldParameters",
            "NMA_FieldParameters",
            ["SamplePtID"],
        )
        op.create_index(
            "FieldParameters$FieldParameter",
            "NMA_FieldParameters",
            ["FieldParameter"],
        )
        op.create_index(
            "FieldParameters$SamplePointID",
            "NMA_FieldParameters",
            ["SamplePointID"],
        )
        op.create_index(
            "FieldParameters$SamplePtID",
            "NMA_FieldParameters",
            ["SamplePtID"],
        )
        op.create_index(
            "FieldParameters$WCLab_ID",
            "NMA_FieldParameters",
            ["WCLab_ID"],
        )
        op.create_index(
            "FieldParameters$GlobalID",
            "NMA_FieldParameters",
            ["GlobalID"],
            unique=True,
        )
        op.create_index(
            "FieldParameters$OBJECTID",
            "NMA_FieldParameters",
            ["OBJECTID"],
            unique=True,
        )


def downgrade() -> None:
    """Drop the legacy field parameters table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_FieldParameters"):
        op.drop_table("NMA_FieldParameters")
