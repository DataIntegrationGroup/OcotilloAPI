"""make measuring_point_history.measuring_point_height nullable

Revision ID: 8c9d0e1f2a3b
Revises: 5336a52336df
Create Date: 2026-02-21 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c9d0e1f2a3b"
down_revision: Union[str, Sequence[str], None] = "5336a52336df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "measuring_point_history",
        "measuring_point_height",
        existing_type=sa.Numeric(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "measuring_point_history",
        "measuring_point_height",
        existing_type=sa.Numeric(),
        nullable=False,
    )
