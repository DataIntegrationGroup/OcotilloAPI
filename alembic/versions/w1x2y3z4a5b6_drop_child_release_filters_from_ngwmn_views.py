"""drop child-row release filters from NGWMN construction/lithology views

The release_status filters added to NGWMN_WellConstruction and
NGWMN_Lithology for well_screen, well_casing_material, and
thing_geologic_formation_association rows emptied those exports in
practice: the transfers never set release_status on those child tables,
so every row defaults to 'draft' (verified 3005/3005 well_screen,
63/63 well_casing_material, 993/993 associations on transferred data).

Construction and lithology rows are attributes of the well, and the
well's own release_status (genuinely managed: public/private) remains
the gate. The thing-level filters are kept; only the child-row
predicates are removed. NGWMN_WaterLevels is unchanged, since the whole
field-data chain it filters on does carry real release values.

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-06-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, Sequence[str], None] = "v0w1x2y3z4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "thing",
    "well_screen",
    "well_casing_material",
    "thing_geologic_formation_association",
    "geologic_formation",
}

DROP_WELLCONSTRUCTION_SQL = 'DROP VIEW IF EXISTS "NGWMN_WellConstruction"'
DROP_LITHOLOGY_SQL = 'DROP VIEW IF EXISTS "NGWMN_Lithology"'


def _create_wellconstruction_view(with_child_filters: bool) -> str:
    screen_filter = " AND ws.release_status = 'public'" if with_child_filters else ""
    material_filter = " AND wcm.release_status = 'public'" if with_child_filters else ""
    return f"""
        CREATE VIEW "NGWMN_WellConstruction" AS
        SELECT
            t.name AS "PointID",
            CASE WHEN t.well_casing_depth IS NOT NULL THEN 0::double precision END AS "CasingTop",
            t.well_casing_depth AS "CasingBottom",
            CASE WHEN t.well_casing_depth IS NOT NULL THEN 'ft bgs' END AS "CasingDepthUnits",
            ws.screen_depth_top AS "ScreenTop",
            ws.screen_depth_bottom AS "ScreenBottom",
            CASE WHEN ws.screen_depth_bottom IS NOT NULL THEN 'ft bgs' END AS "ScreenBottomUnit",
            ws.screen_description AS "ScreenDescription",
            cm.materials AS "CasingDescription"
        FROM thing AS t
        LEFT JOIN well_screen AS ws
            ON ws.thing_id = t.id{screen_filter}
        LEFT JOIN LATERAL (
            SELECT string_agg(wcm.material, ', ' ORDER BY wcm.material) AS materials
            FROM well_casing_material AS wcm
            WHERE wcm.thing_id = t.id{material_filter}
        ) AS cm ON TRUE
        WHERE t.thing_type = 'water well'
          AND t.release_status = 'public'
    """


def _create_lithology_view(with_child_filters: bool) -> str:
    association_filter = (
        "          AND tgfa.release_status = 'public'\n" if with_child_filters else ""
    )
    return f"""
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
{association_filter}          AND t.release_status = 'public'
    """


def _recreate_views(with_child_filters: bool) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot recreate NGWMN views. Missing required tables: "
            f"{', '.join(sorted(missing))}"
        )

    op.execute(text(DROP_WELLCONSTRUCTION_SQL))
    op.execute(text(_create_wellconstruction_view(with_child_filters)))
    op.execute(
        text(
            'COMMENT ON VIEW "NGWMN_WellConstruction" IS '
            "'Well casing and screen intervals in the NGWMN exchange format, "
            "sourced from the Ocotillo thing/well_screen model.'"
        )
    )

    op.execute(text(DROP_LITHOLOGY_SQL))
    op.execute(text(_create_lithology_view(with_child_filters)))
    op.execute(
        text(
            'COMMENT ON VIEW "NGWMN_Lithology" IS '
            "'Lithology intervals in the NGWMN exchange format, sourced from "
            "the Ocotillo geologic formation associations.'"
        )
    )


def upgrade() -> None:
    _recreate_views(with_child_filters=False)


def downgrade() -> None:
    _recreate_views(with_child_filters=True)
