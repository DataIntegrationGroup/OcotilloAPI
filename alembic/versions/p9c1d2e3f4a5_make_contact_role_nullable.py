"""make contact role nullable

Revision ID: p9c1d2e3f4a5
Revises: o8b9c0d1e2f3
Create Date: 2026-03-11 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "p9c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "o8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "contact", "role", existing_type=sa.String(length=100), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "contact", "role", existing_type=sa.String(length=100), nullable=False
    )
