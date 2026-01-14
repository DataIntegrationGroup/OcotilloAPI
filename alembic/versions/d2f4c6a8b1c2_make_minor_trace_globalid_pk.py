"""Make GlobalID the primary key for NMA_MinorTraceChemistry.

Revision ID: d2f4c6a8b1c2
Revises: 6e1c90f6135a
Create Date: 2026-03-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d2f4c6a8b1c2"
down_revision: Union[str, Sequence[str], None] = "6e1c90f6135a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_MinorTraceChemistry"):
        return

    columns = {col["name"] for col in inspector.get_columns("NMA_MinorTraceChemistry")}
    if "GlobalID" not in columns:
        op.add_column(
            "NMA_MinorTraceChemistry",
            sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=False),
        )

    pk = inspector.get_pk_constraint("NMA_MinorTraceChemistry")
    pk_name = pk.get("name")
    if pk_name:
        op.drop_constraint(pk_name, "NMA_MinorTraceChemistry", type_="primary")

    if "id" in columns:
        op.drop_column("NMA_MinorTraceChemistry", "id")

    op.create_primary_key(
        "NMA_MinorTraceChemistry_pkey",
        "NMA_MinorTraceChemistry",
        ["GlobalID"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_MinorTraceChemistry"):
        return

    op.drop_constraint(
        "NMA_MinorTraceChemistry_pkey",
        "NMA_MinorTraceChemistry",
        type_="primary",
    )
    op.add_column(
        "NMA_MinorTraceChemistry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    )
    op.create_primary_key(
        "NMA_MinorTraceChemistry_id_pkey",
        "NMA_MinorTraceChemistry",
        ["id"],
    )
    op.drop_column("NMA_MinorTraceChemistry", "GlobalID")
