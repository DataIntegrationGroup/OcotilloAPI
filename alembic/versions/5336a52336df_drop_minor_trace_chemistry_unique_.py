"""drop minor trace chemistry unique constraint

Revision ID: 5336a52336df
Revises: e71807682f57
Create Date: 2026-02-18 14:22:00.874725

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5336a52336df"
down_revision: Union[str, Sequence[str], None] = "e71807682f57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "uq_minor_trace_chemistry_sample_analyte",
        "NMA_MinorTraceChemistry",
        type_="unique",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.create_unique_constraint(
        "uq_minor_trace_chemistry_sample_analyte",
        "NMA_MinorTraceChemistry",
        ["chemistry_sample_info_id", "analyte"],
    )
