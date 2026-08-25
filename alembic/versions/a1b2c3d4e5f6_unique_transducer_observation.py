"""unique constraint on transducer_observation

Revision ID: a1b2c3d4e5f6
Revises: d9e0f1a2b3c4
Create Date: 2026-08-19

The table had only an index on (deployment_id, parameter_id,
observation_datetime), so nothing prevented the same reading being inserted
twice. That absence is what forces a delete-then-repost load strategy: without a
constraint to conflict on, a re-run can only avoid duplicates by removing what
is already there first, which leaves a window where the data is missing.

With this constraint the loader can use ON CONFLICT DO UPDATE and a re-run
becomes idempotent, so a backfill overlapping existing data is safe.

Note the constraint is on `deployment_id`, not `thing_id` -- the plan named a
column this table does not have. A deployment is a thing/sensor pairing, so two
sensors on the same well may legitimately report the same instant; scoping
uniqueness to the deployment allows that while still catching a re-inserted row.

**Run automated_ingestion/sql/find_duplicate_observations.sql first.** This
migration fails on a table that already violates the constraint, and it is
better to know that before starting than halfway through.
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_transducer_observation_deployment_parameter_datetime"
INDEX_NAME = "ix_transducer_observation_deployment_parameter_datetime"
COLUMNS = ["deployment_id", "parameter_id", "observation_datetime"]


def upgrade() -> None:
    # The unique constraint creates its own index on the same columns, so the
    # existing one would be redundant -- two indexes maintained on every insert
    # into the largest table in the schema.
    op.drop_index(INDEX_NAME, table_name="transducer_observation")
    op.create_unique_constraint(CONSTRAINT_NAME, "transducer_observation", COLUMNS)


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "transducer_observation", type_="unique")
    op.create_index(INDEX_NAME, "transducer_observation", COLUMNS)
