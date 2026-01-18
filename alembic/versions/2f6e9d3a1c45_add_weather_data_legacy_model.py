"""add weather data legacy model

Revision ID: 2f6e9d3a1c45
Revises: 8ed4b9770721
Create Date: 2026-01-09 09:42:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2f6e9d3a1c45"
down_revision: Union[str, Sequence[str], None] = "8ed4b9770721"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "NMA_WeatherData"

    if not inspector.has_table(table_name):
        op.create_table(
            table_name,
            sa.Column("LocationId", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("PointID", sa.String(length=10), nullable=False),
            sa.Column("WeatherID", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("OBJECTID", sa.Integer(), primary_key=True),
        )
        return

    pk = inspector.get_pk_constraint(table_name)
    pk_columns = pk.get("constrained_columns") or []
    if pk_columns != ["OBJECTID"]:
        op.create_primary_key(
            "NMA_WeatherData_pkey",
            table_name,
            ["OBJECTID"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("NMA_WeatherData")
