"""NMW individual-measurement and analytical OGC views

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-22

Four pygeoapi point-layer views exposing individual measurement rows (not
aggregated per well) and analytical summaries from the NMW staging mirror.
All translated from legacy MSSQL queries against NM_Aquifer. Integer OBJECTID
columns are used as the pygeoapi id_field directly.

    ogc_bht_measurements (VIEW)
        One row per BHT measurement with well header and location.
        Translated from the legacy MSSQL BHT query.

    ogc_temp_depth_measurements (VIEW)
        One row per downhole temperature reading with well header, location,
        and elevation. Translated from TempDepth2_SortedWellName query.
        Locations with Exclude=1 are filtered out.

    ogc_heat_flow (VIEW)
        One row per NMW_GtSumHeatFlow record with well header, location,
        elevation, and publication attribution from NMW_Sources. Unit
        conversions (ft→m, HFU→mW/m², TCU→W/m·K) applied inline via
        CASE WHEN. Translated from the legacy MSSQL HeatFlow query.

    ogc_dst (VIEW)
        One row per DST interval with pressure, flow history, and well
        header. The original Access query referenced DST_flwHstryConcat
        (a broken saved query); replaced with a string_agg() CTE over
        NMW_WsDstFlowHistory. DISTINCT used in place of the original
        GROUP BY with no aggregate functions. Translated from the legacy
        MSSQL DST query.
"""

from alembic import op
from sqlalchemy import text

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

_BHT_MEAS_VIEW = "ogc_bht_measurements"
_TEMP_DEPTH_VIEW = "ogc_temp_depth_measurements"
_HEAT_FLOW_VIEW = "ogc_heat_flow"
_DST_VIEW = "ogc_dst"


def upgrade() -> None:
    # ogc_bht_measurements
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_MEAS_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_BHT_MEAS_VIEW}" AS
        SELECT
            d."OBJECTID"                                         AS id,
            hdr."API"                                            AS api,
            hdr."CurWellNam"                                     AS well_name,
            hdr."CurWellNum"                                     AS well_num,
            hdr."CurOperatr"                                     AS operator,
            hdr."WellType"                                       AS well_type,
            hdr."Well_TVD"                                       AS well_tvd,
            hdr."ComplDate"                                      AS completion_date,
            hdr."CurStatus"                                      AS current_status,
            hdr."TotalDepth"                                     AS total_depth,
            hdr."Cuttings"                                       AS cuttings,
            hdr."CoreExists"                                     AS core_exists,
            loc."County"                                         AS county,
            d."Depth"                                            AS bht_depth,
            d."BHT"                                              AS bht,
            d."HrsSnceCir"                                       AS hours_since_circulation,
            d."DateMeasrd"                                       AS date_measured,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtBhtData"    AS d
        JOIN "NMW_GtBhtHeaders"  AS bh  ON bh."BHTGUID"     = d."BHTGUID"
        JOIN "NMW_WellSamples"   AS s   ON s."SamplSetID"   = bh."SamplSetID"
        JOIN "NMW_WellRecords"   AS r   ON r."RecrdSetID"   = s."RecrdsetID"
        JOIN "NMW_WellZDatum"    AS z   ON z."RecrdsetID"   = r."RecrdSetID"
        JOIN "NMW_WellHeaders"   AS hdr ON hdr."WellDataID" = r."WellDataID"
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        WHERE loc."Lat_dd83"  IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        """))

    # ogc_temp_depth_measurements
    op.execute(text(f'DROP VIEW IF EXISTS "{_TEMP_DEPTH_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_TEMP_DEPTH_VIEW}" AS
        SELECT
            td."OBJECTID"                                        AS id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."CurWellNum"                                     AS well_num,
            hdr."API"                                            AS api,
            r."SourceID"                                         AS source_id,
            s."SampleFm"                                         AS sample_fm,
            loc."County"                                         AS county,
            loc."State"                                          AS state,
            loc."Lat_dd27"                                       AS lat_dd27,
            loc."Long_dd27"                                      AS long_dd27,
            loc."Lat_dd83"                                       AS lat_dd83,
            loc."Long_dd83"                                      AS long_dd83,
            loc."LocAccVal"                                      AS loc_acc_val,
            s."EnteredBy"                                        AS entered_by,
            s."EntryDate"                                        AS entry_date,
            td."Depth"                                           AS depth,
            s."SmpDpUnt"                                         AS depth_unit,
            td."Temp"                                            AS temp,
            td."TempUnit"                                        AS temp_unit,
            z."Elev_GL"                                          AS elev_gl,
            z."Elev_unspc"                                       AS elev_unspc,
            z."Elev_KB"                                          AS elev_kb,
            s."SampleDate"                                       AS sample_date,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtTempDepths"  AS td
        JOIN "NMW_WellSamples"   AS s   ON s."SamplSetID"   = td."SamplSetID"
        JOIN "NMW_WellRecords"   AS r   ON r."RecrdSetID"   = s."RecrdsetID"
        JOIN "NMW_WellZDatum"    AS z   ON z."RecrdsetID"   = r."RecrdSetID"
        JOIN "NMW_WellHeaders"   AS hdr ON hdr."WellDataID" = r."WellDataID"
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        WHERE loc."Exclude" = 0
          AND loc."Lat_dd83"  IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        """))

    # ogc_heat_flow
    op.execute(text(f'DROP VIEW IF EXISTS "{_HEAT_FLOW_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_HEAT_FLOW_VIEW}" AS
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
        """))

    # ogc_dst
    op.execute(text(f'DROP VIEW IF EXISTS "{_DST_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_DST_VIEW}" AS
        WITH flow_history AS (
            SELECT
                "DSTInterval",
                string_agg("Operation", '; ' ORDER BY "OBJECTID") AS flow_history
            FROM "NMW_WsDstFlowHistory"
            GROUP BY "DSTInterval"
        )
        SELECT DISTINCT
            i."OBJECTID"                                             AS id,
            hdr."CurWellNam"                                         AS well_name,
            hdr."CurWellNum"                                         AS well_num,
            hdr."API"                                                AS api,
            i."DSTName"                                              AS dst_name,
            dh."DSTOprator"                                          AS dst_operator,
            i."DSTNumber"                                            AS dst_number,
            i."DSTDate"                                              AS dst_date,
            loc."County"                                             AS county,
            loc."State"                                              AS state,
            loc."Lat_dd83"                                           AS lat_dd83,
            loc."Long_dd83"                                          AS long_dd83,
            s."From_Depth"                                           AS from_depth,
            s."To_Depth"                                             AS to_depth,
            i."TargetFm"                                             AS target_fm,
            i."PackrFrom"                                            AS packer_from,
            i."PackerTo"                                             AS packer_to,
            i."SrfChokeSz"                                           AS srf_choke_sz,
            i."BotChokeSz"                                           AS bot_choke_sz,
            s."SmpDpUnt"                                             AS depth_unit,
            z."Elev_GL"                                              AS elev_gl,
            z."Elev_unspc"                                           AS elev_unspc,
            p."PrsGageDpt"                                           AS prs_gage_dpt,
            i."PipeDia"                                              AS pipe_dia,
            i."PipeLength"                                           AS pipe_length,
            fh.flow_history                                          AS flow_history,
            p."PrsInShtIn"                                           AS init_flow,
            p."FlwPrsInMin"                                          AS flw_prs_in_min,
            p."PrsFnShtIn"                                           AS fin_flow,
            p."FlwPrsFinMin"                                         AS flw_prs_fin_min,
            p."PrsInitClsdIn"                                        AS prs_init_clsd_in,
            p."InShtInMin"                                           AS in_sht_in_min,
            p."EquilPress"                                           AS fin_shut_in,
            p."FnShtInMin"                                           AS fn_sht_in_min,
            p."HydrostPrsIn"                                         AS hydrost_prs_in,
            p."HydStPrsFl"                                           AS hyd_st_prs_fl,
            dh."PressUnits"                                          AS press_units,
            p."BlankedOff"                                           AS blanked_off,
            p."FmTemp"                                               AS fm_temp,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                        AS geom
        FROM "NMW_WsDstIntervals"  AS i
        JOIN "NMW_WsDstHeaders"    AS dh  ON dh."DSTGUID"     = i."DSTGUID"
        JOIN "NMW_WellSamples"     AS s   ON s."SamplSetID"   = dh."SamplSetID"
        JOIN "NMW_WellRecords"     AS r   ON r."RecrdSetID"   = s."RecrdsetID"
        JOIN "NMW_WellHeaders"     AS hdr ON hdr."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellZDatum" AS z   ON z."RecrdsetID"   = r."RecrdSetID"
        LEFT JOIN "NMW_WsDstPressure" AS p ON p."DSTInterval" = i."DSTInterval"
        LEFT JOIN flow_history     AS fh  ON fh."DSTInterval" = i."DSTInterval"
        WHERE loc."Lat_dd83"  IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
        """))


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_DST_VIEW}"'))
    op.execute(text(f'DROP VIEW IF EXISTS "{_HEAT_FLOW_VIEW}"'))
    op.execute(text(f'DROP VIEW IF EXISTS "{_TEMP_DEPTH_VIEW}"'))
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_MEAS_VIEW}"'))
