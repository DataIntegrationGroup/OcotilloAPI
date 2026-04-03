"""drop unused well-type OGC views

Revision ID: s4t5u6v7w8x9
Revises: r2s3t4u5v6w7
Create Date: 2026-03-19 14:30:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "s4t5u6v7w8x9"
down_revision: Union[str, Sequence[str], None] = "r2s3t4u5v6w7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOVED_THING_COLLECTIONS = [
    ("abandoned_wells", "abandoned well"),
    ("artesian_wells", "artesian well"),
    ("dry_holes", "dry hole"),
    ("dug_wells", "dug well"),
    ("exploration_wells", "exploration well"),
    ("injection_wells", "injection well"),
    ("monitoring_wells", "monitoring well"),
    ("observation_wells", "observation well"),
    ("piezometers", "piezometer"),
    ("production_wells", "production well"),
    ("test_wells", "test well"),
]

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()


def _safe_view_id(view_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", view_id):
        raise ValueError(f"Unsafe view id: {view_id!r}")
    return view_id


def _drop_view_or_materialized_view(view_name: str) -> None:
    op.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
    op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))


def _create_thing_view(view_id: str, thing_type: str) -> str:
    safe_view_id = _safe_view_id(view_id)
    escaped_thing_type = thing_type.replace("'", "''")
    return f"""
        CREATE VIEW ogc_{safe_view_id} AS
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
        WHERE t.thing_type = '{escaped_thing_type}'
    """


def upgrade() -> None:
    for view_id, _ in REMOVED_THING_COLLECTIONS:
        _drop_view_or_materialized_view(f"ogc_{_safe_view_id(view_id)}")


def downgrade() -> None:
    for view_id, thing_type in REMOVED_THING_COLLECTIONS:
        safe_view_id = _safe_view_id(view_id)
        _drop_view_or_materialized_view(f"ogc_{safe_view_id}")
        op.execute(text(_create_thing_view(view_id, thing_type)))
