"""add geothermal per-interval heat-flow OGC view

Revision ID: y1z2a3b4c5d6
Revises: x0y1z2a3b4c5
Create Date: 2026-06-07 00:00:02.000000

pygeoapi point layer of geothermal wells with per-interval heat-flow values
(NMW_GtHeatFlow), one feature per well with aggregate stats plus a
`measurements` JSON series (one element per interval, ordered by depth).
Distinct from ogc_geothermal_wells_summary_heat_flow (NMW_GtSumHeatFlow).

Link: NMW_GtHeatFlow.IntrvlGUID -> NMW_WsIntervals.IntrvlGUID ->
NMW_WellSamples.SamplSetID -> NMW_WellRecords.RecrdSetID ->
NMW_WellLocations/Headers.WellDataID.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "y1z2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "x0y1z2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEW = "ogc_geothermal_wells_interval_heat_flow"

_REQUIRED_TABLES = (
    "NMW_WellLocations",
    "NMW_WellHeaders",
    "NMW_WellRecords",
    "NMW_WellSamples",
    "NMW_WsIntervals",
    "NMW_GtHeatFlow",
)


def _create_view() -> str:
    return """
        CREATE VIEW ogc_geothermal_wells_interval_heat_flow AS
        SELECT
            r."WellDataID"                          AS well_data_id,
            hdr."CurWellNam"                        AS well_name,
            hdr."API"                               AS api,
            count(hf.*)                             AS interval_count,
            max(hf."Q")                             AS max_heat_flow,
            avg(hf."Q")                             AS avg_heat_flow,
            max(hf."Q_unit")                        AS heat_flow_unit,
            max(hf."Gradient")                      AS max_gradient,
            max(hf."Kpr")                           AS max_thermal_conductivity,
            max(hf."Kpr_unit")                      AS conductivity_unit,
            max(hf."Ka")                            AS max_diffusivity,
            max(hf."Ka_unit")                       AS diffusivity_unit,
            json_agg(
                json_build_object(
                    'from_depth', i."From_Depth",
                    'to_depth', i."To_Depth",
                    'heat_flow', hf."Q",
                    'heat_flow_unit', hf."Q_unit",
                    'gradient', hf."Gradient",
                    'thermal_conductivity', hf."Kpr",
                    'conductivity_unit', hf."Kpr_unit",
                    'diffusivity', hf."Ka",
                    'diffusivity_unit', hf."Ka_unit"
                )
                ORDER BY i."From_Depth"
            )                                       AS measurements,
            ST_SetSRID(
                ST_MakePoint(loc."Long_dd83", loc."Lat_dd83"), 4326
            )                                       AS geom
        FROM "NMW_GtHeatFlow" AS hf
        JOIN "NMW_WsIntervals" AS i ON i."IntrvlGUID" = hf."IntrvlGUID"
        JOIN "NMW_WellSamples" AS s ON s."SamplSetID" = i."SamplSetID"
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
            hdr."API"
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))
    missing = [t for t in _REQUIRED_TABLES if t not in existing]
    if missing:
        raise RuntimeError(
            "Cannot create geothermal interval heat-flow OGC view. Missing "
            "required tables: " + ", ".join(missing)
        )

    op.execute(text(f"DROP VIEW IF EXISTS {_VIEW}"))
    op.execute(text(_create_view()))
    op.execute(
        text(
            f"COMMENT ON VIEW {_VIEW} IS "
            "'Geothermal wells with per-interval heat-flow values (pygeoapi).'"
        )
    )


def downgrade() -> None:
    op.execute(text(f"DROP VIEW IF EXISTS {_VIEW}"))
