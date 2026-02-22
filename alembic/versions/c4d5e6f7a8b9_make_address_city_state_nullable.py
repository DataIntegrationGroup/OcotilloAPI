"""make address.city and address.state nullable

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-21 16:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "address",
        "city",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    op.alter_column(
        "address",
        "state",
        existing_type=sa.String(length=50),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "address",
        "city",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        "address",
        "state",
        existing_type=sa.String(length=50),
        nullable=False,
    )
