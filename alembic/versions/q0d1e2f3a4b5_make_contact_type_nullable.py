"""make contact type nullable

Revision ID: q0d1e2f3a4b5
Revises: p9c1d2e3f4a5
Create Date: 2026-03-11 17:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "q0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "p9c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "contact",
        "contact_type",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "contact",
        "contact_type",
        existing_type=sa.String(length=100),
        nullable=False,
    )
