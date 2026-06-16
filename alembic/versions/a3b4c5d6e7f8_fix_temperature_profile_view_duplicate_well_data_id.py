"""fix temperature profile view duplicate well_data_id

Revision ID: a3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-06-15

NMW_WellLocations has multiple rows per WellDataID (OBJECTID is its PK, not
WellDataID). The prior view grouped by WellDataID + Lat_dd83 + Long_dd83,
producing one row per (well, location) pair. When a well has more than one
location row the unique index on well_data_id fails at REFRESH time.

Fix: deduplicate NMW_WellLocations to one row per WellDataID via DISTINCT ON
before joining, so the GROUP BY always yields exactly one row per well.
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "z2a3b4c5d6e7"
branch_labels = None
depends_on = None

_VIEW = "ogc_geothermal_wells_temperature_profile"


def upgrade() -> None:
    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_VIEW}"'))
    op.execute(
        text(
            f"""
        CREATE MATERIALIZED VIEW "{_VIEW}" AS
        WITH loc AS (
            SELECT DISTINCT ON ("WellDataID")
                "WellDataID", "Lat_dd83", "Long_dd83"
            FROM "NMW_WellLocations"
            WHERE "Lat_dd83" IS NOT NULL
              AND "Long_dd83" IS NOT NULL
            ORDER BY "WellDataID", "OBJECTID"
        )
        SELECT
            r."WellDataID"                                       AS well_data_id,
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
            f"CREATE UNIQUE INDEX ux_{_VIEW}_well_data_id "
            f'ON "{_VIEW}" (well_data_id)'
        )
    )
    op.execute(text(f'CREATE INDEX ix_{_VIEW}_geom ON "{_VIEW}" USING GIST (geom)'))


def downgrade() -> None:
    op.execute(text(f'DROP MATERIALIZED VIEW IF EXISTS "{_VIEW}"'))
    # Restore the original view (without the DISTINCT ON deduplication).
    op.execute(
        text(
            f"""
        CREATE MATERIALIZED VIEW "{_VIEW}" AS
        SELECT
            r."WellDataID"                                       AS well_data_id,
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
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        WHERE loc."Lat_dd83" IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
          AND td."Depth" IS NOT NULL
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
            f"CREATE UNIQUE INDEX ux_{_VIEW}_well_data_id "
            f'ON "{_VIEW}" (well_data_id)'
        )
    )
    op.execute(text(f'CREATE INDEX ix_{_VIEW}_geom ON "{_VIEW}" USING GIST (geom)'))
