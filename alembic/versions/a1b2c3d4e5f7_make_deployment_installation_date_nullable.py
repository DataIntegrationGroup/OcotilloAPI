"""make deployment installation_date nullable

Revision ID: a1b2c3d4e5f7
Revises: 9a0b1c2d3e4f
Create Date: 2026-02-21 14:32:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "9a0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "deployment",
        "installation_date",
        existing_type=sa.Date(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "deployment",
        "installation_date",
        existing_type=sa.Date(),
        nullable=False,
    )
