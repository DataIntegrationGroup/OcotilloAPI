"""add ogc_dst view

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-06-18

Drill Stem Test records with well header, location, interval, and pressure
data. Translated from the legacy MSSQL DST query against NM_Aquifer.

The original Access query referenced DST_flwHstryConcat, a broken saved
query that never executed. We replace it with a string_agg() CTE over
NMW_WsDstFlowHistory that concatenates operation descriptions per interval.

The original GROUP BY with no aggregate functions is equivalent to
SELECT DISTINCT, implemented that way here.
"""

from alembic import op
from sqlalchemy import text

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None

_VIEW = "ogc_dst"


def upgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
    op.execute(
        text(
            f"""
        CREATE VIEW "{_VIEW}" AS
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
        """
        )
    )


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
