"""add NGWMN views sourced from the new Ocotillo data model

Replaces the legacy NMA_view_NGWMN_* copy tables as the source for NGWMN
exports. These views reproduce the original AMPAPI (SQL Server) view
definitions but read from the new Ocotillo tables:

- NGWMN_WaterLevels:      observation/sample/field_activity/field_event/thing
- NGWMN_WellConstruction: thing/well_screen/well_casing_material
- NGWMN_Lithology:        thing_geologic_formation_association/geologic_formation

Revision ID: u8v9w0x1y2z3
Revises: t6u7v8w9x0y1
Create Date: 2026-06-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "u8v9w0x1y2z3"
down_revision: Union[str, Sequence[str], None] = "t6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "thing",
    "well_screen",
    "well_casing_material",
    "observation",
    "sample",
    "field_activity",
    "field_event",
    "parameter",
    "thing_geologic_formation_association",
    "geologic_formation",
}

DROP_WATERLEVELS_SQL = 'DROP VIEW IF EXISTS "NGWMN_WaterLevels"'
DROP_WELLCONSTRUCTION_SQL = 'DROP VIEW IF EXISTS "NGWMN_WellConstruction"'
DROP_LITHOLOGY_SQL = 'DROP VIEW IF EXISTS "NGWMN_Lithology"'


def _create_waterlevels_view() -> str:
    # Mirrors dbo.view_NGWMN_WaterLevels:
    #   SELECT PointID, DateMeasured, DepthToWaterBGS, 'ft bgs', CASE
    #   MeasurementMethod..., CASE DataQuality..., PublicRelease
    #   FROM WaterLevels WHERE PublicRelease = 1
    #
    # The transfer stored observation.value as depth-to-water below the
    # measuring point (DepthToWater) and measuring_point_height separately,
    # so DepthToWaterBGS = value - measuring_point_height (0 when no MP
    # height was recorded).
    #
    # observation_datetime was converted to UTC during transfer; rows whose
    # legacy timestamp had no time component were stored at 00:00 UTC, so
    # only rows with a real time component are shifted back to local time
    # before taking the date.
    #
    # MeasurementMethod/WLAccuracy reproduce the legacy CASE expressions,
    # keyed on the lexicon meanings the transfer wrote (LU_MeasurementMethod
    # and LU_DataQuality), including the legacy quirk mapping code O
    # ("Observed...") to 'Acoustic Sounder'.
    return """
        CREATE VIEW "NGWMN_WaterLevels" AS
        SELECT
            t.name AS "PointID",
            CASE
                WHEN (o.observation_datetime AT TIME ZONE 'UTC')::time = '00:00:00'
                THEN (o.observation_datetime AT TIME ZONE 'UTC')::date
                ELSE (o.observation_datetime AT TIME ZONE 'America/Denver')::date
            END AS "DateMeasured",
            o.value - COALESCE(o.measuring_point_height, 0) AS "DepthToWaterBGS",
            'ft bgs' AS "WLUnits",
            CASE s.sample_method
                WHEN 'Steel-tape measurement' THEN 'Steel tape'
                WHEN 'Electric tape measurement (E-probe)' THEN 'Electric tape'
                WHEN 'Observed (required for F, N, and W water level status)' THEN 'Acoustic Sounder'
                WHEN 'Estimated' THEN 'Estimated'
                WHEN 'Reported, method not known' THEN 'Reported'
                WHEN 'Pressure-gage measurement' THEN 'Pressure gauge'
                WHEN 'Unknown (for legacy data only; not for new data entry)' THEN 'Unknown; from legacy data'
                ELSE NULL
            END AS "MeasurementMethod",
            CASE o.nma_data_quality
                WHEN 'Water level accurate to within two hundreths of a foot' THEN '0.02 ft'
                WHEN 'Water level accurate to within one foot' THEN '1.0 ft'
                WHEN 'Water level accuracy not to nearest foot or water level not repeatable' THEN 'Unknown'
                ELSE NULL
            END AS "WLAccuracy",
            TRUE AS "PublicRelease"
        FROM observation AS o
        JOIN sample AS s ON s.id = o.sample_id
        JOIN field_activity AS fa ON fa.id = s.field_activity_id
        JOIN field_event AS fe ON fe.id = fa.field_event_id
        JOIN thing AS t ON t.id = fe.thing_id
        JOIN parameter AS p ON p.id = o.parameter_id
        WHERE p.parameter_name = 'groundwater level'
          AND o.release_status = 'public'
    """


def _create_wellconstruction_view() -> str:
    # Mirrors dbo.view_NGWMN_WellConstruction:
    #   WellData LEFT JOIN WellScreens ON WellData.WellID = WellScreens.WellID
    # CasingTop is 0 whenever a casing depth exists (casing assumed to start
    # at ground surface). The legacy free-text CasingDescription was reduced
    # to controlled material terms during transfer, so it is rebuilt here as
    # a comma-separated list of well_casing_material terms.
    return """
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
        LEFT JOIN well_screen AS ws ON ws.thing_id = t.id
        LEFT JOIN LATERAL (
            SELECT string_agg(wcm.material, ', ' ORDER BY wcm.material) AS materials
            FROM well_casing_material AS wcm
            WHERE wcm.thing_id = t.id
        ) AS cm ON TRUE
        WHERE t.thing_type = 'water well'
    """


def _create_lithology_view() -> str:
    # Mirrors dbo.view_NGWMN_Lithology:
    #   Stratigraphy INNER JOIN LU_Lithology ON Lithology = ABBREVIATION
    # The new model keeps the resolved lithology term on geologic_formation
    # (the abbreviation code was not migrated), so the term backs both the
    # Lithology and TERM columns. The inner join is reproduced by requiring
    # a non-null lithology. StratSource was not migrated and is NULL.
    return """
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
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot create NGWMN views. Missing required tables: "
            f"{', '.join(sorted(missing))}"
        )

    op.execute(text(DROP_WATERLEVELS_SQL))
    op.execute(text(_create_waterlevels_view()))
    op.execute(
        text(
            'COMMENT ON VIEW "NGWMN_WaterLevels" IS '
            "'Public manual groundwater level measurements in the NGWMN "
            "exchange format, sourced from the Ocotillo observation model.'"
        )
    )

    op.execute(text(DROP_WELLCONSTRUCTION_SQL))
    op.execute(text(_create_wellconstruction_view()))
    op.execute(
        text(
            'COMMENT ON VIEW "NGWMN_WellConstruction" IS '
            "'Well casing and screen intervals in the NGWMN exchange format, "
            "sourced from the Ocotillo thing/well_screen model.'"
        )
    )

    op.execute(text(DROP_LITHOLOGY_SQL))
    op.execute(text(_create_lithology_view()))
    op.execute(
        text(
            'COMMENT ON VIEW "NGWMN_Lithology" IS '
            "'Lithology intervals in the NGWMN exchange format, sourced from "
            "the Ocotillo geologic formation associations.'"
        )
    )


def downgrade() -> None:
    op.execute(text(DROP_LITHOLOGY_SQL))
    op.execute(text(DROP_WELLCONSTRUCTION_SQL))
    op.execute(text(DROP_WATERLEVELS_SQL))
