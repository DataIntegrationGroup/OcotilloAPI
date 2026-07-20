"""dedupe NMW_WellLocations in the measurement OGC views

Revision ID: a5b6c7d8e9f0
Revises: y3z4a5b6c7d8
Create Date: 2026-07-20

``NMW_WellLocations`` is keyed on ``OBJECTID``, not ``WellDataID``, so a single
well can carry several location rows. The per-well geothermal views
(``d1e2f3a4b5c6``) already account for this with a ``DISTINCT ON ("WellDataID")``
CTE, but the four measurement views created in ``e2f3a4b5c6d7`` join
``NMW_WellLocations`` directly. Where a well has more than one location row,
that join fans a single measurement into N rows sharing the same ``OBJECTID``
-- which pygeoapi surfaces as duplicate feature ids.

This revision recreates all four views with the same deduped-location CTE the
geothermal views use. ``e2f3a4b5c6d7`` is left untouched: it is already applied
in production, so the fix has to arrive as a new revision.

The tie-break (``ORDER BY "WellDataID", "OBJECTID"``) matches ``d1e2f3a4b5c6``
so both view families resolve a multi-location well to the same row.

Only the location join changes. Column lists, unit conversions, join order, and
the remaining filters are carried over from ``e2f3a4b5c6d7`` verbatim. Note
that the ``Exclude = 0`` predicate moves *inside* the CTE for the two views
that use it: filtering after the dedup would let ``DISTINCT ON`` settle on an
excluded row and drop the well entirely, instead of falling through to the next
eligible location.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "y3z4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BHT_MEAS_VIEW = "ogc_bht_measurements"
_TEMP_DEPTH_VIEW = "ogc_temp_depth_measurements"
_HEAT_FLOW_VIEW = "ogc_heat_flow"
_DST_VIEW = "ogc_dst"

# One location row per well. Two variants because ogc_temp_depth_measurements
# and ogc_heat_flow additionally require Exclude = 0, which has to be applied
# before the dedup (see module docstring).
_LOC_CTE = """
            SELECT DISTINCT ON ("WellDataID")
                "WellDataID", "County", "State",
                "Lat_dd27", "Long_dd27", "Lat_dd83", "Long_dd83", "LocAccVal"
            FROM "NMW_WellLocations"
            WHERE "Lat_dd83"  IS NOT NULL
              AND "Long_dd83" IS NOT NULL
            ORDER BY "WellDataID", "OBJECTID"
"""

_LOC_CTE_NOT_EXCLUDED = """
            SELECT DISTINCT ON ("WellDataID")
                "WellDataID", "County", "State",
                "Lat_dd27", "Long_dd27", "Lat_dd83", "Long_dd83", "LocAccVal"
            FROM "NMW_WellLocations"
            WHERE "Exclude" = 0
              AND "Lat_dd83"  IS NOT NULL
              AND "Long_dd83" IS NOT NULL
            ORDER BY "WellDataID", "OBJECTID"
"""

_COORDS_PRESENT = """
        WHERE loc."Lat_dd83"  IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
"""

_NOT_EXCLUDED_AND_COORDS_PRESENT = """
        WHERE loc."Exclude" = 0
          AND loc."Lat_dd83"  IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
"""


def _loc_parts(deduped: bool, exclude_filter: bool, left_join: bool = False):
    """Location CTE / join / trailing-filter fragments for one view.

    ``deduped=True`` is this revision's behavior; ``deduped=False`` reproduces
    the direct join from ``e2f3a4b5c6d7`` so downgrade is faithful.
    """
    if deduped:
        cte = _LOC_CTE_NOT_EXCLUDED if exclude_filter else _LOC_CTE
        # The dedup CTE already applies both predicates internally, so no
        # trailing WHERE is needed. A LEFT JOIN would be pointless here: the
        # original's WHERE on loc columns made it an inner join in practice.
        return f"WITH loc AS ({cte})", 'JOIN loc ON loc."WellDataID"', ""

    join_kw = "LEFT JOIN" if left_join else "JOIN"
    where = _NOT_EXCLUDED_AND_COORDS_PRESENT if exclude_filter else _COORDS_PRESENT
    return "", f'{join_kw} "NMW_WellLocations" AS loc ON loc."WellDataID"', where


def _recreate_views(deduped: bool) -> None:
    # ogc_bht_measurements
    cte, loc_join, loc_where = _loc_parts(deduped, exclude_filter=False)
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_MEAS_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_BHT_MEAS_VIEW}" AS
        {cte}
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
        {loc_join} = r."WellDataID"
        {loc_where}
        """))

    # ogc_temp_depth_measurements
    cte, loc_join, loc_where = _loc_parts(deduped, exclude_filter=True)
    op.execute(text(f'DROP VIEW IF EXISTS "{_TEMP_DEPTH_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_TEMP_DEPTH_VIEW}" AS
        {cte}
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
        {loc_join} = r."WellDataID"
        {loc_where}
        """))

    # ogc_heat_flow
    cte, loc_join, loc_where = _loc_parts(deduped, exclude_filter=True)
    op.execute(text(f'DROP VIEW IF EXISTS "{_HEAT_FLOW_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_HEAT_FLOW_VIEW}" AS
        {cte}
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
        {loc_join} = r."WellDataID"
        LEFT JOIN "NMW_WellZDatum" AS z  ON z."RecrdsetID"   = r."RecrdSetID"
        JOIN "NMW_Sources"        AS src ON src."SourceID"   = r."SourceID"
        {loc_where}
        """))

    # ogc_dst -- the only view with a second CTE, so the location CTE has to be
    # spliced into the same WITH clause rather than prefixed.
    cte, loc_join, loc_where = _loc_parts(deduped, exclude_filter=False, left_join=True)
    with_clause = (
        f"WITH loc AS ({_LOC_CTE}), flow_history AS ("
        if deduped
        else "WITH flow_history AS ("
    )
    op.execute(text(f'DROP VIEW IF EXISTS "{_DST_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_DST_VIEW}" AS
        {with_clause}
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
        {loc_join} = r."WellDataID"
        LEFT JOIN "NMW_WellZDatum" AS z   ON z."RecrdsetID"   = r."RecrdSetID"
        LEFT JOIN "NMW_WsDstPressure" AS p ON p."DSTInterval" = i."DSTInterval"
        LEFT JOIN flow_history     AS fh  ON fh."DSTInterval" = i."DSTInterval"
        {loc_where}
        """))


def upgrade() -> None:
    _recreate_views(deduped=True)


def downgrade() -> None:
    _recreate_views(deduped=False)
