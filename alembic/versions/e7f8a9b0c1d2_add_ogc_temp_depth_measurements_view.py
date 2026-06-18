"""add ogc_temp_depth_measurements view

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-06-18

Individual temperature-depth readings with well header, location, and
elevation data. Translated from the legacy MSSQL TempDepth2_SortedWellName
query against NM_Aquifer. One row per reading; locations with Exclude=1
are filtered out.
"""

from alembic import op
from sqlalchemy import text

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None

_VIEW = "ogc_temp_depth_measurements"


def upgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
    op.execute(
        text(
            f"""
        CREATE VIEW "{_VIEW}" AS
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
        """
        )
    )


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
