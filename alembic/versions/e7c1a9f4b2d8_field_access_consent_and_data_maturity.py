"""rename permission_history to field_access_consent; add data_maturity

Two vocabulary fixes from ADR5, neither of which changes any API response
shape:

1. ``permission_history`` records a landowner's consent to physical site
   access. It is a domain fact, not authorization, and the name implied
   otherwise. It becomes ``field_access_consent``. The ``permission_type``
   and ``permission_allowed`` columns keep their names -- ``permission_type``
   is lexicon-backed, and both are published in Thing responses.

2. ``release_status`` was one column carrying two axes. Its lexicon lists
   `draft`, `public`, `private`, `published`, `archived` (visibility) next to
   `provisional` and `final` (review state), so a record could not be public
   and provisional at once -- which San Acacia data is (see
   automated_ingestion/ocotillo/loader.py). Release *level* stays in
   ``release_status``; review state moves to ``data_maturity``.

   ``data_maturity`` is not a new vocabulary. The lexicon category
   (`provisional`, `in review`, `approved`) and the column already existed on
   ``transducer_observation``; this generalizes them onto every ReleaseMixin
   table, so ``transducer_observation`` is deliberately absent from the list
   below -- it already has the column, unchanged.

``data_maturity`` is nullable and starts NULL, meaning "not stated". No
existing row changes meaning. Rows that carry `release_status='provisional'`
are left alone; splitting them onto the two axes is a data migration with its
own decision to make.

Revision ID: e7c1a9f4b2d8
Revises: c9d0e1f2a3b4
Create Date: 2026-08-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c1a9f4b2d8"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table backed by a model that mixes in ReleaseMixin, with
# permission_history already under its new name and transducer_observation
# omitted because it already carries data_maturity.
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
    "transducer_observation_block",
    "well_casing_material",
    "well_purpose",
    "well_screen",
)

# sqlalchemy-continuum mirrors every tracked column into the version table, so
# the models carrying __versioned__ need the new column there too. Version rows
# are written explicitly and historical rows have no answer, so it is nullable.
VERSION_TABLES = (
    "aquifer_system_version",
    "geologic_formation_version",
    "location_version",
    "observation_version",
    "parameter_version",
    "regulatory_limit_version",
    "thing_version",
)


def upgrade() -> None:
    op.rename_table("permission_history", "field_access_consent")
    # rename_table leaves the constraint and sequence names behind, which is
    # cosmetic but makes the old name resurface in every error message.
    op.execute(
        sa.text(
            "ALTER TABLE field_access_consent "
            "RENAME CONSTRAINT permission_history_pkey TO field_access_consent_pkey"
        )
    )
    op.execute(
        sa.text(
            "ALTER SEQUENCE IF EXISTS permission_history_id_seq "
            "RENAME TO field_access_consent_id_seq"
        )
    )

    for table in RELEASE_TABLES:
        op.add_column(
            table,
            sa.Column(
                "data_maturity",
                sa.String(length=100),
                nullable=True,
                comment="Review state; orthogonal to release_status",
            ),
        )
        op.create_foreign_key(
            f"{table}_data_maturity_fkey",
            table,
            "lexicon_term",
            ["data_maturity"],
            ["term"],
            onupdate="CASCADE",
        )

    for table in VERSION_TABLES:
        op.add_column(
            table,
            sa.Column(
                "data_maturity",
                sa.String(length=100),
                autoincrement=False,
                nullable=True,
            ),
        )


def downgrade() -> None:
    for table in VERSION_TABLES:
        op.drop_column(table, "data_maturity")

    for table in RELEASE_TABLES:
        op.drop_constraint(f"{table}_data_maturity_fkey", table, type_="foreignkey")
        op.drop_column(table, "data_maturity")

    op.execute(
        sa.text(
            "ALTER SEQUENCE IF EXISTS field_access_consent_id_seq "
            "RENAME TO permission_history_id_seq"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE field_access_consent "
            "RENAME CONSTRAINT field_access_consent_pkey TO permission_history_pkey"
        )
    )
    op.rename_table("field_access_consent", "permission_history")
