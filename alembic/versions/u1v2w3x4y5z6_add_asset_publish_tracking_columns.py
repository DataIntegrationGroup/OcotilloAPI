"""add asset publish tracking columns

Revision ID: u1v2w3x4y5z6
Revises: t6u7v8w9x0y1
Create Date: 2026-04-17 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, Sequence[str], None] = "a8c9d0e1f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("publish_target", sa.String(), nullable=True))
    op.add_column("asset", sa.Column("publish_status", sa.String(), nullable=True))
    op.add_column("asset", sa.Column("publish_workspace", sa.String(), nullable=True))
    op.add_column("asset", sa.Column("publish_store_name", sa.String(), nullable=True))
    op.add_column("asset", sa.Column("publish_layer_name", sa.String(), nullable=True))
    op.add_column(
        "asset",
        sa.Column(
            "publish_last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column("asset", sa.Column("publish_last_error", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("asset", "publish_last_error")
    op.drop_column("asset", "publish_last_attempt_at")
    op.drop_column("asset", "publish_layer_name")
    op.drop_column("asset", "publish_store_name")
    op.drop_column("asset", "publish_workspace")
    op.drop_column("asset", "publish_status")
    op.drop_column("asset", "publish_target")
