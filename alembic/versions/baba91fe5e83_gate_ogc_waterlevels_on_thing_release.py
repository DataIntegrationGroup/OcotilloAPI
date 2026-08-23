"""gate ogc_waterlevels on the thing's release status

ogc_waterlevels filtered on the reading's own release_status only, so a well
whose release_status is 'draft' or 'private' still published its public
readings through OGC API - EDR -- with the well's name and coordinates
attached. ogc_water_chemistry (d9e0f1a2b3c4) already required the parent thing
to be public; this brings water levels onto the same rule.

The internal mirror, ogc_internal_waterlevels, is deliberately left alone: it
carries non-public records by design for authenticated staff clients, the same
way ogc_internal_water_chemistry does.

Revision ID: baba91fe5e83
Revises: 986e0eb85ab3
Create Date: 2026-08-22 18:35:00.000000

"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "baba91fe5e83"
down_revision: Union[str, Sequence[str], None] = "986e0eb85ab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORIGINAL_REVISION = "z9a0b1c2d3e4_add_edr_water_views.py"

# Shared join from a thing to its current location point. Mirrors the join in
# z9a0b1c2d3e4, which is the definition of record for this view.
_LOCATION_JOIN = """
    JOIN location_thing_association lta
        ON lta.thing_id = t.id AND lta.effective_end IS NULL
    JOIN location l ON l.id = lta.location_id
"""


def _load_original_module():
    """Import z9a0b1c2d3e4 so downgrade restores its SQL rather than a copy."""
    path = Path(__file__).with_name(_ORIGINAL_REVISION)
    if not path.exists():
        raise RuntimeError(
            "Cannot restore the previous ogc_waterlevels definition: "
            f"{_ORIGINAL_REVISION} is missing from alembic/versions."
        )
    spec = importlib.util.spec_from_file_location("_edr_water_views", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_waterlevels_view() -> str:
    return f"""
        CREATE VIEW ogc_waterlevels AS
        -- manual water-level readings
        SELECT
            'm-' || o.id                        AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            o.observation_datetime              AS datetime,
            o.value                             AS value,
            o.unit                              AS unit,
            'groundwater level'                 AS parameter_name,
            'manual'                            AS source,
            NULL::integer                       AS deployment_id,
            o.release_status                    AS release_status
        FROM observation o
        JOIN parameter p
            ON p.id = o.parameter_id AND p.parameter_name = 'groundwater level'
        JOIN sample sm ON sm.id = o.sample_id
        JOIN field_activity fa ON fa.id = sm.field_activity_id
        JOIN field_event fe ON fe.id = fa.field_event_id
        JOIN thing t ON t.id = fe.thing_id
        {_LOCATION_JOIN}
        WHERE o.release_status = 'public'
          AND t.release_status = 'public'
          AND o.value IS NOT NULL

        UNION ALL

        -- transducer (instrument) water-level readings
        SELECT
            't-' || tobs.id                     AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            tobs.observation_datetime           AS datetime,
            tobs.value                          AS value,
            p.default_unit                      AS unit,
            'groundwater level'                 AS parameter_name,
            'transducer'                        AS source,
            tobs.deployment_id                  AS deployment_id,
            tobs.release_status                 AS release_status
        FROM transducer_observation tobs
        JOIN parameter p
            ON p.id = tobs.parameter_id AND p.parameter_name = 'groundwater level'
        JOIN deployment d ON d.id = tobs.deployment_id
        JOIN thing t ON t.id = d.thing_id
        {_LOCATION_JOIN}
        WHERE tobs.release_status = 'public'
          AND t.release_status = 'public'
          AND tobs.value IS NOT NULL
    """


def upgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS ogc_waterlevels"))
    op.execute(text(_create_waterlevels_view()))


def downgrade() -> None:
    original = _load_original_module()
    op.execute(text("DROP VIEW IF EXISTS ogc_waterlevels"))
    op.execute(text(original._create_waterlevels_view()))
