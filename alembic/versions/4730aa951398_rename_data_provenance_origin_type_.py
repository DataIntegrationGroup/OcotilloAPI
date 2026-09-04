"""rename data_provenance origin_type/source_type and origin_source/source_reference

Revision ID: 4730aa951398
Revises: e1f2a3b4c5d6
Create Date: 2026-09-04 10:35:20.442868

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision: str = '4730aa951398'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename DataProvenance columns for clarity.

    origin_type   -> source_type      (provenance classification)
    origin_source -> source_reference  (specific citation)

    Postgres auto-follows the existing FK constraint on ``origin_type`` to
    ``lexicon_term.term`` during a column rename, so no index/FK recreation is
    required and the initial migration stays untouched.
    """
    op.execute("ALTER TABLE data_provenance RENAME COLUMN origin_type TO source_type;")
    op.execute(
        "ALTER TABLE data_provenance RENAME COLUMN origin_source TO source_reference;"
    )
    # Postgres auto-follows the FK to lexicon_term.term on column rename but does
    # not rename the constraint, so keep its name consistent with the new column.
    op.execute(
        "ALTER TABLE data_provenance RENAME CONSTRAINT data_provenance_origin_type_fkey "
        "TO data_provenance_source_type_fkey;"
    )


def downgrade() -> None:
    """Revert the DataProvenance column renames."""
    op.execute(
        "ALTER TABLE data_provenance RENAME CONSTRAINT data_provenance_source_type_fkey "
        "TO data_provenance_origin_type_fkey;"
    )
    op.execute(
        "ALTER TABLE data_provenance RENAME COLUMN source_reference TO origin_source;"
    )
    op.execute("ALTER TABLE data_provenance RENAME COLUMN source_type TO origin_type;")
