"""
Revision ID: 7b8c9d0e1f2a
Revises: c7f8a9b0c1d2
Create Date: 2026-02-02 00:00:00.000000

Removes the is_suitable_for_datalogger column from the thing and thing_version tables.
"""

# revision identifiers, used by Alembic.
revision = "7b8c9d0e1f2a"
down_revision = "c7f8a9b0c1d2"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column("thing", "is_suitable_for_datalogger")
    op.drop_column("thing_version", "is_suitable_for_datalogger")


def downgrade():
    op.add_column(
        "thing", sa.Column("is_suitable_for_datalogger", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "thing_version",
        sa.Column("is_suitable_for_datalogger", sa.Boolean(), nullable=True),
    )
