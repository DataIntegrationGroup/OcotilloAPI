"""Drop thing_id from NMA_Radionuclides

Revision ID: d9f1e2c3b4a5
Revises: 71a4c6b3d2e8
Create Date: 2026-02-04 15:32:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9f1e2c3b4a5"
down_revision: Union[str, Sequence[str], None] = "71a4c6b3d2e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_thing_id_fk_and_indexes(inspector) -> None:
    fks = inspector.get_foreign_keys("NMA_Radionuclides")
    for fk in fks:
        if "thing_id" in (fk.get("constrained_columns") or []):
            op.drop_constraint(fk["name"], "NMA_Radionuclides", type_="foreignkey")

    indexes = inspector.get_indexes("NMA_Radionuclides")
    for idx in indexes:
        if "thing_id" in (idx.get("column_names") or []):
            op.drop_index(idx["name"], table_name="NMA_Radionuclides")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("NMA_Radionuclides")]
    if "thing_id" in columns:
        _drop_thing_id_fk_and_indexes(inspector)
        op.drop_column("NMA_Radionuclides", "thing_id")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("NMA_Radionuclides")]
    if "thing_id" not in columns:
        op.add_column(
            "NMA_Radionuclides",
            sa.Column("thing_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_nma_radionuclides_thing_id",
            "NMA_Radionuclides",
            "thing",
            ["thing_id"],
            ["id"],
            ondelete="CASCADE",
        )
