"""add geothermal OGC views (bottom-hole temps + temperature-depth profile)

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-06-07 00:00:00.000000

Two point layers over the NM_Wells staging mirror (db/nmw_legacy.py):

    ogc_geothermal_wells_bht
        One feature per geothermal well that has bottom-hole-temperature data
        (NMW_GtBhtData), with aggregate BHT stats.

    ogc_geothermal_wells_temperature_profile  (MATERIALIZED)
        One feature per geothermal well that has a downhole temperature-vs-depth
        series (NMW_GtTempDepths, ~370k source rows), with the ordered series as
        a JSON array. Materialized + indexed (unique well_data_id, GiST geom);
        REFRESH MATERIALIZED VIEW after a data reload.

Well geometry is built from NMW_WellLocations Lat/Long_dd83 (WGS84). Geothermal
data links to a well via:
    gt_*.SamplSetID -> NMW_WellSamples.SamplSetID
    NMW_WellSamples.RecrdsetID -> NMW_WellRecords.RecrdSetID
    NMW_WellRecords.WellDataID -> NMW_WellLocations/Headers.WellDataID
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "w9x0y1z2a3b4"
down_revision: Union[str, Sequence[str], None] = "v8w9x0y1z2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BHT_VIEW = "ogc_geothermal_wells_bht"
_PROFILE_VIEW = "ogc_geothermal_wells_temperature_profile"

_REQUIRED_TABLES = (
    "NMW_WellLocations",
    "NMW_WellHeaders",
    "NMW_WellRecords",
    "NMW_WellSamples",
    "NMW_GtBhtData",
    "NMW_GtBhtHeaders",
    "NMW_GtTempDepths",
)


def _create_bht_view() -> str:
    return """
        CREATE VIEW ogc_geothermal_wells_bht AS
        SELECT
            r."WellDataID"                                       AS well_data_id,
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


def _create_profile_view() -> str:
    # Materialized: the source NMW_GtTempDepths is large (~370k source rows) and
    # this groups + builds a JSON series per well, too heavy to recompute per
    # pygeoapi request. Staging data loads once, so staleness is a non-issue;
    # REFRESH MATERIALIZED VIEW after a reload.
    return """
        CREATE MATERIALIZED VIEW ogc_geothermal_wells_temperature_profile AS
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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))
    missing = [t for t in _REQUIRED_TABLES if t not in existing]
    if missing:
        raise RuntimeError(
            "Cannot create geothermal OGC views. Missing required tables: "
            + ", ".join(missing)
        )

    op.execute(text(f"DROP VIEW IF EXISTS {_BHT_VIEW}"))
    op.execute(text(_create_bht_view()))
    op.execute(
        text(
            f"COMMENT ON VIEW {_BHT_VIEW} IS "
            "'Geothermal wells with bottom-hole-temperature data.'"
        )
    )

    op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {_PROFILE_VIEW}"))
    op.execute(text(f"DROP VIEW IF EXISTS {_PROFILE_VIEW}"))
    op.execute(text(_create_profile_view()))
    op.execute(
        text(
            f"COMMENT ON MATERIALIZED VIEW {_PROFILE_VIEW} IS "
            "'Geothermal wells with downhole temperature-vs-depth series.'"
        )
    )
    # Unique index on the feature id enables REFRESH ... CONCURRENTLY; GiST on
    # the geometry for fast pygeoapi bbox queries.
    op.execute(
        text(
            f"CREATE UNIQUE INDEX ux_{_PROFILE_VIEW}_well_data_id "
            f"ON {_PROFILE_VIEW} (well_data_id)"
        )
    )
    op.execute(
        text(
            f"CREATE INDEX ix_{_PROFILE_VIEW}_geom ON {_PROFILE_VIEW} USING gist (geom)"
        )
    )


def downgrade() -> None:
    op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {_PROFILE_VIEW}"))
    op.execute(text(f"DROP VIEW IF EXISTS {_BHT_VIEW}"))
