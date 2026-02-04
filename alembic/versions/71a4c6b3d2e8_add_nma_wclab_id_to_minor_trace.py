"""Add nma_WCLab_ID column to NMA_MinorTraceChemistry

Revision ID: 71a4c6b3d2e8
Revises: 50d1c2a3b4c5
Create Date: 2026-01-31 01:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "71a4c6b3d2e8"
down_revision: Union[str, Sequence[str], None] = "50d1c2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "NMA_MinorTraceChemistry",
        sa.Column("nma_WCLab_ID", sa.String(length=25), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("NMA_MinorTraceChemistry", "nma_WCLab_ID")
