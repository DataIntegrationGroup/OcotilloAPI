"""Add unique index for NGWMN well construction

Revision ID: 50d1c2a3b4c5
Revises: 3cb924ca51fd
Create Date: 2026-01-31 00:27:12.204176

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50d1c2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "3cb924ca51fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_ngwmn_wc_point_casing_screen"
TABLE_NAME = "NMA_view_NGWMN_WellConstruction"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["PointID", "CasingTop", "ScreenTop"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
