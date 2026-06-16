"""add integer id to geothermal OGC views

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-15

All other OGC views use an integer id_field (from thing.id). pygeoapi's
PostgreSQL provider is tested against integer PKs. Replace well_data_id as the
id_field with row_number() OVER () AS id to match the convention, and keep
well_data_id as a regular attribute column.
"""

from alembic import op
from sqlalchemy import text

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None

_BHT_VIEW = "ogc_geothermal_wells_bht"
_PROFILE_VIEW = "ogc_geothermal_wells_temperature_profile"


def upgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_VIEW}"'))
    op.execute(
        text(
            f"""
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
        """
        )
    )

    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_PROFILE_VIEW}"'))
    op.execute(
        text(
            f"""
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
        """
        )
    )
    op.execute(
        text(f"CREATE UNIQUE INDEX ux_{_PROFILE_VIEW}_id " f'ON "{_PROFILE_VIEW}" (id)')
    )
    op.execute(
        text(
            f'CREATE INDEX ix_{_PROFILE_VIEW}_geom ON "{_PROFILE_VIEW}" USING GIST (geom)'
        )
    )


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_BHT_VIEW}"'))
    op.execute(
        text(
            f"""
        CREATE VIEW "{_BHT_VIEW}" AS
        SELECT
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
        """
        )
    )

    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_PROFILE_VIEW}"'))
    op.execute(
        text(
            f"""
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
        """
        )
    )
    op.execute(
        text(
            f"CREATE UNIQUE INDEX ux_{_PROFILE_VIEW}_well_data_id "
            f'ON "{_PROFILE_VIEW}" (well_data_id)'
        )
    )
    op.execute(
        text(
            f'CREATE INDEX ix_{_PROFILE_VIEW}_geom ON "{_PROFILE_VIEW}" USING GIST (geom)'
        )
    )
