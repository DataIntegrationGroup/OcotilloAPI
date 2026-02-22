"""make address.postal_code nullable

Revision ID: 9a0b1c2d3e4f
Revises: 8c9d0e1f2a3b
Create Date: 2026-02-21 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a0b1c2d3e4f"
down_revision: Union[str, Sequence[str], None] = "8c9d0e1f2a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "address",
        "postal_code",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "address",
        "postal_code",
        existing_type=sa.String(length=20),
        nullable=False,
    )
