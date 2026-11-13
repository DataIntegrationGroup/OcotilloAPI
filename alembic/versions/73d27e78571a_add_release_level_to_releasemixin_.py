"""add release_level to ReleaseMixin tables

Revision ID: 73d27e78571a
Revises: 7480e4ee69dc
Create Date: 2026-11-13

Splits release_status's visibility half into release_level, per
docs/release-level-and-data-maturity-vocabulary.md. release_status stays
for now -- dropped in a later migration once every consumer has moved over.

Maps public->public, private->private, draft/provisional->pending by name
only (provisional only matters on the two transducer tables). We expect
published/final/archived to be empty everywhere (open question 2), so
rather than quietly defaulting them to pending too, the migration raises
if it finds one -- better to find out now.

Seven tables are __versioned__ (sqlalchemy_continuum) and need the same
column on their _version shadow table too, or writes to them fail -- same
pattern as e123456789ab_add_observation_data_quality.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "73d27e78571a"
down_revision: Union[str, Sequence[str], None] = "7480e4ee69dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY = "release_level"
CATEGORY_DESCRIPTION = (
    "Who may see a record: pending (no release decision made), private "
    "(explicitly withheld), or public (released)."
)
PENDING_DEFINITION = (
    "Not yet released to any audience, because no release decision has "
    "been made yet."
)
CATEGORY_TERMS = ("pending", "private", "public")

# Every table carrying ReleaseMixin's release_status column.
TABLES = (
    "address",
    "analysis_method",
    "aquifer_system",
    "aquifer_type",
    "asset",
    "contact",
    "data_provenance",
    "deployment",
    "email",
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
    "permission_history",
    "phone",
    "regulatory_limit",
    "sample",
    "sensor",
    "status_history",
    "stratigraphic_interval",
    "thing",
    "thing_aquifer_association",
    "thing_id_link",
    "transducer_observation",
    "transducer_observation_block",
    "well_casing_material",
    "well_purpose",
    "well_screen",
)

# __versioned__ (sqlalchemy_continuum) tables among the above -- their
# "_version" shadow table needs the same column too.
VERSIONED_TABLES = (
    "aquifer_system",
    "geologic_formation",
    "location",
    "observation",
    "parameter",
    "regulatory_limit",
    "thing",
)


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            "INSERT INTO lexicon_category (name, description) "
            "VALUES (:name, :description) ON CONFLICT (name) DO NOTHING"
        ),
        {"name": CATEGORY, "description": CATEGORY_DESCRIPTION},
    )
    connection.execute(
        sa.text(
            "INSERT INTO lexicon_term (term, definition) VALUES (:term, :definition) "
            "ON CONFLICT (term) DO NOTHING"
        ),
        {"term": "pending", "definition": PENDING_DEFINITION},
    )
    connection.execute(
        sa.text("""
            INSERT INTO lexicon_term_category_association (term_id, category_id)
            SELECT t.id, c.id
            FROM lexicon_term t, lexicon_category c
            WHERE t.term = ANY(:terms) AND c.name = :category
            ON CONFLICT DO NOTHING
            """),
        {"terms": list(CATEGORY_TERMS), "category": CATEGORY},
    )

    for table in TABLES:
        op.add_column(
            table,
            sa.Column("release_level", sa.String(length=100), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_release_level",
            table,
            "lexicon_term",
            ["release_level"],
            ["term"],
            onupdate="CASCADE",
        )

        for release_status, release_level in (
            ("public", "public"),
            ("private", "private"),
            ("draft", "pending"),
            ("provisional", "pending"),
        ):
            connection.execute(
                sa.text(
                    f'UPDATE "{table}" SET release_level = :release_level '
                    f"WHERE release_status = :release_status"
                ),
                {"release_status": release_status, "release_level": release_level},
            )

        unaccounted = connection.execute(
            sa.text(
                f'SELECT release_status, COUNT(*) FROM "{table}" '
                f"WHERE release_level IS NULL GROUP BY release_status"
            )
        ).all()
        if unaccounted:
            raise RuntimeError(
                f"{table}: release_status value(s) not handled by this "
                f"migration, refusing to guess a release_level for them: "
                f"{dict(unaccounted)}"
            )

    for table in VERSIONED_TABLES:
        op.add_column(
            f"{table}_version",
            sa.Column(
                "release_level",
                sa.String(length=100),
                sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for table in VERSIONED_TABLES:
        op.drop_column(f"{table}_version", "release_level")

    for table in TABLES:
        op.drop_constraint(f"fk_{table}_release_level", table, type_="foreignkey")
        op.drop_column(table, "release_level")

    # Lexicon terms/categories left in place -- same convention as
    # b2c3d4e5f6a7 and c89d6680bff6.
