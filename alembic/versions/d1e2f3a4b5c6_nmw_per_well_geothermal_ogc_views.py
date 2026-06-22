"""NMW per-well geothermal OGC views

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-22

Four pygeoapi point-layer views that aggregate geothermal data to one
feature per well. All geometry is built from NMW_WellLocations Lat/Long_dd83
(WGS84). All views use integer id (row_number() OVER ()) as the pygeoapi
id_field; pygeoapi's PostgreSQL provider requires an integer PK column.

    ogc_geothermal_wells_bht (VIEW)
        One feature per well with BHT aggregate stats. Links via:
        NMW_GtBhtData → NMW_GtBhtHeaders.BHTGUID → NMW_WellSamples.SamplSetID
        → NMW_WellRecords.RecrdSetID → NMW_WellLocations/Headers.WellDataID

    ogc_geothermal_wells_temperature_profile (MATERIALIZED VIEW)
        One feature per well with temperature-depth JSON series. Materialized
        because the source NMW_GtTempDepths is large (~370k rows) and the
        json_agg is too heavy to recompute per request. NMW_WellLocations is
        deduped via DISTINCT ON before joining because a well can have multiple
        location rows (OBJECTID is the PK, not WellDataID). REFRESH after a
        data reload.

    ogc_geothermal_wells_summary_heat_flow (VIEW)
        One feature per well with summary heat-flow stats and a measurements
        JSON series. Links via NMW_GtSumHeatFlow.RecrdSetID.

    ogc_geothermal_wells_interval_heat_flow (VIEW)
        One feature per well with per-interval heat-flow stats. Links via
        NMW_GtHeatFlow.IntrvlGUID → NMW_WsIntervals → NMW_WellSamples.
"""

from alembic import op
from sqlalchemy import text

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None

_BHT_VIEW = "ogc_geothermal_wells_bht"
_PROFILE_VIEW = "ogc_geothermal_wells_temperature_profile"
_SUM_HF_VIEW = "ogc_geothermal_wells_summary_heat_flow"
_INT_HF_VIEW = "ogc_geothermal_wells_interval_heat_flow"


def upgrade() -> None:
    # ogc_geothermal_wells_bht
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_BHT_VIEW}" AS
        SELECT
            row_number() OVER ()                                 AS id,
            r."WellDataID"::text                                 AS well_data_id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."API"                                            AS api,
            hdr."TotalDepth"                                     AS total_depth,
            count(d.*)                                           AS bht_count,
            max(d."BHT")                                         AS max_bht,
            min(d."BHT")                                         AS min_bht,
            max(d."Depth")                                       AS max_bht_depth,
            max(d."TempUnit")                                    AS temp_unit,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtBhtData" AS d
        JOIN "NMW_GtBhtHeaders" AS h ON h."BHTGUID" = d."BHTGUID"
        JOIN "NMW_WellSamples" AS s ON s."SamplSetID" = h."SamplSetID"
        JOIN "NMW_WellRecords" AS r ON r."RecrdSetID" = s."RecrdsetID"
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        WHERE loc."Lat_dd83" IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        GROUP BY
            r."WellDataID",
            loc."Lat_dd83",
            loc."Long_dd83",
            hdr."CurWellNam",
            hdr."API",
            hdr."TotalDepth"
        """))

    # ogc_geothermal_wells_temperature_profile (materialized)
    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_PROFILE_VIEW}"'))
    op.execute(text(f"""
        CREATE MATERIALIZED VIEW "{_PROFILE_VIEW}" AS
        WITH loc AS (
            SELECT DISTINCT ON ("WellDataID")
                "WellDataID", "Lat_dd83", "Long_dd83"
            FROM "NMW_WellLocations"
            WHERE "Lat_dd83" IS NOT NULL
              AND "Long_dd83" IS NOT NULL
            ORDER BY "WellDataID", "OBJECTID"
        )
        SELECT
            row_number() OVER ()                                 AS id,
            r."WellDataID"::text                                 AS well_data_id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."API"                                            AS api,
            count(td.*)                                          AS reading_count,
            min(td."Depth")                                      AS min_depth,
            max(td."Depth")                                      AS max_depth,
            min(td."Temp")                                       AS min_temp,
            max(td."Temp")                                       AS max_temp,
            max(td."TempUnit")                                   AS temp_unit,
            json_agg(
                json_build_object('depth', td."Depth", 'temp', td."Temp")
                ORDER BY td."Depth"
            )                                                    AS series,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtTempDepths" AS td
        JOIN "NMW_WellSamples" AS s ON s."SamplSetID" = td."SamplSetID"
        JOIN "NMW_WellRecords" AS r ON r."RecrdSetID" = s."RecrdsetID"
        JOIN loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        WHERE td."Depth" IS NOT NULL
          AND td."Temp" IS NOT NULL
        GROUP BY
            r."WellDataID",
            loc."Lat_dd83",
            loc."Long_dd83",
            hdr."CurWellNam",
            hdr."API"
        """))
    op.execute(
        text(f'CREATE UNIQUE INDEX ux_{_PROFILE_VIEW}_id ON "{_PROFILE_VIEW}" (id)')
    )
    op.execute(
        text(
            f'CREATE INDEX ix_{_PROFILE_VIEW}_geom ON "{_PROFILE_VIEW}" USING GIST (geom)'
        )
    )

    # ogc_geothermal_wells_summary_heat_flow
    op.execute(text(f'DROP VIEW IF EXISTS "{_SUM_HF_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_SUM_HF_VIEW}" AS
        SELECT
            row_number() OVER ()                                 AS id,
            r."WellDataID"::text                                 AS well_data_id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."API"                                            AS api,
            count(shf.*)                                         AS heat_flow_count,
            max(shf."HeatFlow")                                  AS max_heat_flow,
            avg(shf."HeatFlow")                                  AS avg_heat_flow,
            max(shf."HtFlowUnit")                                AS heat_flow_unit,
            max(shf."ThermlGrad")                                AS max_thermal_gradient,
            max(shf."GradUnit")                                  AS gradient_unit,
            max(shf."ThermlCond")                                AS max_thermal_conductivity,
            max(shf."TCondUnit")                                 AS conductivity_unit,
            max(shf."Quality")                                   AS quality,
            json_agg(
                json_build_object(
                    'from_depth', shf."FromDepth",
                    'to_depth', shf."ToDepth",
                    'depth_unit', shf."DepthUnit",
                    'heat_flow', shf."HeatFlow",
                    'heat_flow_error', shf."HtFlowErr",
                    'heat_flow_unit', shf."HtFlowUnit",
                    'thermal_gradient', shf."ThermlGrad",
                    'gradient_unit', shf."GradUnit",
                    'thermal_conductivity', shf."ThermlCond",
                    'conductivity_unit', shf."TCondUnit",
                    'quality', shf."Quality"
                )
                ORDER BY shf."FromDepth"
            )                                                    AS measurements,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtSumHeatFlow" AS shf
        JOIN "NMW_WellRecords" AS r ON r."RecrdSetID" = shf."RecrdSetID"
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        WHERE loc."Lat_dd83" IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        GROUP BY
            r."WellDataID",
            loc."Lat_dd83",
            loc."Long_dd83",
            hdr."CurWellNam",
            hdr."API"
        """))

    # ogc_geothermal_wells_interval_heat_flow
    op.execute(text(f'DROP VIEW IF EXISTS "{_INT_HF_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_INT_HF_VIEW}" AS
        SELECT
            row_number() OVER ()                                 AS id,
            r."WellDataID"::text                                 AS well_data_id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."API"                                            AS api,
            count(hf.*)                                          AS interval_count,
            max(hf."Q")                                          AS max_heat_flow,
            avg(hf."Q")                                          AS avg_heat_flow,
            max(hf."Q_unit")                                     AS heat_flow_unit,
            max(hf."Gradient")                                   AS max_gradient,
            max(hf."Kpr")                                        AS max_thermal_conductivity,
            max(hf."Kpr_unit")                                   AS conductivity_unit,
            max(hf."Ka")                                         AS max_diffusivity,
            max(hf."Ka_unit")                                    AS diffusivity_unit,
            json_agg(
                json_build_object(
                    'from_depth', i."From_Depth",
                    'to_depth', i."To_Depth",
                    'heat_flow', hf."Q",
                    'heat_flow_unit', hf."Q_unit",
                    'gradient', hf."Gradient",
                    'thermal_conductivity', hf."Kpr",
                    'conductivity_unit', hf."Kpr_unit",
                    'diffusivity', hf."Ka",
                    'diffusivity_unit', hf."Ka_unit"
                )
                ORDER BY i."From_Depth"
            )                                                    AS measurements,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtHeatFlow" AS hf
        JOIN "NMW_WsIntervals" AS i ON i."IntrvlGUID" = hf."IntrvlGUID"
        JOIN "NMW_WellSamples" AS s ON s."SamplSetID" = i."SamplSetID"
        JOIN "NMW_WellRecords" AS r ON r."RecrdSetID" = s."RecrdsetID"
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        WHERE loc."Lat_dd83" IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        GROUP BY
            r."WellDataID",
            loc."Lat_dd83",
            loc."Long_dd83",
            hdr."CurWellNam",
            hdr."API"
        """))


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_INT_HF_VIEW}"'))
    op.execute(text(f'DROP VIEW IF EXISTS "{_SUM_HF_VIEW}"'))
    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_PROFILE_VIEW}"'))
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_VIEW}"'))
