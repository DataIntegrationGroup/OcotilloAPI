"""add NMA chemistry lineage relations

Revision ID: 95d8b982cd5d
Revises: 2f6e9d3a1c45
Create Date: 2026-01-09 00:55:48.545861

This migration adds:
1. thing_id FK column to NMA_Chemistry_SampleInfo (NOT NULL, no orphans)
2. NMA_MinorTraceChemistry table (child of NMA_Chemistry_SampleInfo)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "95d8b982cd5d"
down_revision: Union[str, Sequence[str], None] = "2f6e9d3a1c45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("NMA_Chemistry_SampleInfo")}
    if "thing_id" not in columns:
        # Add thing_id FK to NMA_Chemistry_SampleInfo (NOT NULL - no orphans)
        op.add_column(
            "NMA_Chemistry_SampleInfo",
            sa.Column("thing_id", sa.Integer(), nullable=False),
        )

    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("NMA_Chemistry_SampleInfo")
        if fk.get("name")
    }
    if "fk_chemistry_sample_info_thing" not in existing_fks:
        op.create_foreign_key(
            "fk_chemistry_sample_info_thing",
            "NMA_Chemistry_SampleInfo",
            "thing",
            ["thing_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Create NMA_MinorTraceChemistry table
    op.create_table(
        "NMA_MinorTraceChemistry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "chemistry_sample_info_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("analyte", sa.String(50), nullable=True),
        sa.Column("sample_value", sa.Float(), nullable=True),
        sa.Column("units", sa.String(20), nullable=True),
        sa.Column("symbol", sa.String(10), nullable=True),
        sa.Column("analysis_method", sa.String(100), nullable=True),
        sa.Column("analysis_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("analyses_agency", sa.String(100), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("volume_unit", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["chemistry_sample_info_id"],
            ["NMA_Chemistry_SampleInfo.SamplePtID"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("NMA_MinorTraceChemistry")
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("NMA_Chemistry_SampleInfo")
        if fk.get("name")
    }
    if "fk_chemistry_sample_info_thing" in existing_fks:
        op.drop_constraint(
            "fk_chemistry_sample_info_thing",
            "NMA_Chemistry_SampleInfo",
            type_="foreignkey",
        )
    columns = {col["name"] for col in inspector.get_columns("NMA_Chemistry_SampleInfo")}
    if "thing_id" in columns:
        op.drop_column("NMA_Chemistry_SampleInfo", "thing_id")
