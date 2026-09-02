"""split springs view to drop well-specific columns

All 11 Group A thing-type views (ogc_water_wells, ogc_springs, ...) share one
view template (_create_thing_view in f4a5b6c7d8e9 / 2d3c3a268652), which
carries 12 well-specific columns -- nma_pk_welldata, well_depth, hole_depth,
well_casing_diameter, well_casing_depth, well_completion_date,
well_driller_name, well_construction_method, well_pump_type, well_pump_depth,
formation_completion_code, nma_formation_zone -- on every layer, well or not.
A consumer browsing ogc_springs sees a well_depth column that is always NULL
for every spring, with nothing to say it will never hold data.

This is the first of a staged split: only ogc_springs and
ogc_internal_springs move to a non-well template here (6 columns: id, name,
first_visit_date, release_status, elevation, point). The other 9 non-well
layers keep the well-carrying template for now and move in follow-up
migrations, one at a time. ogc_water_wells is unaffected either way -- it
actually needs the well columns.

downgrade() recreates both springs views with the exact original 18-column
SQL, so it's fully reversible.

Revision ID: a2b3c4d5e6f7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-02 00:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "thing",
    "location",
    "location_thing_association",
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

VIEWS = [
    ("ogc_springs", True),
    ("ogc_internal_springs", False),
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
            "Cannot recreate the springs view. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_non_well_thing_view(view_name: str, public_only: bool) -> str:
    """Non-well Group A template: drops the 12 well-specific columns."""
    safe_view_name = _safe_relation_name(view_name)
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW {safe_view_name} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        )
        SELECT
            t.id,
            t.name,
            t.first_visit_date,
            t.release_status,
            l.elevation,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE t.thing_type = 'spring'{release_filter}
    """


def _create_thing_view_with_well_columns(view_name: str, public_only: bool) -> str:
    """Original shared Group A template, kept here only so downgrade() can
    restore ogc_springs / ogc_internal_springs byte-identically."""
    safe_view_name = _safe_relation_name(view_name)
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW {safe_view_name} AS
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
        WHERE t.thing_type = 'spring'{release_filter}
    """


def upgrade() -> None:
    _check_required_tables()
    for view_name, public_only in VIEWS:
        safe_view_name = _safe_relation_name(view_name)
        op.execute(text(f"DROP VIEW IF EXISTS {safe_view_name}"))
        op.execute(text(_create_non_well_thing_view(view_name, public_only)))


def downgrade() -> None:
    for view_name, public_only in VIEWS:
        safe_view_name = _safe_relation_name(view_name)
        op.execute(text(f"DROP VIEW IF EXISTS {safe_view_name}"))
        op.execute(text(_create_thing_view_with_well_columns(view_name, public_only)))
