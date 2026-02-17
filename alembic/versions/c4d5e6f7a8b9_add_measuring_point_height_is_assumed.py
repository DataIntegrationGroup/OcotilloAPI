"""Add measuring_point_height_is_assumed to measuring_point_history.

Revision ID: c4d5e6f7a8b9
Revises: e71807682f57
Create Date: 2026-02-16 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "e71807682f57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("measuring_point_history"):
        columns = {
            col["name"] for col in inspector.get_columns("measuring_point_history")
        }
        if "measuring_point_height_is_assumed" not in columns:
            op.add_column(
                "measuring_point_history",
                sa.Column(
                    "measuring_point_height_is_assumed",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("measuring_point_history"):
        columns = {
            col["name"] for col in inspector.get_columns("measuring_point_history")
        }
        if "measuring_point_height_is_assumed" in columns:
            op.drop_column(
                "measuring_point_history", "measuring_point_height_is_assumed"
            )
