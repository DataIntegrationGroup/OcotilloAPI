"""promote thing_geologic_formation_association to stratigraphic_interval (BDMS-1554)

``thing_geologic_formation_association`` was used as a well's stratigraphic
log, but it could only say which formation a depth interval was in. The legacy
NM_Aquifer ``Stratigraphy`` row it came from is a full interval description:
formation (optional), lithology, lithologic modifier, contributing unit,
source and notes. ``NGWMN_Lithology`` read lithology from
``geologic_formation``, so it could carry one rock type per formation, and
``StratSource`` was always null.

This revision:

* renames the table to ``stratigraphic_interval``, keeping its rows and ids
  (``NGWMN_Lithology.OBJECTID`` is the id), and renames its sequence and
  constraints to match;
* adds ``lithology`` (lexicon term), ``lithologic_modifier``,
  ``contributing_unit``, ``source`` and ``nma_pk_stratigraphy`` (the legacy
  ``Stratigraphy.GlobalID``);
* re-points polymorphic rows (notes, data provenance, status and permission
  history) that name the old table;
* rebuilds ``NGWMN_Lithology`` to read the interval's lithology, falling back
  to the formation's, with a LEFT JOIN so an interval with a lithology but no
  formation is exported, and ``StratSource`` from ``source``.

The data is filled by the data migration
``20261105_0001_backfill_stratigraphic_intervals``.

Revision ID: 7480e4ee69dc
Revises: c89d6680bff6
Create Date: 2026-11-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "7480e4ee69dc"
down_revision: Union[str, Sequence[str], None] = "c89d6680bff6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = "thing_geologic_formation_association"
NEW = "stratigraphic_interval"
# Constraints Postgres named after the table, renamed with it.
CONSTRAINT_SUFFIXES = (
    "pkey",
    "geologic_formation_id_fkey",
    "release_status_fkey",
    "thing_id_fkey",
)
POLYMORPHIC_TABLES = (
    "notes",
    "data_provenance",
    "status_history",
    "permission_history",
)
NEW_COLUMNS = (
    "nma_pk_stratigraphy",
    "source",
    "contributing_unit",
    "lithologic_modifier",
    "lithology",
)

DROP_LITHOLOGY_SQL = 'DROP VIEW IF EXISTS "NGWMN_Lithology"'
COMMENT_SQL = (
    'COMMENT ON VIEW "NGWMN_Lithology" IS '
    "'Lithology intervals in the NGWMN exchange format, sourced from "
    "the Ocotillo stratigraphic intervals.'"
)
OLD_COMMENT_SQL = (
    'COMMENT ON VIEW "NGWMN_Lithology" IS '
    "'Lithology intervals in the NGWMN exchange format, sourced from "
    "the Ocotillo geologic formation associations.'"
)

INTERVAL_VIEW_SQL = """
    CREATE VIEW "NGWMN_Lithology" AS
    SELECT
        si.id AS "OBJECTID",
        t.name AS "PointID",
        si.lithology AS "Lithology",
        si.lithology AS "TERM",
        si.source::character varying AS "StratSource",
        si.top_depth AS "StratTop",
        CASE WHEN si.top_depth IS NOT NULL THEN 'ft bgs' END AS "StratTopUnit",
        si.bottom_depth AS "StratBottom",
        CASE WHEN si.bottom_depth IS NOT NULL THEN 'ft bgs' END
            AS "StratBottomUnit"
    FROM stratigraphic_interval AS si
    JOIN thing AS t ON t.id = si.thing_id
    WHERE si.lithology IS NOT NULL
      AND t.release_status = 'public'
"""

# The definition from w1x2y3z4a5b6, restored on downgrade.
FORMATION_VIEW_SQL = """
    CREATE VIEW "NGWMN_Lithology" AS
    SELECT
        tgfa.id AS "OBJECTID",
        t.name AS "PointID",
        gf.lithology AS "Lithology",
        gf.lithology AS "TERM",
        NULL::character varying AS "StratSource",
        tgfa.top_depth AS "StratTop",
        CASE WHEN tgfa.top_depth IS NOT NULL THEN 'ft bgs' END AS "StratTopUnit",
        tgfa.bottom_depth AS "StratBottom",
        CASE WHEN tgfa.bottom_depth IS NOT NULL THEN 'ft bgs' END
            AS "StratBottomUnit"
    FROM thing_geologic_formation_association AS tgfa
    JOIN thing AS t ON t.id = tgfa.thing_id
    JOIN geologic_formation AS gf ON gf.id = tgfa.geologic_formation_id
    WHERE gf.lithology IS NOT NULL
      AND t.release_status = 'public'
"""

# (column, old comment, new comment) for the columns kept through the rename.
COLUMN_COMMENTS = (
    (
        "thing_id",
        "The foreign key linking this record to the `Thing` table."
        "Deleting a `Thing` will cascade and delete its formation log.",
        "The well this interval belongs to. Deleting the well deletes "
        "its stratigraphic log.",
    ),
    (
        "geologic_formation_id",
        "The foreign key linking this record to the `GeologicFormation` table."
        "This is set to `SET NULL` on delete, as deleting a formation definition "
        "(a rare admin action)should not delete the historical fact that a well "
        "had a pick at this depth.",
        "The geologic formation this interval falls in, if known. "
        "Deleting a formation keeps the interval and clears this link.",
    ),
    (
        "top_depth",
        "The depth (in feet) to the top of the geologic formation, as measured "
        "from ground surface.",
        "Depth (in feet below ground surface) to the top of the interval.",
    ),
    (
        "bottom_depth",
        "The depth (in feet) to the bottom of the geologic formation, as "
        "measured from ground surface.",
        "Depth (in feet below ground surface) to the bottom of the interval.",
    ),
)
COMPLETION_CODE_COMMENT = (
    "The geologic formation in which the well was completed (from "
    "WellData.FormationZone). This indicates the target formation for the "
    "well, not the full stratigraphic column. For detailed depth-interval "
    "stratigraphy, see {}."
)


def _set_comments(table: str, upgrade: bool) -> None:
    for column, old, new in COLUMN_COMMENTS:
        op.alter_column(
            table,
            column,
            comment=new if upgrade else old,
            existing_comment=old if upgrade else new,
        )
    names = ("formation_associations", "stratigraphic_intervals")
    old, new = names if upgrade else names[::-1]
    for thing_table in ("thing", "thing_version"):
        op.alter_column(
            thing_table,
            "formation_completion_code",
            comment=COMPLETION_CODE_COMMENT.format(new),
            existing_comment=COMPLETION_CODE_COMMENT.format(old),
        )


def _rename(src: str, dst: str) -> None:
    op.rename_table(src, dst)
    op.execute(text(f"ALTER SEQUENCE {src}_id_seq RENAME TO {dst}_id_seq"))
    for suffix in CONSTRAINT_SUFFIXES:
        op.execute(
            text(
                f"ALTER TABLE {dst} RENAME CONSTRAINT {src}_{suffix} TO {dst}_{suffix}"
            )
        )
    bind = op.get_bind()
    for table in POLYMORPHIC_TABLES:
        bind.execute(
            text(f"UPDATE {table} SET target_table = :dst WHERE target_table = :src"),
            {"src": src, "dst": dst},
        )


def upgrade() -> None:
    op.execute(text(DROP_LITHOLOGY_SQL))
    _rename(OLD, NEW)
    _set_comments(NEW, upgrade=True)

    op.add_column(
        NEW,
        sa.Column(
            "lithology",
            sa.String(length=100),
            sa.ForeignKey(
                "lexicon_term.term",
                onupdate="CASCADE",
                name=f"{NEW}_lithology_fkey",
            ),
            nullable=True,
            comment="The rock type of this interval, from the lithology lexicon "
            "(legacy Stratigraphy.Lithology via LU_Lithology).",
        ),
    )
    op.add_column(
        NEW,
        sa.Column(
            "lithologic_modifier",
            sa.Text(),
            nullable=True,
            comment="Free-text qualifier on the lithology, e.g. color or grain "
            "size (legacy Stratigraphy.LithologicModifier).",
        ),
    )
    op.add_column(
        NEW,
        sa.Column(
            "contributing_unit",
            sa.Boolean(),
            nullable=True,
            comment="Whether this interval contributes water to the well "
            "(legacy Stratigraphy.ContributingUnit).",
        ),
    )
    op.add_column(
        NEW,
        sa.Column(
            "source",
            sa.Text(),
            nullable=True,
            comment="Where the interval was described, e.g. a driller's log "
            "(legacy Stratigraphy.StratSource). Published as NGWMN StratSource.",
        ),
    )
    op.add_column(
        NEW,
        sa.Column(
            "nma_pk_stratigraphy",
            sa.String(length=36),
            nullable=True,
            comment="Legacy NM_Aquifer Stratigraphy.GlobalID this interval was "
            "migrated from.",
        ),
    )
    op.create_unique_constraint(
        f"{NEW}_nma_pk_stratigraphy_key", NEW, ["nma_pk_stratigraphy"]
    )

    op.execute(text(INTERVAL_VIEW_SQL))
    op.execute(text(COMMENT_SQL))


def downgrade() -> None:
    op.execute(text(DROP_LITHOLOGY_SQL))
    op.drop_constraint(f"{NEW}_nma_pk_stratigraphy_key", NEW, type_="unique")
    for column in NEW_COLUMNS:
        op.drop_column(NEW, column)
    _set_comments(NEW, upgrade=False)
    _rename(NEW, OLD)
    op.execute(text(FORMATION_VIEW_SQL))
    op.execute(text(OLD_COMMENT_SQL))
