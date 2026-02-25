"""Create pygeoapi supporting OGC views.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-02-25 12:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

THING_COLLECTIONS = [
    ("wells", "water well"),
    ("springs", "spring"),
    ("abandoned_wells", "abandoned well"),
    ("artesian_wells", "artesian well"),
    ("diversions_surface_water", "diversion of surface water, etc."),
    ("dry_holes", "dry hole"),
    ("dug_wells", "dug well"),
    ("ephemeral_streams", "ephemeral stream"),
    ("exploration_wells", "exploration well"),
    ("injection_wells", "injection well"),
    ("lakes_ponds_reservoirs", "lake, pond or reservoir"),
    ("meteorological_stations", "meteorological station"),
    ("monitoring_wells", "monitoring well"),
    ("observation_wells", "observation well"),
    ("other_things", "other"),
    ("outfalls_wastewater_return_flow", "outfall of wastewater or return flow"),
    ("perennial_streams", "perennial stream"),
    ("piezometers", "piezometer"),
    ("production_wells", "production well"),
    ("rock_sample_locations", "rock sample location"),
    ("soil_gas_sample_locations", "soil gas sample location"),
    ("test_wells", "test well"),
]


def _safe_view_id(view_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", view_id):
        raise ValueError(f"Unsafe view id: {view_id!r}")
    return view_id


def _create_thing_view(view_id: str, thing_type: str) -> str:
    safe_view_id = _safe_view_id(view_id)
    escaped_thing_type = thing_type.replace("'", "''")
    return f"""
        CREATE VIEW ogc_{safe_view_id} AS
        WITH latest_location AS (
            SELECT DISTINCT ON (lta.thing_id)
                lta.thing_id,
                lta.location_id,
                lta.effective_start
            FROM location_thing_association AS lta
            WHERE lta.effective_end IS NULL
            ORDER BY lta.thing_id, lta.effective_start DESC
        )
        SELECT
            t.id,
            t.name,
            t.thing_type,
            t.first_visit_date,
            t.spring_type,
            t.nma_pk_welldata,
            t.well_depth,
            t.hole_depth,
            t.well_casing_diameter,
            t.well_casing_depth,
            t.well_completion_date,
            t.well_driller_name,
            t.well_construction_method,
            t.well_pump_type,
            t.well_pump_depth,
            t.formation_completion_code,
            t.nma_formation_zone,
            t.release_status,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE t.thing_type = '{escaped_thing_type}'
    """


def _create_latest_depth_view() -> str:
    return """
        CREATE MATERIALIZED VIEW ogc_latest_depth_to_water_wells AS
        WITH latest_location AS (
            SELECT DISTINCT ON (lta.thing_id)
                lta.thing_id,
                lta.location_id,
                lta.effective_start
            FROM location_thing_association AS lta
            WHERE lta.effective_end IS NULL
            ORDER BY lta.thing_id, lta.effective_start DESC
        ),
        ranked_obs AS (
            SELECT
                fe.thing_id,
                o.id AS observation_id,
                o.observation_datetime,
                o.value,
                o.measuring_point_height,
                (o.value - o.measuring_point_height) AS depth_to_water_bgs,
                ROW_NUMBER() OVER (
                    PARTITION BY fe.thing_id
                    ORDER BY o.observation_datetime DESC, o.id DESC
                ) AS rn
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN thing AS t ON t.id = fe.thing_id
            WHERE
                t.thing_type = 'water well'
                AND fa.activity_type = 'groundwater level'
                AND o.value IS NOT NULL
                AND o.measuring_point_height IS NOT NULL
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            ro.observation_id,
            ro.observation_datetime,
            ro.value AS depth_to_water_reference,
            ro.measuring_point_height,
            ro.depth_to_water_bgs,
            l.point
        FROM ranked_obs AS ro
        JOIN thing AS t ON t.id = ro.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE ro.rn = 1
    """


def _create_latest_depth_fallback_view() -> str:
    return """
        CREATE MATERIALIZED VIEW ogc_latest_depth_to_water_wells AS
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            NULL::integer AS observation_id,
            NULL::timestamptz AS observation_datetime,
            NULL::double precision AS depth_to_water_reference,
            NULL::double precision AS measuring_point_height,
            NULL::double precision AS depth_to_water_bgs,
            l.point
        FROM thing AS t
        JOIN location_thing_association AS lta ON lta.thing_id = t.id
        JOIN location AS l ON l.id = lta.location_id
        WHERE FALSE
    """


def _create_avg_tds_view() -> str:
    return """
        CREATE MATERIALIZED VIEW ogc_avg_tds_wells AS
        WITH latest_location AS (
            SELECT DISTINCT ON (lta.thing_id)
                lta.thing_id,
                lta.location_id,
                lta.effective_start
            FROM location_thing_association AS lta
            WHERE lta.effective_end IS NULL
            ORDER BY lta.thing_id, lta.effective_start DESC
        ),
        tds_obs AS (
            SELECT
                csi.thing_id,
                mc.id AS major_chemistry_id,
                mc."AnalysisDate" AS analysis_date,
                mc."SampleValue" AS sample_value,
                mc."Units" AS units
            FROM "NMA_MajorChemistry" AS mc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mc.chemistry_sample_info_id
            JOIN thing AS t ON t.id = csi.thing_id
            WHERE
                t.thing_type = 'water well'
                AND mc."SampleValue" IS NOT NULL
                AND (
                    lower(coalesce(mc."Analyte", '')) IN (
                        'tds',
                        'total dissolved solids'
                    )
                    OR lower(coalesce(mc."Symbol", '')) = 'tds'
                )
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            COUNT(to2.major_chemistry_id)::integer AS tds_observation_count,
            AVG(to2.sample_value)::double precision AS avg_tds_value,
            MIN(to2.analysis_date) AS first_tds_observation_datetime,
            MAX(to2.analysis_date) AS latest_tds_observation_datetime,
            l.point
        FROM tds_obs AS to2
        JOIN thing AS t ON t.id = to2.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        GROUP BY t.id, t.name, t.thing_type, l.point
    """


def _create_avg_tds_fallback_view() -> str:
    return """
        CREATE MATERIALIZED VIEW ogc_avg_tds_wells AS
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            NULL::integer AS tds_observation_count,
            NULL::double precision AS avg_tds_value,
            NULL::timestamptz AS first_tds_observation_datetime,
            NULL::timestamptz AS latest_tds_observation_datetime,
            l.point
        FROM thing AS t
        JOIN location_thing_association AS lta ON lta.thing_id = t.id
        JOIN location AS l ON l.id = lta.location_id
        WHERE FALSE
    """


def _drop_view_or_materialized_view(view_name: str) -> None:
    op.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
    op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    required_core = {"thing", "location", "location_thing_association"}
    existing_tables = set(inspector.get_table_names(schema="public"))
    if not required_core.issubset(existing_tables):
        missing_tables = sorted(t for t in required_core if t not in existing_tables)
        missing_tables_str = ", ".join(missing_tables)
        raise RuntimeError(
            "Cannot create pygeoapi supporting views. The following required core "
            f"tables are missing: {missing_tables_str}"
        )

    for view_id, thing_type in THING_COLLECTIONS:
        safe_view_id = _safe_view_id(view_id)
        op.execute(text(f"DROP VIEW IF EXISTS ogc_{safe_view_id}"))
        op.execute(text(_create_thing_view(view_id, thing_type)))

    _drop_view_or_materialized_view("ogc_latest_depth_to_water_wells")
    required_depth = {"observation", "sample", "field_activity", "field_event"}
    if required_depth.issubset(existing_tables):
        op.execute(text(_create_latest_depth_view()))
        op.execute(
            text(
                "COMMENT ON MATERIALIZED VIEW ogc_latest_depth_to_water_wells IS "
                "'Latest depth-to-water per well view for pygeoapi.'"
            )
        )
    else:
        op.execute(text(_create_latest_depth_fallback_view()))
        op.execute(
            text(
                "COMMENT ON MATERIALIZED VIEW ogc_latest_depth_to_water_wells IS "
                "'STUB VIEW: required source tables (observation/sample/field_activity/field_event) were missing at migration time; this view intentionally returns zero rows.'"
            )
        )

    _drop_view_or_materialized_view("ogc_avg_tds_wells")
    required_tds = {"NMA_MajorChemistry", "NMA_Chemistry_SampleInfo"}
    if required_tds.issubset(existing_tables):
        op.execute(text(_create_avg_tds_view()))
        op.execute(
            text(
                "COMMENT ON MATERIALIZED VIEW ogc_avg_tds_wells IS "
                "'Average TDS per well from major chemistry results for pygeoapi.'"
            )
        )
    else:
        op.execute(text(_create_avg_tds_fallback_view()))
        op.execute(
            text(
                "COMMENT ON MATERIALIZED VIEW ogc_avg_tds_wells IS "
                "'STUB VIEW: required source tables (NMA_MajorChemistry/NMA_Chemistry_SampleInfo) were missing at migration time; this view intentionally returns zero rows.'"
            )
        )


def downgrade() -> None:
    _drop_view_or_materialized_view("ogc_avg_tds_wells")
    _drop_view_or_materialized_view("ogc_latest_depth_to_water_wells")
    for view_id, _ in THING_COLLECTIONS:
        safe_view_id = _safe_view_id(view_id)
        op.execute(text(f"DROP VIEW IF EXISTS ogc_{safe_view_id}"))
