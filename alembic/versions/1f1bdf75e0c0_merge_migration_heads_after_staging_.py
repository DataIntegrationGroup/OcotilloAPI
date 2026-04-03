"""merge migration heads after staging merge

Revision ID: 1f1bdf75e0c0
Revises: 545a5b77e5e8, t6u7v8w9x0y1
Create Date: 2026-04-03 10:12:48.253856

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision: str = '1f1bdf75e0c0'
down_revision: Union[str, Sequence[str], None] = ('545a5b77e5e8', 't6u7v8w9x0y1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
