"""change NMA_MinorTraceChemistry volume from Float to Integer

Revision ID: g4a5b6c7d8e9
Revises: f3b4c5d6e7f8
Create Date: 2026-01-14 12:00:00.000000

This migration changes the volume column in NMA_MinorTraceChemistry from Float to Integer
to match the source database schema (NM_Aquifer_Dev_DB).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "f3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change volume column from Float to Integer."""
    op.alter_column(
        "NMA_MinorTraceChemistry",
        "volume",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="volume::integer",
    )


def downgrade() -> None:
    """Revert volume column from Integer back to Float."""
    op.alter_column(
        "NMA_MinorTraceChemistry",
        "volume",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
    )
