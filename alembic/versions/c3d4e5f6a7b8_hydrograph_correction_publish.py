"""publish provenance for corrected transducer blocks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-19

The hydrograph corrector publishes a *derived* series: water head converted to
depth below ground surface against manual anchors, then shifted, snapped, and
drift-corrected. None of those numbers are what the instrument recorded, so the
database has to carry enough to tell a reviewer what happened to them.

Three columns on the block cover the batch: the file it came from, whether that
file held water head or depth to water, and the ordered list of corrections
applied. `comment` already exists and takes the publisher's free-text note.

One column on the observation covers the row: `note`, set only on readings a
correction actually moved. NULL therefore means "as measured", which is the
distinction review needs. The legacy `nma_waterlevelscontinuous_*_notes`
columns cannot serve -- each is scoped to one legacy source table.

The block time-order check is relaxed from `>` to `>=`. A block spanning a
single instant is legitimate: a published file with one reading, or a block
narrowed by a range delete until one observation survives. The block reader
matches observations inclusively on both bounds, so a zero-width block still
covers its reading. Loosening a check constraint cannot invalidate existing
rows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

# Spelled as it exists in the database, typo included -- renaming it here would
# leave deployed environments with a constraint this migration cannot find.
TIME_ORDER_CONSTRAINT = "check_transuder_block_time_order"


def upgrade() -> None:
    op.add_column(
        "transducer_observation_block",
        sa.Column(
            "source_file",
            sa.String(length=255),
            nullable=True,
            comment="Name of the logger file the corrected series was derived from",
        ),
    )
    op.add_column(
        "transducer_observation_block",
        sa.Column(
            "source_kind",
            sa.String(length=50),
            nullable=True,
            comment="What the source file measured: water_head or depth_to_water",
        ),
    )
    op.add_column(
        "transducer_observation_block",
        sa.Column(
            "corrections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Corrections applied to the source series, in applied order",
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "note",
            sa.Text(),
            nullable=True,
            comment=(
                "Per-reading correction annotation; NULL means the value is as "
                "measured"
            ),
        ),
    )

    op.drop_constraint(
        TIME_ORDER_CONSTRAINT, "transducer_observation_block", type_="check"
    )
    op.create_check_constraint(
        TIME_ORDER_CONSTRAINT,
        "transducer_observation_block",
        "end_datetime >= start_datetime",
    )


def downgrade() -> None:
    # Zero-width blocks may have been created while the loosened constraint was
    # in force, so widen them by a second rather than let the stricter
    # constraint fail to validate. A one-second span on a block that covered an
    # instant is a smaller lie than a failed downgrade.
    op.execute(
        "UPDATE transducer_observation_block "
        "SET end_datetime = start_datetime + interval '1 second' "
        "WHERE end_datetime = start_datetime"
    )
    op.drop_constraint(
        TIME_ORDER_CONSTRAINT, "transducer_observation_block", type_="check"
    )
    op.create_check_constraint(
        TIME_ORDER_CONSTRAINT,
        "transducer_observation_block",
        "end_datetime > start_datetime",
    )

    op.drop_column("transducer_observation", "note")
    op.drop_column("transducer_observation_block", "corrections")
    op.drop_column("transducer_observation_block", "source_kind")
    op.drop_column("transducer_observation_block", "source_file")
