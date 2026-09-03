"""Index grants by principal, and ask for NGWMN consent once per row

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-03

Two costs found reviewing the access-control stack, both in the read path.

**The grant index did not match the query.** `ix_permission_grant_principal`
leads with `principal_type`, and `services.visibility.load_grants` filters on
`principal_id` alone -- it asks for every grant naming any of the caller's
identities, then lets `domain/access.py` decide, which is the whole point of
having the rules in one place. A leading column the query never constrains is
a column the planner cannot use, so every authorization check sequentially
scanned the table. Harmless at 85 rows and not harmless once grants are issued
per user.

The old index stays: the console lists grants by principal *and* capability,
and that query does constrain both.

**The NGWMN views asked twice per row.** Each needs two consents -- site
metadata for the identity it reports against, and the type it carries -- and
expressing that as two `= ANY(...)` calls invoked the function twice for every
row. Array containment asks the same question once.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Imported rather than restated: the bodies these views are built from live in
# the migration that first gated them, and a second copy would drift.
from alembic.versions.d6e7f8a9b0c1_gate_ngwmn_views_on_consent import (  # noqa: E402
    LITHOLOGY,
    WATER_LEVELS,
    WELL_CONSTRUCTION,
)

VIEWS = [
    ("NGWMN_WellConstruction", WELL_CONSTRUCTION, "well construction"),
    ("NGWMN_WaterLevels", WATER_LEVELS, "water level"),
    ("NGWMN_Lithology", LITHOLOGY, "well construction"),
]

# One function call, both consents. `@>` is "contains every element of".
FOLDED_PREDICATE = """
    AND destination_consent_types(t.id, 'ngwmn')
        @> ARRAY['site metadata', '{data_type}']::text[]
"""

# What d6e7f8a9b0c1 wrote, for the downgrade.
SPLIT_PREDICATE = """
    AND 'site metadata' = ANY(destination_consent_types(t.id, 'ngwmn'))
    AND '{data_type}' = ANY(destination_consent_types(t.id, 'ngwmn'))
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_permission_grant_principal_id",
        "permission_grant",
        ["principal_id"],
    )
    for name, body, data_type in VIEWS:
        predicate = FOLDED_PREDICATE.format(data_type=data_type)
        op.execute(f'CREATE OR REPLACE VIEW "{name}" AS {body}{predicate};')


def downgrade() -> None:
    """Downgrade schema."""
    for name, body, data_type in VIEWS:
        predicate = SPLIT_PREDICATE.format(data_type=data_type)
        op.execute(f'CREATE OR REPLACE VIEW "{name}" AS {body}{predicate};')
    op.drop_index("ix_permission_grant_principal_id", table_name="permission_grant")
