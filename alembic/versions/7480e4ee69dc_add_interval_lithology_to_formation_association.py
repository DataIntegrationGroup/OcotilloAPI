"""store lithology per stratigraphy interval (BDMS-1554)

``NGWMN_Lithology`` read lithology from ``geologic_formation.lithology``, so it
could carry one value per formation. The legacy ``view_NGWMN_Lithology`` joined
``Stratigraphy`` to ``LU_Lithology`` on each row, so every interval had its own
lithology, and intervals with a lithology code but no ``UnitIdentifier`` were
in it too.

This revision:

* adds a nullable ``lithology`` lexicon-term column to
  ``thing_geologic_formation_association``, and
* rebuilds ``NGWMN_Lithology`` to read the interval's lithology, falling back
  to the formation's when the interval has none. The formation join becomes a
  LEFT JOIN, so an interval with a lithology but no formation is exported.

The data is filled by the data migration
``20261105_0001_backfill_stratigraphy_interval_lithology``.

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

TABLE = "thing_geologic_formation_association"
DROP_LITHOLOGY_SQL = 'DROP VIEW IF EXISTS "NGWMN_Lithology"'
COMMENT_SQL = (
    'COMMENT ON VIEW "NGWMN_Lithology" IS '
    "'Lithology intervals in the NGWMN exchange format, sourced from "
    "the Ocotillo geologic formation associations.'"
)

INTERVAL_LITHOLOGY_VIEW_SQL = """
    CREATE VIEW "NGWMN_Lithology" AS
    SELECT
        tgfa.id AS "OBJECTID",
        t.name AS "PointID",
        COALESCE(tgfa.lithology, gf.lithology) AS "Lithology",
        COALESCE(tgfa.lithology, gf.lithology) AS "TERM",
        NULL::character varying AS "StratSource",
        tgfa.top_depth AS "StratTop",
        CASE WHEN tgfa.top_depth IS NOT NULL THEN 'ft bgs' END AS "StratTopUnit",
        tgfa.bottom_depth AS "StratBottom",
        CASE WHEN tgfa.bottom_depth IS NOT NULL THEN 'ft bgs' END AS "StratBottomUnit"
    FROM thing_geologic_formation_association AS tgfa
    JOIN thing AS t ON t.id = tgfa.thing_id
    LEFT JOIN geologic_formation AS gf ON gf.id = tgfa.geologic_formation_id
    WHERE COALESCE(tgfa.lithology, gf.lithology) IS NOT NULL
      AND t.release_status = 'public'
"""

# The definition from w1x2y3z4a5b6, restored on downgrade.
FORMATION_LITHOLOGY_VIEW_SQL = """
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
        CASE WHEN tgfa.bottom_depth IS NOT NULL THEN 'ft bgs' END AS "StratBottomUnit"
    FROM thing_geologic_formation_association AS tgfa
    JOIN thing AS t ON t.id = tgfa.thing_id
    JOIN geologic_formation AS gf ON gf.id = tgfa.geologic_formation_id
    WHERE gf.lithology IS NOT NULL
      AND t.release_status = 'public'
"""


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "lithology",
            sa.String(length=100),
            sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
            nullable=True,
            comment="The lithology of this interval, from the lithology lexicon. "
            "Falls back to the formation's lithology in NGWMN_Lithology when null.",
        ),
    )
    op.execute(text(DROP_LITHOLOGY_SQL))
    op.execute(text(INTERVAL_LITHOLOGY_VIEW_SQL))
    op.execute(text(COMMENT_SQL))


def downgrade() -> None:
    op.execute(text(DROP_LITHOLOGY_SQL))
    op.execute(text(FORMATION_LITHOLOGY_VIEW_SQL))
    op.execute(text(COMMENT_SQL))
    op.drop_column(TABLE, "lithology")
