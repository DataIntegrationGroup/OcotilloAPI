"""add nma_data_quality to observation

Revision ID: e123456789ab
Revises: b12e3919077e
Create Date: 2026-02-05 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e123456789ab"
down_revision: Union[str, Sequence[str], None] = "b12e3919077e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "observation",
        sa.Column(
            "nma_data_quality",
            sa.String(length=100),
            sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "observation_version",
        sa.Column(
            "nma_data_quality",
            sa.String(length=100),
            sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("observation_version", "nma_data_quality")
    op.drop_column("observation", "nma_data_quality")
