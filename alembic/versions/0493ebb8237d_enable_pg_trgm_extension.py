"""enable pg_trgm extension

Revision ID: 0493ebb8237d
Revises: t6u7v8w9x0y1
Create Date: 2026-05-01 11:17:44.571959

"""

from typing import Sequence, Union

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0493ebb8237d"
down_revision: Union[str, Sequence[str], None] = "t6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


def downgrade() -> None:
    op.execute(text("DROP EXTENSION IF EXISTS pg_trgm"))
