"""add group search vector

Revision ID: y3z4a5b6c7d8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-06 16:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op


revision: str = "y3z4a5b6c7d8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "group",
        sa.Column(
            "search_vector",
            sqlalchemy_utils.types.ts_vector.TSVectorType(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_group_search_vector",
        "group",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        """
        UPDATE "group"
        SET search_vector = to_tsvector(
            'pg_catalog.simple',
            concat_ws(' ', name, description, group_type)
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER "group_search_vector_update"
        BEFORE INSERT OR UPDATE ON "group"
        FOR EACH ROW EXECUTE PROCEDURE
        tsvector_update_trigger(
            'search_vector',
            'pg_catalog.simple',
            'name',
            'description',
            'group_type'
        )
        """
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS "group_search_vector_update" ON "group"')
    op.drop_index("ix_group_search_vector", table_name="group", postgresql_using="gin")
    op.drop_column("group", "search_vector")
