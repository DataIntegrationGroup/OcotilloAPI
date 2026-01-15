"""Add search_vector triggers for searchable tables.

Revision ID: e4f7a9c0b2d3
Revises: d2f4c6a8b1c2
Create Date: 2026-03-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "e4f7a9c0b2d3"
down_revision: Union[str, Sequence[str], None] = "d2f4c6a8b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEARCH_VECTOR_TRIGGERS = {
    "contact": ("name", "role", "organization", "nma_pk_owners"),
    "phone": ("phone_number",),
    "email": ("email",),
    "address": (
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
    ),
    "asset": ("name", "mime_type", "storage_service", "storage_path"),
    "thing": ("name",),
    "well_purpose": ("purpose",),
    "well_casing_material": ("material",),
    "publication": ("title", "abstract", "doi", "publisher", "url"),
    "pub_author": ("name", "affiliation"),
}


def _create_trigger(table: str, columns: Sequence[str]) -> None:
    trigger_name = f"{table}_search_vector_update"
    column_list = ", ".join(f"'{col}'" for col in columns)
    op.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "{table}"')
    op.execute(
        f"""
        CREATE TRIGGER "{trigger_name}"
        BEFORE INSERT OR UPDATE ON "{table}"
        FOR EACH ROW EXECUTE FUNCTION
        tsvector_update_trigger('search_vector', 'pg_catalog.simple', {column_list});
        """
    )


def _drop_trigger(table: str) -> None:
    trigger_name = f"{table}_search_vector_update"
    op.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "{table}"')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table, columns in SEARCH_VECTOR_TRIGGERS.items():
        if not inspector.has_table(table):
            continue
        column_names = {col["name"] for col in inspector.get_columns(table)}
        if "search_vector" not in column_names:
            continue
        _create_trigger(table, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table in SEARCH_VECTOR_TRIGGERS:
        if inspector.has_table(table):
            _drop_trigger(table)
