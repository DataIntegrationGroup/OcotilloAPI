"""add transducer daily data materialized view

Aggregates raw transducer observations into one row per well, parameter,
day, and QC status. This is the new-model replacement for the legacy
NMA_WaterLevelsContinuous_Pressure_Daily table, which AMPAPI rebuilt
nightly from the raw continuous pressure record.

Revision ID: v0w1x2y3z4a5
Revises: u8v9w0x1y2z3
Create Date: 2026-06-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "v0w1x2y3z4a5"
down_revision: Union[str, Sequence[str], None] = "u8v9w0x1y2z3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "transducer_observation",
    "deployment",
    "thing",
    "parameter",
}

DROP_VIEW_SQL = "DROP MATERIALIZED VIEW IF EXISTS transducer_daily_data"


def _create_transducer_daily_data_view() -> str:
    # transducer_observation.value is depth to water in feet below ground
    # surface (the transfer wrote DepthToWaterBGS directly), so the daily
    # depth columns need no measuring-point correction.
    #
    # The transfer wrote legacy timestamps unshifted (naive local clock
    # readings stored as UTC), so bucketing on the UTC date preserves the
    # original measurement dates.
    #
    # QC status: the transfer marked QCed rows release_status='public' and
    # un-reviewed rows 'private', so qced mirrors the legacy QCed flag.
    return """
        CREATE MATERIALIZED VIEW transducer_daily_data AS
        SELECT
            d.thing_id,
            t.name AS point_id,
            tob.parameter_id,
            p.parameter_name,
            (tob.observation_datetime AT TIME ZONE 'UTC')::date AS date_measured,
            (tob.release_status = 'public') AS qced,
            avg(tob.value) AS depth_to_water_bgs,
            min(tob.value) AS depth_to_water_bgs_min,
            max(tob.value) AS depth_to_water_bgs_max,
            count(*) AS measurement_count,
            min(tob.observation_datetime) AS first_measurement_at,
            max(tob.observation_datetime) AS last_measurement_at,
            avg(tob.nma_waterlevelscontinuous_pressure_temperature_water) AS temperature_water,
            avg(tob.nma_waterlevelscontinuous_pressure_water_head) AS water_head,
            avg(tob.nma_waterlevelscontinuous_pressure_water_head_adjusted) AS water_head_adjusted,
            avg(tob.nma_waterlevelscontinuous_pressure_conddl_ms_cm) AS conddl_ms_cm
        FROM transducer_observation AS tob
        JOIN deployment AS d ON d.id = tob.deployment_id
        JOIN thing AS t ON t.id = d.thing_id
        JOIN parameter AS p ON p.id = tob.parameter_id
        GROUP BY
            d.thing_id,
            t.name,
            tob.parameter_id,
            p.parameter_name,
            (tob.observation_datetime AT TIME ZONE 'UTC')::date,
            (tob.release_status = 'public')
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot create transducer_daily_data. Missing required tables: "
            f"{', '.join(sorted(missing))}"
        )

    op.execute(text(DROP_VIEW_SQL))
    op.execute(text(_create_transducer_daily_data_view()))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW transducer_daily_data IS "
            "'Daily aggregates of transducer observations per well, parameter, "
            "and QC status. Replacement for the legacy "
            "NMA_WaterLevelsContinuous_Pressure_Daily table. Refresh with "
            "REFRESH MATERIALIZED VIEW CONCURRENTLY transducer_daily_data.'"
        )
    )
    # Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_transducer_daily_data_key "
            "ON transducer_daily_data (thing_id, parameter_id, date_measured, qced)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ix_transducer_daily_data_point_id_date "
            "ON transducer_daily_data (point_id, date_measured)"
        )
    )


def downgrade() -> None:
    op.execute(text(DROP_VIEW_SQL))
