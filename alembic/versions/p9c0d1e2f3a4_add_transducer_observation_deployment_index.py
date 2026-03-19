"""Add transducer observation deployment lookup index.

Revision ID: p9c0d1e2f3a4
Revises: o8b9c0d1e2f3
Create Date: 2026-03-19 11:05:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "p9c0d1e2f3a4"
down_revision = "o8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_transducer_observation_deployment_parameter_datetime",
        "transducer_observation",
        ["deployment_id", "parameter_id", "observation_datetime"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transducer_observation_deployment_parameter_datetime",
        table_name="transducer_observation",
    )
