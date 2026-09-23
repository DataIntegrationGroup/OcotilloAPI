"""index the per-row lookups in the water well field operations layer

`ogc_internal_water_well_field_operations` reaches three tables once per output
row: `group_thing_association` through the `grp` LATERAL, and `phone` and
`email` through the primary_contact_phone/primary_contact_email correlated
subqueries. None of the three had an index on the column being looked up --
Postgres does not index foreign keys on its own -- so each lookup was a
sequential scan, executed 10 034 times on staging (one per water well).

Measured on staging (ocotillo-staging, 10 034 wells, PostgreSQL 17.9), full
layer download, 16 376 ms total:

    Seq Scan on group_thing_association   10 034 loops   10 736 ms
    Seq Scan on phone                     10 034 loops    1 475 ms
    Seq Scan on email                     10 034 loops      780 ms

~13 s of the 16.4 s. The same three scans dominate the ordinary paged request
that clients actually make: `ORDER BY id LIMIT 10` measured 14 417 ms, because
the sort computes every row's columns before the limit applies.

Not included, deliberately:

- No index on `notes`. The 13 note columns are also per-row correlated
  subqueries, but `ix_notes_polymorphic_link (target_id, target_table)` already
  serves them -- they do not appear among the costed nodes in the staging plan.
- No change to the view itself. With these indexes the LATERAL becomes an index
  scan; restructuring the SQL would carry correctness risk for no measured gain.
- Plain CREATE INDEX, not CONCURRENTLY, which cannot run inside alembic's
  transaction. All three tables are small (under 500 kB on staging), so the
  lock is brief.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_group_thing_association_thing_id", "group_thing_association", ["thing_id"]),
    ("ix_phone_contact_id", "phone", ["contact_id"]),
    ("ix_email_contact_id", "email", ["contact_id"]),
]


def upgrade() -> None:
    for index_name, table_name, columns in INDEXES:
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    for index_name, table_name, _columns in INDEXES:
        op.drop_index(index_name, table_name=table_name, if_exists=True)
