"""merge staging migrations

Revision ID: 2d67da5ff3ae
Revises: 1d2c3b4a5e67, g4a5b6c7d8e9
Create Date: 2026-01-21 12:24:14.992587

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision: str = '2d67da5ff3ae'
down_revision: Union[str, Sequence[str], None] = ('1d2c3b4a5e67', 'g4a5b6c7d8e9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
