"""add NMW_Sources mirror table

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-18

1:1 mirror of the NM_Wells tbl_sources publication/data-source registry.
Keyed by the free-text SourceID string that appears in NMW_WellRecords.SourceID.
Needed to join publication attribution (FirstAuth, PubYear, Title, etc.)
into the ogc_heat_flow view.
"""

from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "NMW_Sources",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("SourceID", sa.String(), nullable=True),
        sa.Column("FirstAuth", sa.String(), nullable=True),
        sa.Column("PubYear", sa.String(), nullable=True),
        sa.Column("Title", sa.String(), nullable=True),
        sa.Column("Journal", sa.String(), nullable=True),
        sa.Column("Volume", sa.String(), nullable=True),
        sa.Column("PageNo", sa.String(), nullable=True),
        sa.Column("ReportNo", sa.String(), nullable=True),
        sa.Column("Publisher", sa.String(), nullable=True),
        sa.Column("City", sa.String(), nullable=True),
        sa.Column("URL", sa.String(), nullable=True),
        sa.Column("Comments", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index("ix_NMW_Sources_SourceID", "NMW_Sources", ["SourceID"])


def downgrade() -> None:
    op.drop_index("ix_NMW_Sources_SourceID", table_name="NMW_Sources")
    op.drop_table("NMW_Sources")
