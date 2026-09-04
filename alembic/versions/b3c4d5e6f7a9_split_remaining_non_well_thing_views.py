"""split remaining non-well Group A views to drop well-specific columns

Same fix as a2b3c4d5e6f7 (springs), applied to the other 8 non-well
layers: diversions_surface_water, ephemeral_streams, lakes_ponds_reservoirs,
meteorological_stations, outfalls_wastewater_return_flow,
perennial_streams, rock_sample_locations, soil_gas_sample_locations.
Checked db/thing.py for a type-specific column on each, the way springs had
spring_type -- none exists, so all 8 use the same non-well template as
springs, with no extra columns.

other_things is intentionally excluded -- it is an internal-only catch-all
for records that do not fit a defined feature type, so "well vs non-well"
does not apply to it.

water_wells and ogc_springs (already migrated) are unaffected.

downgrade() restores the exact pre-migration SQL (well columns +
last_observation_date) for each of the 8 layers.

Revision ID: b3c4d5e6f7a9
Revises: a2b3c4d5e6f7
Create Date: 2026-09-03 00:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a9"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "thing",
    "location",
    "location_thing_association",
    "observation",
    "sample",
    "field_activity",
    "field_event",
}

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()

# (view_id, thing_type) for the 8 remaining non-well Group A layers.
NON_WELL_VIEWS = [
    ("diversions_surface_water", "diversion of surface water, etc."),
    ("ephemeral_streams", "ephemeral stream"),
    ("lakes_ponds_reservoirs", "lake, pond or reservoir"),
    ("meteorological_stations", "meteorological station"),
    ("outfalls_wastewater_return_flow", "outfall of wastewater or return flow"),
    ("perennial_streams", "perennial stream"),
    ("rock_sample_locations", "rock sample location"),
    ("soil_gas_sample_locations", "soil gas sample location"),
]

# (view_name, thing_type, public_only) for both mounts of each layer.
VIEWS = [
    (f"{prefix}{view_id}", thing_type, public_only)
    for view_id, thing_type in NON_WELL_VIEWS
    for prefix, public_only in (("ogc_", True), ("ogc_internal_", False))
]


def _safe_relation_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Unsafe relation name: {name!r}")
    return name


def _check_required_tables() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot recreate the non-well Group A views. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_non_well_thing_view(
    view_name: str, thing_type: str, public_only: bool
) -> str:
    """Non-well Group A template: drops the 12 well-specific columns, keeps
    the generic last_observation_date lookup from b8c9d0e1f2a3."""
    safe_view_name = _safe_relation_name(view_name)
    escaped_thing_type = thing_type.replace("'", "''")
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    observation_release_filter = (
        "\n                  AND o.release_status = 'public'" if public_only else ""
    )
    return f"""
        CREATE VIEW {safe_view_name} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        )
        SELECT
            t.id,
            t.name,
            t.first_visit_date,
            (
                last_obs.last_observation_datetime AT TIME ZONE 'UTC'
            )::date AS last_observation_date,
            t.release_status,
            l.elevation,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        LEFT JOIN LATERAL (
            SELECT MAX(o.observation_datetime) AS last_observation_datetime
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            WHERE fe.thing_id = t.id{observation_release_filter}
        ) AS last_obs ON TRUE
        WHERE t.thing_type = '{escaped_thing_type}'{release_filter}
    """


def _create_thing_view_with_well_columns(
    view_name: str, thing_type: str, public_only: bool
) -> str:
    """Template as it stood immediately before this migration (well columns
    + last_observation_date, per b8c9d0e1f2a3), kept here only so
    downgrade() can restore each view byte-identically."""
    safe_view_name = _safe_relation_name(view_name)
    escaped_thing_type = thing_type.replace("'", "''")
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    observation_release_filter = (
        "\n                  AND o.release_status = 'public'" if public_only else ""
    )
    return f"""
        CREATE VIEW {safe_view_name} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        )
        SELECT
            t.id,
            t.name,
            t.first_visit_date,
            (
                last_obs.last_observation_datetime AT TIME ZONE 'UTC'
            )::date AS last_observation_date,
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
            l.elevation,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        LEFT JOIN LATERAL (
            SELECT MAX(o.observation_datetime) AS last_observation_datetime
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            WHERE fe.thing_id = t.id{observation_release_filter}
        ) AS last_obs ON TRUE
        WHERE t.thing_type = '{escaped_thing_type}'{release_filter}
    """


def upgrade() -> None:
    _check_required_tables()
    for view_name, thing_type, public_only in VIEWS:
        safe_view_name = _safe_relation_name(view_name)
        op.execute(text(f"DROP VIEW IF EXISTS {safe_view_name}"))
        op.execute(
            text(_create_non_well_thing_view(view_name, thing_type, public_only))
        )


def downgrade() -> None:
    for view_name, thing_type, public_only in VIEWS:
        safe_view_name = _safe_relation_name(view_name)
        op.execute(text(f"DROP VIEW IF EXISTS {safe_view_name}"))
        op.execute(
            text(
                _create_thing_view_with_well_columns(view_name, thing_type, public_only)
            )
        )
