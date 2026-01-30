"""merge_migrations_after_staging_merge

Revision ID: 43bc34504ee6
Revises: 3cb924ca51fd, e123456789ab
Create Date: 2026-01-30 11:52:41.932306

"""

from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
import sqlalchemy_utils

# revision identifiers, used by Alembic.
revision: str = "43bc34504ee6"
down_revision: Union[str, Sequence[str], None] = ("3cb924ca51fd", "e123456789ab")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
