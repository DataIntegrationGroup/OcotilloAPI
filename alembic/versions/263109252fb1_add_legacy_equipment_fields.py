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
    ("WI_Duration", sa.Integer()),
    ("WI_EndFrequency", sa.Integer()),
    ("WI_Magnitude", sa.Integer()),
    ("WI_MicGain", sa.Boolean()),
    ("WI_MinSoundDepth", sa.Integer()),
    ("WI_StartFrequency", sa.Integer()),
)


def upgrade() -> None:
    """Upgrade schema."""

    for field, column_type in FIELDS:
        op.add_column(
            "deployment",
            sa.Column(
                f"nma_{field}",
                column_type,
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for field, _ in FIELDS:
        op.drop_column("deployment", f"nma_{field}")
