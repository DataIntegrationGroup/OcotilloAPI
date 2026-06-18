"""add ogc_heat_flow view

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-06-18

Summary heat-flow records with well header, location, elevation, and
publication attribution. Translated from the legacy MSSQL HeatFlow query
against NM_Aquifer. IIf() unit-conversion expressions translated to
CASE WHEN. County WHERE filter removed — filter via API instead.
One row per GT_SumHeatFlow record.
"""

from alembic import op
from sqlalchemy import text

revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None

_VIEW = "ogc_heat_flow"


def upgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
    op.execute(
        text(
            f"""
        CREATE VIEW "{_VIEW}" AS
        SELECT
            shf."OBJECTID"                                           AS id,
            hdr."CurWellNam"                                         AS well_name,
            hdr."CurWellNum"                                         AS well_num,
            hdr."API"                                                AS api,
            loc."County"                                             AS county,
            loc."State"                                              AS state,
            loc."Lat_dd27"                                           AS lat_dd27,
            loc."Long_dd27"                                          AS long_dd27,
            loc."Lat_dd83"                                           AS lat_dd83,
            loc."Long_dd83"                                          AS long_dd83,
            r."SourceID"                                             AS source_id,
            z."Elev_GL"                                              AS elev_gl,
            z."Elev_KB"                                              AS elev_kb,
            z."Elev_unspc"                                           AS elev_unspc,
            CASE WHEN z."DepthUnits" = 'ft'
                 THEN 0.3048 * z."Elev_unspc"
                 ELSE z."Elev_unspc"
            END                                                      AS elevation_m,
            z."DepthUnits"                                           AS depth_units,
            hdr."TotalDepth"                                         AS total_depth,
            CASE WHEN z."DepthUnits" = 'ft'
                 THEN 0.3048 * hdr."TotalDepth"
                 ELSE hdr."TotalDepth"
            END                                                      AS total_depth_m,
            shf."FromDepth"                                          AS from_depth,
            shf."ToDepth"                                            AS to_depth,
            shf."ThermlCond"                                         AS therml_cond,
            shf."TCondRange"                                         AS tcond_range,
            shf."TCondError"                                         AS tcond_error,
            shf."TCondUnit"                                          AS tcond_unit,
            CASE WHEN shf."TCondUnit" = 'TCU'
                 THEN 0.4184 * shf."ThermlCond"
                 ELSE shf."ThermlCond"
            END                                                      AS tc_si,
            shf."SampleType"                                         AS sample_type,
            shf."NumSamples"                                         AS num_samples,
            shf."ThermlGrad"                                         AS therml_grad,
            shf."TGradRange"                                         AS tgrad_range,
            shf."TGError"                                            AS tg_error,
            shf."GradUnit"                                           AS grad_unit,
            shf."HeatFlow"                                           AS heat_flow,
            shf."HtFlowUnit"                                         AS ht_flow_unit,
            CASE WHEN shf."HtFlowUnit" = 'HFU'
                 THEN 41.84 * shf."HeatFlow"
                 ELSE shf."HeatFlow"
            END                                                      AS heat_flow_si,
            shf."Quality"                                            AS quality,
            src."FirstAuth"                                          AS first_auth,
            src."PubYear"                                            AS pub_year,
            src."Title"                                              AS title,
            src."Journal"                                            AS journal,
            src."Volume"                                             AS volume,
            src."PageNo"                                             AS page_no,
            shf."HtFlowEst"                                          AS ht_flow_est,
            r."EntryDate"                                            AS entry_date,
            CASE WHEN shf."HtFlowUnit" = 'HFU'
                 THEN 41.84 * shf."HtFlowEst"
                 ELSE shf."HtFlowEst"
            END                                                      AS ht_flow_est_si,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                        AS geom
        FROM "NMW_GtSumHeatFlow"  AS shf
        JOIN "NMW_WellRecords"    AS r   ON r."RecrdSetID"   = shf."RecrdSetID"
        JOIN "NMW_WellHeaders"    AS hdr ON hdr."WellDataID" = r."WellDataID"
        JOIN "NMW_WellLocations"  AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellZDatum" AS z  ON z."RecrdsetID"   = r."RecrdSetID"
        JOIN "NMW_Sources"        AS src ON src."SourceID"   = r."SourceID"
        WHERE loc."Exclude" = 0
          AND loc."Lat_dd83"  IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        """
        )
    )


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
