"""merge nmw mirror chain into staging head

Revision ID: 03ef547ed7be
Revises: e2f3a4b5c6d7, x2y3z4a5b6c7
Create Date: 2026-06-23 19:39:25.256933

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "03ef547ed7be"
down_revision: Union[str, Sequence[str], None] = ("e2f3a4b5c6d7", "x2y3z4a5b6c7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
