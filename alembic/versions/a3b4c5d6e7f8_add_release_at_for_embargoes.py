"""add release_at, the date an embargoed record becomes public

An embargo is a record withheld from public release until a date decided in
advance: `release_status = 'embargoed'` plus a `release_at`. This adds the
second half of that pair to every ReleaseMixin table.

`release_at` is intent, not enforcement. Nothing on the read path consults it:
`services/release_schedule.py` flips `release_status` to `public` when the date
arrives, and `release_status` stays the only column the OGC views filter on.
The reason is in that module -- seven of the public collections are
materialized views refreshed nightly, where a date predicate would be frozen
at refresh time and buy nothing.

Nullable, defaulting to NULL, meaning "no embargo". That default is
load-bearing rather than incidental: migration w1x2y3z4a5b6 records three
NGWMN exports emptied outright by a release predicate whose column defaulted
to something other than "released". No existing row changes meaning, and no
row is embargoed until somebody says so.

Unlike e7c1a9f4b2d8's data_maturity, `transducer_observation` is included --
it has no head start on this column.

Revision ID: a3b4c5d6e7f8
Revises: 79a3ab24627e
Create Date: 2026-09-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "79a3ab24627e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table backed by a model that mixes in ReleaseMixin.
RELEASE_TABLES = (
    "address",
    "analysis_method",
    "aquifer_system",
    "aquifer_type",
    "asset",
    "contact",
    "data_provenance",
    "deployment",
    "email",
    "field_access_consent",
    "field_activity",
    "field_event",
    "field_event_participant",
    "geologic_formation",
    "group",
    "location",
    "measuring_point_history",
    "monitoring_frequency_history",
    "notes",
    "observation",
    "parameter",
    "phone",
    "regulatory_limit",
    "sample",
    "sensor",
    "status_history",
    "thing",
    "thing_aquifer_association",
    "thing_geologic_formation_association",
    "thing_id_link",
    "transducer_observation",
    "transducer_observation_block",
    "well_casing_material",
    "well_purpose",
    "well_screen",
)

# sqlalchemy-continuum mirrors every tracked column into the version table, so
# the models carrying __versioned__ need the new column there too.
VERSION_TABLES = (
    "aquifer_system_version",
    "geologic_formation_version",
    "location_version",
    "observation_version",
    "parameter_version",
    "regulatory_limit_version",
    "thing_version",
)

COMMENT = (
    "Date an embargoed record becomes public. NULL means no embargo. "
    "Read by services/release_schedule.py, never by the read path."
)

# An embargo names its date, and a date means an embargo. Enforced in the
# table because the schema layer cannot: a PATCH body carrying only
# `release_status` is a fragment, not a row, and the CLI, the transfers and
# psql do not go through pydantic at all. Every existing row satisfies it --
# release_at starts NULL everywhere and nothing is embargoed yet -- so the
# constraint validates without a scan finding anything.
#
# Not applied to the _version tables: those record history, and a constraint
# on what a past state may have been would be a claim nobody checked.
CHECK_NAME = "{table}_embargo_needs_date"
CHECK_SQL = (
    "(release_status = 'embargoed' AND release_at IS NOT NULL) "
    "OR (release_status IS DISTINCT FROM 'embargoed' AND release_at IS NULL)"
)


def upgrade() -> None:
    for table in RELEASE_TABLES:
        op.add_column(
            table,
            sa.Column("release_at", sa.Date(), nullable=True, comment=COMMENT),
        )

    for table in RELEASE_TABLES:
        op.create_check_constraint(
            CHECK_NAME.format(table=table), table, sa.text(CHECK_SQL)
        )

    for table in VERSION_TABLES:
        op.add_column(
            table,
            sa.Column("release_at", sa.Date(), autoincrement=False, nullable=True),
        )


def downgrade() -> None:
    for table in VERSION_TABLES:
        op.drop_column(table, "release_at")

    for table in RELEASE_TABLES:
        op.drop_constraint(CHECK_NAME.format(table=table), table, type_="check")
        op.drop_column(table, "release_at")
