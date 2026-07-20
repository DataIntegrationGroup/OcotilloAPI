"""add EDR water-level and water-chemistry views

Creates the ogc_waterlevels and ogc_water_chemistry views that back the OGC
API - EDR collections (see ADR3). Both views are publication-filtered to
release_status = 'public', matching the existing ogc_* feature-view convention.

ogc_waterlevels unions manual readings (Observation, parameter
"groundwater level") and transducer readings (TransducerObservation via
Deployment), so a collection-level query returns the merged series while the
deployment_id column still lets EDR expose each transducer deployment as an
instance.

ogc_water_chemistry exposes every non-water-level Observation (keyed by its
Parameter analyte) collected on a Sample.

Revision ID: z9a0b1c2d3e4
Revises: b6c7d8e9f0a1
Create Date: 2026-07-12 20:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "z9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "observation",
    "transducer_observation",
    "deployment",
    "sample",
    "field_activity",
    "field_event",
    "thing",
    "location",
    "location_thing_association",
    "parameter",
}

DROP_WATERLEVELS = "DROP VIEW IF EXISTS ogc_waterlevels"
DROP_WATER_CHEMISTRY = "DROP VIEW IF EXISTS ogc_water_chemistry"

# Shared join from a thing to its current location point.
_LOCATION_JOIN = """
    JOIN location_thing_association lta
        ON lta.thing_id = t.id AND lta.effective_end IS NULL
    JOIN location l ON l.id = lta.location_id
"""


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
        WHERE o.release_status = 'public' AND o.value IS NOT NULL

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
        WHERE tobs.release_status = 'public' AND tobs.value IS NOT NULL
    """


def _create_water_chemistry_view() -> str:
    return f"""
        CREATE VIEW ogc_water_chemistry AS
        SELECT
            'c-' || o.id                        AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            o.observation_datetime              AS datetime,
            o.value                             AS value,
            o.unit                              AS unit,
            p.parameter_name                    AS parameter_name,
            o.sample_id                         AS sample_id,
            o.release_status                    AS release_status
        FROM observation o
        JOIN parameter p
            ON p.id = o.parameter_id AND p.parameter_name <> 'groundwater level'
        JOIN sample sm ON sm.id = o.sample_id
        JOIN field_activity fa ON fa.id = sm.field_activity_id
        JOIN field_event fe ON fe.id = fa.field_event_id
        JOIN thing t ON t.id = fe.thing_id
        {_LOCATION_JOIN}
        WHERE o.release_status = 'public' AND o.value IS NOT NULL
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing
    if missing:
        raise RuntimeError(
            "Cannot create EDR water views. Missing required tables: "
            f"{sorted(missing)}"
        )

    op.execute(text(DROP_WATERLEVELS))
    op.execute(text(_create_waterlevels_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_waterlevels IS "
            "'Public depth-to-water readings (manual + transducer) for EDR.'"
        )
    )

    op.execute(text(DROP_WATER_CHEMISTRY))
    op.execute(text(_create_water_chemistry_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_water_chemistry IS "
            "'Public water-chemistry analyses (by analyte) for EDR.'"
        )
    )


def downgrade() -> None:
    op.execute(text(DROP_WATERLEVELS))
    op.execute(text(DROP_WATER_CHEMISTRY))
