"""add latest tds pygeoapi materialized view

Revision ID: i2b3c4d5e6f7
Revises: d5e6f7a8b9c0
Create Date: 2026-03-02 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "i2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()


def _create_latest_tds_view() -> str:
    return f"""
        CREATE VIEW ogc_latest_tds_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        tds_obs AS (
            SELECT
                csi.thing_id,
                mc.id AS major_chemistry_id,
                COALESCE(mc."AnalysisDate", csi."CollectionDate") AS observation_datetime,
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
        ),
        ranked_tds AS (
            SELECT
                to2.thing_id,
                to2.major_chemistry_id,
                to2.observation_datetime,
                to2.sample_value,
                to2.units,
                ROW_NUMBER() OVER (
                    PARTITION BY to2.thing_id
                    ORDER BY to2.observation_datetime DESC NULLS LAST, to2.major_chemistry_id DESC
                ) AS rn
            FROM tds_obs AS to2
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            rt.major_chemistry_id,
            rt.observation_datetime::date AS latest_tds_observation_date,
            rt.sample_value AS latest_tds_value,
            rt.units AS latest_tds_units,
            l.point
        FROM ranked_tds AS rt
        JOIN thing AS t ON t.id = rt.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE rt.rn = 1
    """


def _create_avg_tds_view() -> str:
    return f"""
        CREATE MATERIALIZED VIEW ogc_avg_tds_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        tds_obs AS (
            SELECT
                csi.thing_id,
                mc.id AS major_chemistry_id,
                COALESCE(mc."AnalysisDate", csi."CollectionDate")::date AS observation_date,
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
            MIN(to2.observation_date) AS first_tds_observation_date,
            MAX(to2.observation_date) AS last_tds_observation_date,
            l.point
        FROM tds_obs AS to2
        JOIN thing AS t ON t.id = to2.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        GROUP BY t.id, t.name, t.thing_type, l.point
    """


def _create_avg_tds_view_with_datetime_columns() -> str:
    return f"""
        CREATE MATERIALIZED VIEW ogc_avg_tds_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
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
            MIN(to2.analysis_date::date) AS first_tds_observation_date,
            MAX(to2.analysis_date::date) AS last_tds_observation_date,
            l.point
        FROM tds_obs AS to2
        JOIN thing AS t ON t.id = to2.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        GROUP BY t.id, t.name, t.thing_type, l.point
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    required_tds = {"NMA_MajorChemistry", "NMA_Chemistry_SampleInfo"}

    if not required_tds.issubset(existing_tables):
        missing_tds_tables = sorted(t for t in required_tds if t not in existing_tables)
        missing_tds_tables_str = ", ".join(missing_tds_tables)
        raise RuntimeError(
            "Cannot create TDS views. The following required "
            f"tables are missing: {missing_tds_tables_str}"
        )

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_avg_tds_wells"))
    op.execute(text("DROP VIEW IF EXISTS ogc_latest_tds_wells"))
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_latest_tds_wells"))

    op.execute(text(_create_avg_tds_view()))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_avg_tds_wells IS "
            "'Average TDS per well from major chemistry results for pygeoapi.'"
        )
    )
    op.execute(
        text("CREATE UNIQUE INDEX ux_ogc_avg_tds_wells_id " "ON ogc_avg_tds_wells (id)")
    )

    op.execute(text(_create_latest_tds_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_latest_tds_wells IS "
            "'Latest TDS per well from major chemistry results for pygeoapi.'"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_avg_tds_wells"))
    op.execute(text("DROP VIEW IF EXISTS ogc_latest_tds_wells"))
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_latest_tds_wells"))
    op.execute(text(_create_avg_tds_view_with_datetime_columns()))
    op.execute(
        text("CREATE UNIQUE INDEX ux_ogc_avg_tds_wells_id " "ON ogc_avg_tds_wells (id)")
    )
