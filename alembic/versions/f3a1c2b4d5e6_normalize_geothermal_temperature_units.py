"""Normalize geothermal OGC view temperatures to Celsius

Revision ID: f3a1c2b4d5e6
Revises: 2d3c3a268652
Create Date: 2026-08-06

The geothermal per-well views created in d1e2f3a4b5c6 passed legacy
temperatures through unconverted and labelled them with ``max("TempUnit")``.
That is wrong two ways:

    1. ``max()`` over a mixed-unit well picks a unit lexically ('F' > 'C'),
       so a well holding both C and F readings was labelled 'F' while the
       values stayed mixed.
    2. ``min("Temp")`` / ``max("Temp")`` aggregate across those mixed units,
       so 100 F sorts above 40 C and the extremes are meaningless.

This revision adds two helper functions and rebuilds the two temperature
views so every temperature is also published in Celsius:

    nmw_temp_unit_code(text) -> text
        Canonicalizes a legacy unit string to 'C', 'F', 'K', or NULL when
        unrecognized. NMW_GtTempDepths."TempUnit" is String(1) while
        NMW_GtBhtData."TempUnit" is String(5), so both single-letter codes
        and spelled-out forms are accepted.

    nmw_temp_to_c(double precision, text) -> double precision
        Converts a value to Celsius using that code. Returns NULL when the
        unit is unrecognized rather than assuming a default, so unconvertible
        readings are visible instead of silently wrong.

Changes to ogc_geothermal_wells_bht and
ogc_geothermal_wells_temperature_profile:

    * new ``*_c`` columns (min_bht_c/max_bht_c, min_temp_c/max_temp_c)
      aggregated over normalized values -- these are the ones to chart.
    * ``temp_unit`` is now the constant 'C', describing the ``*_c`` columns.
    * new ``temp_unit_source`` lists the distinct source units actually
      present for the well ('C', 'F', 'C,F', 'UNKNOWN', ...), and
      ``temp_unit_mixed`` flags wells that mix units.
    * new ``unconvertible_count`` counts readings whose unit was not
      recognized (present in the raw columns, NULL in the ``*_c`` columns).
    * pre-existing raw columns (min_bht/max_bht, min_temp/max_temp, and the
      profile ``series`` 'temp' key) are kept unchanged for compatibility.
      They remain mixed-unit; consumers should move to the ``*_c`` columns.
    * profile ``series`` objects gain 'temp_c' and 'temp_unit_source'.

Heat-flow units (HtFlowUnit, GradUnit, TCondUnit, Q_unit, Kpr_unit, Ka_unit)
and depth units are NOT normalized here -- the summary and interval heat-flow
views are untouched.

Rebuilding ogc_geothermal_wells_temperature_profile drops and recreates the
materialized view, which repopulates it WITH DATA. Expect the usual matview
build cost against the ~370k-row NMW_GtTempDepths source.
"""

from alembic import op
from sqlalchemy import text

revision = "f3a1c2b4d5e6"
down_revision = "2d3c3a268652"
branch_labels = None
depends_on = None

_BHT_VIEW = "ogc_geothermal_wells_bht"
_PROFILE_VIEW = "ogc_geothermal_wells_temperature_profile"

_LOC_CTE = """
        WITH loc AS (
            SELECT DISTINCT ON ("WellDataID")
                "WellDataID", "Lat_dd83", "Long_dd83"
            FROM "NMW_WellLocations"
            WHERE "Lat_dd83" IS NOT NULL
              AND "Long_dd83" IS NOT NULL
            ORDER BY "WellDataID", "OBJECTID"
        )
"""


def upgrade() -> None:
    op.execute(text("""
        CREATE OR REPLACE FUNCTION public.nmw_temp_unit_code(unit text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE upper(regexp_replace(coalesce(unit, ''), '[^A-Za-z]', '', 'g'))
                WHEN 'C'          THEN 'C'
                WHEN 'DEGC'       THEN 'C'
                WHEN 'DEGREESC'   THEN 'C'
                WHEN 'CELSIUS'    THEN 'C'
                WHEN 'CENTIGRADE' THEN 'C'
                WHEN 'F'          THEN 'F'
                WHEN 'DEGF'       THEN 'F'
                WHEN 'DEGREESF'   THEN 'F'
                WHEN 'FAHRENHEIT' THEN 'F'
                WHEN 'K'          THEN 'K'
                WHEN 'DEGK'       THEN 'K'
                WHEN 'KELVIN'     THEN 'K'
                ELSE NULL
            END
        $$
        """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION public.nmw_temp_to_c(val double precision, unit text)
        RETURNS double precision
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE public.nmw_temp_unit_code(unit)
                WHEN 'C' THEN val
                WHEN 'F' THEN (val - 32.0) * 5.0 / 9.0
                WHEN 'K' THEN val - 273.15
                ELSE NULL
            END
        $$
        """))

    # ogc_geothermal_wells_bht
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_BHT_VIEW}" AS
        {_LOC_CTE}
        SELECT
            row_number() OVER ()                                 AS id,
            r."WellDataID"::text                                 AS well_data_id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."API"                                            AS api,
            hdr."TotalDepth"                                     AS total_depth,
            count(d.*)                                           AS bht_count,
            max(d."BHT")                                         AS max_bht,
            min(d."BHT")                                         AS min_bht,
            max(public.nmw_temp_to_c(d."BHT", d."TempUnit"))            AS max_bht_c,
            min(public.nmw_temp_to_c(d."BHT", d."TempUnit"))            AS min_bht_c,
            max(d."Depth")                                       AS max_bht_depth,
            'C'::text                                            AS temp_unit,
            string_agg(
                DISTINCT coalesce(public.nmw_temp_unit_code(d."TempUnit"), 'UNKNOWN'),
                ','
                ORDER BY coalesce(public.nmw_temp_unit_code(d."TempUnit"), 'UNKNOWN')
            )                                                    AS temp_unit_source,
            count(DISTINCT coalesce(public.nmw_temp_unit_code(d."TempUnit"), 'UNKNOWN')) > 1
                                                                 AS temp_unit_mixed,
            count(*) FILTER (
                WHERE d."BHT" IS NOT NULL
                  AND public.nmw_temp_to_c(d."BHT", d."TempUnit") IS NULL
            )                                                    AS unconvertible_count,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtBhtData" AS d
        JOIN "NMW_GtBhtHeaders" AS h ON h."BHTGUID" = d."BHTGUID"
        JOIN "NMW_WellSamples" AS s ON s."SamplSetID" = h."SamplSetID"
        JOIN "NMW_WellRecords" AS r ON r."RecrdSetID" = s."RecrdsetID"
        JOIN loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
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
        {_LOC_CTE}
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
            min(public.nmw_temp_to_c(td."Temp", td."TempUnit"))         AS min_temp_c,
            max(public.nmw_temp_to_c(td."Temp", td."TempUnit"))         AS max_temp_c,
            'C'::text                                            AS temp_unit,
            string_agg(
                DISTINCT coalesce(public.nmw_temp_unit_code(td."TempUnit"), 'UNKNOWN'),
                ','
                ORDER BY coalesce(public.nmw_temp_unit_code(td."TempUnit"), 'UNKNOWN')
            )                                                    AS temp_unit_source,
            count(DISTINCT coalesce(public.nmw_temp_unit_code(td."TempUnit"), 'UNKNOWN')) > 1
                                                                 AS temp_unit_mixed,
            count(*) FILTER (
                WHERE public.nmw_temp_to_c(td."Temp", td."TempUnit") IS NULL
            )                                                    AS unconvertible_count,
            json_agg(
                json_build_object(
                    'depth', td."Depth",
                    'temp', td."Temp",
                    'temp_c', public.nmw_temp_to_c(td."Temp", td."TempUnit"),
                    'temp_unit_source',
                        coalesce(public.nmw_temp_unit_code(td."TempUnit"), 'UNKNOWN')
                )
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


def downgrade() -> None:
    # Restore the d1e2f3a4b5c6 definitions verbatim, then drop the helpers.
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_VIEW}"'))
    op.execute(text(f"""
        CREATE VIEW "{_BHT_VIEW}" AS
        {_LOC_CTE}
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
        JOIN loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        GROUP BY
            r."WellDataID",
            loc."Lat_dd83",
            loc."Long_dd83",
            hdr."CurWellNam",
            hdr."API",
            hdr."TotalDepth"
        """))

    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_PROFILE_VIEW}"'))
    op.execute(text(f"""
        CREATE MATERIALIZED VIEW "{_PROFILE_VIEW}" AS
        {_LOC_CTE}
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

    op.execute(
        text("DROP FUNCTION IF EXISTS public.nmw_temp_to_c(double precision, text)")
    )
    op.execute(text("DROP FUNCTION IF EXISTS public.nmw_temp_unit_code(text)"))
