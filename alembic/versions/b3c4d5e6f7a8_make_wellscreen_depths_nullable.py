"""make wellscreen depth fields nullable

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f7
Create Date: 2026-02-21 15:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "well_screen",
        "screen_depth_top",
        existing_type=sa.Float(),
        nullable=True,
    )
    op.alter_column(
        "well_screen",
        "screen_depth_bottom",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "well_screen",
        "screen_depth_bottom",
        existing_type=sa.Float(),
        nullable=False,
    )
    op.alter_column(
        "well_screen",
        "screen_depth_top",
        existing_type=sa.Float(),
        nullable=False,
    )
