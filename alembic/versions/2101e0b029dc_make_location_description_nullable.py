"""Make location description nullable

Revision ID: 2101e0b029dc
Revises: 66ac1af4ba69
Create Date: 2026-01-02 23:19:38.901275

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision: str = '2101e0b029dc'
down_revision: Union[str, Sequence[str], None] = '66ac1af4ba69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Makes the location.description column nullable to accommodate
    legacy data from MS Access that may not have descriptions.
    """
    op.alter_column('location', 'description',
                    existing_type=sa.String(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('location', 'description',
                    existing_type=sa.String(),
                    nullable=False)
