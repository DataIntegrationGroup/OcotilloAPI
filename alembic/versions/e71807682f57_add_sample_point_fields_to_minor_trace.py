"""add sample point fields to minor trace

Revision ID: e71807682f57
Revises: h1b2c3d4e5f6
Create Date: 2026-02-10 20:07:25.586385

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e71807682f57"
down_revision: Union[str, Sequence[str], None] = "h1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "NMA_MinorTraceChemistry",
        sa.Column("nma_SamplePointID", sa.String(length=10), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("NMA_MinorTraceChemistry", "nma_SamplePointID")
