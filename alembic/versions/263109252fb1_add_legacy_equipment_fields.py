"""add legacy equipment fields

Revision ID: 263109252fb1
Revises: c1d2e3f4a5b6
Create Date: 2026-01-28 10:05:10.122531

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "263109252fb1"
down_revision: Union[str, Sequence[str], None] = "3a9c1f5b7d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
FIELDS = (
    "WI_Duration",
    "WI_EndFrequency",
    "WI_Magnitude",
    "WI_MicGain",
    "WI_MinSoundDepth",
    "WI_StartFrequency",
)


def upgrade() -> None:
    """Upgrade schema."""

    for field in FIELDS:
        op.add_column(
            "deployment",
            sa.Column(
                f"nma_{field}",
                sa.Integer(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for field in FIELDS:
        op.drop_column("deployment", f"nma_{field}")
