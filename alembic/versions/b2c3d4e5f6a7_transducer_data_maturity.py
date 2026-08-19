"""data_maturity on transducer_observation

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-19

`release_status` is one column whose lexicon lists `public` and `provisional` as
siblings, so a reading cannot be both visible and marked unreviewed. Those are
orthogonal: visibility is who may see it, maturity is how much it should be
trusted. This adds the second axis.

Terms follow USGS usage. `provisional` and `approved` are what USGS publishes
against -- "provisional data subject to revision" is the standard caveat on
unapproved records. `in review` is the intermediate state from the Aquarius
approval levels USGS uses for continuous time series (Working / In Review /
Approved); Aquarius' `Working` is folded into `provisional` because the two are
indistinguishable to a consumer.

Existing rows are backfilled from the legacy AMPAPI QC flag,
`nma_waterlevelscontinuous_pressure_qced`, which records exactly this: whether a
reading has been quality controlled. True becomes `approved`, false becomes
`provisional`.

Rows where that flag is NULL stay NULL. Those did not come from the NMA
transducer tables, so there is no evidence either way, and NULL reads as "not
stated" -- which is true, where guessing would not be.
"""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

CATEGORY = "data_maturity"
TERMS = ("provisional", "in review", "approved")


def upgrade() -> None:
    connection = op.get_bind()

    # `lexicon_term.term` is globally unique and categories share terms through
    # an association table, so `provisional` and `approved` already exist from
    # `release_status` and `review_status`. Only the intermediate state is new.
    connection.execute(
        sa.text(
            "INSERT INTO lexicon_term (term, definition) VALUES (:term, :definition) "
            "ON CONFLICT (term) DO NOTHING"
        ),
        {
            "term": "in review",
            "definition": (
                "Under review and not yet approved. Intermediate state from the "
                "USGS Aquarius approval levels used for continuous records."
            ),
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO lexicon_category (name) VALUES (:name) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": CATEGORY},
    )
    connection.execute(
        sa.text("""
            INSERT INTO lexicon_term_category_association (term_id, category_id)
            SELECT t.id, c.id
            FROM lexicon_term t, lexicon_category c
            WHERE t.term = ANY(:terms) AND c.name = :category
            ON CONFLICT DO NOTHING
            """),
        {"terms": list(TERMS), "category": CATEGORY},
    )

    op.add_column(
        "transducer_observation",
        sa.Column(
            "data_maturity",
            sa.String(length=100),
            nullable=True,
            comment=(
                "How far through review this reading is. Orthogonal to "
                "release_status, which controls visibility. NULL means not stated."
            ),
        ),
    )
    op.create_foreign_key(
        "fk_transducer_observation_data_maturity",
        "transducer_observation",
        "lexicon_term",
        ["data_maturity"],
        ["term"],
        onupdate="CASCADE",
    )

    # The legacy QC flag answers this question directly, so the maturity of
    # historical rows is a lookup rather than a guess. Done after the foreign
    # key so a bad value here would fail loudly rather than persist.
    connection.execute(sa.text("""
            UPDATE transducer_observation
               SET data_maturity = CASE
                     WHEN nma_waterlevelscontinuous_pressure_qced THEN 'approved'
                     ELSE 'provisional'
                   END
             WHERE nma_waterlevelscontinuous_pressure_qced IS NOT NULL
            """))


def downgrade() -> None:
    op.drop_constraint(
        "fk_transducer_observation_data_maturity",
        "transducer_observation",
        type_="foreignkey",
    )
    op.drop_column("transducer_observation", "data_maturity")

    # The terms are left in place. They may have been adopted elsewhere by the
    # time this is reversed, and an unused lexicon term is harmless where a
    # missing one breaks a foreign key.
