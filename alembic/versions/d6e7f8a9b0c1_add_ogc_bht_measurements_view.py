"""add ogc_bht_measurements view

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-06-17

Individual BHT measurement rows with well header, location, and Z-datum
filter — translated from the legacy MSSQL query against NM_Aquifer.
One row per measurement (not aggregated per well).
"""

from alembic import op
from sqlalchemy import text

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None

_VIEW = "ogc_bht_measurements"


def upgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
    op.execute(
        text(
            f"""
        CREATE VIEW "{_VIEW}" AS
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
        """
        )
    )


def downgrade() -> None:
    op.execute(text(f'DROP VIEW IF EXISTS "{_VIEW}"'))
