"""add last_observation_date to the Group A thing views

Ticket A13. The 11 thing-type layers (Group A) carry construction and location
detail but no signal of data recency: a consumer could not tell a well measured
last month from one last visited in 1994 without querying a second layer.

This adds `last_observation_date` to the shared thing-view template -- the date
of the most recent observation recorded against the thing, or NULL where the
thing has no observations at all. All 11 public views and their 11
`ogc_internal_` counterparts are rebuilt from the same template here, so the
two mounts stay column-for-column identical.

Scope of "observation": rows in the `observation` table, reached through the
sample -> field_activity -> field_event chain that every other observation-
backed view in this schema uses. Continuous transducer readings
(`transducer_observation`) are deliberately *not* folded in: they live on a
different chain (deployment -> thing), they exist for a handful of instrumented
water wells rather than for Group A generally, and a max() over the largest
table in the schema would need its own index on
(deployment_id, observation_datetime) to stay cheap. Wells with logger data are
served by ogc_actively_monitored_wells and the water-elevation layers. If
Group A currency should later include instrument readings, that is a separate
ticket and a separate index.

The date is the UTC calendar date of the observation timestamp -- same
convention as transducer_daily_data (v0w1x2y3z4a5) -- rather than a
session-timezone cast, so the value does not depend on who is querying.

Public views count only observations with release_status='public', matching how
the public mount filters everything else; the internal views count all of them.
A public well whose only observations are private therefore reads NULL on
/ogcapi and carries a date on /ogcapi-internal.

Per-thing lookup is a LEFT JOIN LATERAL rather than a grouped CTE so that a
paginated or single-feature request touches only the observations of the rows
it returns. That path had no indexes at all (Postgres does not index foreign
keys on its own), so the four it needs are created here.

The view bodies below are otherwise character-for-character the templates from
f4a5b6c7d8e9 (public) and 2d3c3a268652 (internal); downgrade() restores them.

Revision ID: b8c9d0e1f2a3
Revises: 986e0eb85ab3
Create Date: 2026-08-24 00:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "baba91fe5e83"
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

# Same 11 thing-type views as f4a5b6c7d8e9's THING_VIEWS.
THING_VIEWS = [
    ("water_wells", "water well"),
    ("springs", "spring"),
    ("diversions_surface_water", "diversion of surface water, etc."),
    ("ephemeral_streams", "ephemeral stream"),
    ("lakes_ponds_reservoirs", "lake, pond or reservoir"),
    ("meteorological_stations", "meteorological station"),
    ("other_things", "other"),
    ("outfalls_wastewater_return_flow", "outfall of wastewater or return flow"),
    ("perennial_streams", "perennial stream"),
    ("rock_sample_locations", "rock sample location"),
    ("soil_gas_sample_locations", "soil gas sample location"),
]

# (name, table, columns) for the observation chain the lateral walks
# thing -> field_event -> field_activity -> sample -> observation.
SUPPORTING_INDEXES = [
    ("ix_field_event_thing_id", "field_event", "thing_id"),
    ("ix_field_activity_field_event_id", "field_activity", "field_event_id"),
    ("ix_sample_field_activity_id", "sample", "field_activity_id"),
    (
        "ix_observation_sample_id_observation_datetime",
        "observation",
        "sample_id, observation_datetime",
    ),
]


def _safe_view_id(view_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", view_id):
        raise ValueError(f"Unsafe view id: {view_id!r}")
    return view_id


def _check_required_tables() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot add last_observation_date to the OGC thing views. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_thing_view(
    view_id: str, thing_type: str, public_only: bool, table_prefix: str
) -> str:
    """The Group A view template, with last_observation_date."""
    safe_view_id = _safe_view_id(f"{table_prefix}{view_id}")
    escaped_thing_type = thing_type.replace("'", "''")
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    observation_release_filter = (
        "\n                  AND o.release_status = 'public'" if public_only else ""
    )
    return f"""
        CREATE VIEW {safe_view_id} AS
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


def _create_thing_view_pre_a13(
    view_id: str, thing_type: str, public_only: bool, table_prefix: str
) -> str:
    """The template as it stood in f4a5b6c7d8e9/2d3c3a268652, for downgrade."""
    safe_view_id = _safe_view_id(f"{table_prefix}{view_id}")
    escaped_thing_type = thing_type.replace("'", "''")
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW {safe_view_id} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        )
        SELECT
            t.id,
            t.name,
            t.first_visit_date,
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
        WHERE t.thing_type = '{escaped_thing_type}'{release_filter}
    """


def _rebuild_thing_views(builder) -> None:
    for table_prefix, public_only in (("ogc_", True), ("ogc_internal_", False)):
        for view_id, thing_type in THING_VIEWS:
            view_name = _safe_view_id(f"{table_prefix}{view_id}")
            op.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
            op.execute(text(builder(view_id, thing_type, public_only, table_prefix)))


def upgrade() -> None:
    _check_required_tables()

    for index_name, table_name, columns in SUPPORTING_INDEXES:
        op.execute(
            text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
        )

    _rebuild_thing_views(_create_thing_view)


def downgrade() -> None:
    _rebuild_thing_views(_create_thing_view_pre_a13)

    for index_name, _table_name, _columns in SUPPORTING_INDEXES:
        op.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
