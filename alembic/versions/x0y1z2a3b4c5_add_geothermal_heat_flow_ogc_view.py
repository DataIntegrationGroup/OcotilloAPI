"""add geothermal heat-flow OGC view

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-06-07 00:00:01.000000

pygeoapi point layer of geothermal wells with summary heat-flow determinations
(NMW_GtSumHeatFlow), one feature per well with aggregate heat-flow / gradient /
conductivity stats. Geometry from NMW_WellLocations Lat/Long_dd83.

Link: NMW_GtSumHeatFlow.RecrdSetID -> NMW_WellRecords.RecrdSetID ->
NMW_WellLocations/Headers.WellDataID.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "x0y1z2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "w9x0y1z2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEW = "ogc_geothermal_wells_heat_flow"

_REQUIRED_TABLES = (
    "NMW_WellLocations",
    "NMW_WellHeaders",
    "NMW_WellRecords",
    "NMW_GtSumHeatFlow",
)


def _create_view() -> str:
    return """
        CREATE VIEW ogc_geothermal_wells_heat_flow AS
        SELECT
            r."WellDataID"                                       AS well_data_id,
            hdr."CurWellNam"                                     AS well_name,
            hdr."API"                                            AS api,
            count(shf.*)                                         AS heat_flow_count,
            max(shf."HeatFlow")                                  AS max_heat_flow,
            avg(shf."HeatFlow")                                  AS avg_heat_flow,
            max(shf."HtFlowUnit")                                AS heat_flow_unit,
            max(shf."ThermlGrad")                                AS max_thermal_gradient,
            max(shf."GradUnit")                                  AS gradient_unit,
            max(shf."ThermlCond")                                AS max_thermal_conductivity,
            max(shf."TCondUnit")                                 AS conductivity_unit,
            max(shf."Quality")                                   AS quality,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                                    AS geom
        FROM "NMW_GtSumHeatFlow" AS shf
        JOIN "NMW_WellRecords" AS r ON r."RecrdSetID" = shf."RecrdSetID"
        JOIN "NMW_WellLocations" AS loc ON loc."WellDataID" = r."WellDataID"
        LEFT JOIN "NMW_WellHeaders" AS hdr ON hdr."WellDataID" = r."WellDataID"
        WHERE loc."Lat_dd83" IS NOT NULL
          AND loc."Long_dd83" IS NOT NULL
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
            "Cannot create geothermal heat-flow OGC view. Missing required "
            "tables: " + ", ".join(missing)
        )

    op.execute(text(f"DROP VIEW IF EXISTS {_VIEW}"))
    op.execute(text(_create_view()))
    op.execute(
        text(
            f"COMMENT ON VIEW {_VIEW} IS "
            "'Geothermal wells with summary heat-flow determinations (pygeoapi).'"
        )
    )


def downgrade() -> None:
    op.execute(text(f"DROP VIEW IF EXISTS {_VIEW}"))
