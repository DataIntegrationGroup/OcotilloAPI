"""add normalized chemistry results materialized view

Revision ID: b6f7a8b9c0d1
Revises: l5e6f7a8b9c0
Create Date: 2026-03-04 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "b6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "l5e6f7a8b9c0"
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

# Static analyte columns for major chemistry pivots.
# Includes aliases observed in current DB values (e.g., Ca(total), IONBAL, TAn, TCat, Na+K).
STATIC_ANALYTE_COLUMNS: list[tuple[str, str]] = [
    ("tds", "tds"),
    ("calcium", "calcium"),
    ("calcium_total", "calcium_total"),
    ("magnesium", "magnesium"),
    ("magnesium_total", "magnesium_total"),
    ("sodium", "sodium"),
    ("sodium_total", "sodium_total"),
    ("potassium", "potassium"),
    ("potassium_total", "potassium_total"),
    ("sodium_plus_potassium", "sodium_plus_potassium"),
    ("bicarbonate", "bicarbonate"),
    ("carbonate", "carbonate"),
    ("sulfate", "sulfate"),
    ("chloride", "chloride"),
    ("ion_balance", "ion_balance"),
    ("total_anions", "total_anions"),
    ("total_cations", "total_cations"),
    ("alkalinity", "alkalinity"),
    ("hardness", "hardness"),
    ("specific_conductance", "specific_conductance"),
    ("ph", "ph"),
    ("nitrate", "nitrate"),
    ("fluoride", "fluoride"),
    ("silica", "silica"),
]


def _static_analyte_select_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.sample_value) FILTER "
                f"(WHERE lr.analyte_key = '{analyte_key}') AS {column_name}"
            )
            for analyte_key, column_name in STATIC_ANALYTE_COLUMNS
        ]
    )


def _static_analyte_unit_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.units) FILTER "
                f"(WHERE lr.analyte_key = '{analyte_key}') AS {column_name}_units"
            )
            for analyte_key, column_name in STATIC_ANALYTE_COLUMNS
        ]
    )


def _create_major_chemistry_results_view() -> str:
    static_columns = _static_analyte_select_columns()
    static_unit_columns = _static_analyte_unit_columns()
    return f"""
        CREATE MATERIALIZED VIEW ogc_major_chemistry_results AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        chemistry_rows AS (
            SELECT
                csi.thing_id,
                mc.id AS result_id,
                COALESCE(mc."AnalysisDate", csi."CollectionDate") AS observation_datetime,
                trim(mc."Analyte") AS analyte_name,
                trim(mc."Symbol") AS symbol_name,
                mc."SampleValue"::double precision AS sample_value,
                mc."Units" AS units
            FROM "NMA_MajorChemistry" AS mc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mc.chemistry_sample_info_id
            JOIN thing AS t
                ON t.id = csi.thing_id
            WHERE mc."SampleValue" IS NOT NULL
              AND t.thing_type = 'water well'
        ),
        normalized_rows AS (
            SELECT
                cr.thing_id,
                cr.result_id,
                cr.observation_datetime,
                NULLIF(
                    regexp_replace(
                        lower(trim(coalesce(cr.analyte_name, ''))),
                        '[^a-z0-9]+',
                        '',
                        'g'
                    ),
                    ''
                ) AS analyte_token,
                NULLIF(
                    regexp_replace(
                        lower(trim(coalesce(cr.symbol_name, ''))),
                        '[^a-z0-9]+',
                        '',
                        'g'
                    ),
                    ''
                ) AS symbol_token,
                cr.sample_value,
                cr.units
            FROM chemistry_rows AS cr
        ),
        mapped_rows AS (
            SELECT
                nr.thing_id,
                nr.result_id,
                nr.observation_datetime,
                CASE
                    WHEN coalesce(nr.symbol_token, '') = 'tds'
                        OR coalesce(nr.analyte_token, '') IN ('tds', 'totaldissolvedsolids')
                        THEN 'tds'

                    WHEN coalesce(nr.symbol_token, '') = 'ca'
                        OR coalesce(nr.analyte_token, '') = 'ca'
                        THEN 'calcium'
                    WHEN coalesce(nr.analyte_token, '') = 'catotal'
                        THEN 'calcium_total'

                    WHEN coalesce(nr.symbol_token, '') = 'mg'
                        OR coalesce(nr.analyte_token, '') = 'mg'
                        THEN 'magnesium'
                    WHEN coalesce(nr.analyte_token, '') = 'mgtotal'
                        THEN 'magnesium_total'

                    WHEN coalesce(nr.symbol_token, '') = 'na'
                        OR coalesce(nr.analyte_token, '') = 'na'
                        THEN 'sodium'
                    WHEN coalesce(nr.analyte_token, '') = 'natotal'
                        THEN 'sodium_total'

                    WHEN coalesce(nr.symbol_token, '') = 'k'
                        OR coalesce(nr.analyte_token, '') = 'k'
                        THEN 'potassium'
                    WHEN coalesce(nr.analyte_token, '') = 'ktotal'
                        THEN 'potassium_total'

                    WHEN coalesce(nr.analyte_token, '') = 'nak'
                        THEN 'sodium_plus_potassium'

                    WHEN coalesce(nr.symbol_token, '') = 'hco3'
                        OR coalesce(nr.analyte_token, '') = 'hco3'
                        THEN 'bicarbonate'
                    WHEN coalesce(nr.symbol_token, '') = 'co3'
                        OR coalesce(nr.analyte_token, '') = 'co3'
                        THEN 'carbonate'
                    WHEN coalesce(nr.symbol_token, '') = 'so4'
                        OR coalesce(nr.analyte_token, '') = 'so4'
                        THEN 'sulfate'
                    WHEN coalesce(nr.symbol_token, '') = 'cl'
                        OR coalesce(nr.analyte_token, '') = 'cl'
                        THEN 'chloride'

                    WHEN coalesce(nr.analyte_token, '') = 'ionbal'
                        THEN 'ion_balance'
                    WHEN coalesce(nr.analyte_token, '') = 'tan'
                        THEN 'total_anions'
                    WHEN coalesce(nr.analyte_token, '') = 'tcat'
                        THEN 'total_cations'

                    WHEN coalesce(nr.analyte_token, '') IN ('alk', 'alkalinity')
                        THEN 'alkalinity'
                    WHEN coalesce(nr.analyte_token, '') IN ('hrd', 'hardness')
                        THEN 'hardness'
                    WHEN coalesce(nr.analyte_token, '') IN (
                        'condlab',
                        'specificconductance',
                        'specificconductivity',
                        'conductivity'
                    )
                        THEN 'specific_conductance'
                    WHEN coalesce(nr.symbol_token, '') = 'ph'
                        OR coalesce(nr.analyte_token, '') IN ('ph', 'phl')
                        THEN 'ph'

                    WHEN coalesce(nr.symbol_token, '') = 'no3'
                        OR coalesce(nr.analyte_token, '') IN ('no3', 'nitrate')
                        THEN 'nitrate'
                    WHEN coalesce(nr.symbol_token, '') = 'f'
                        OR coalesce(nr.analyte_token, '') IN ('f', 'fluoride')
                        THEN 'fluoride'
                    WHEN coalesce(nr.symbol_token, '') = 'sio2'
                        OR coalesce(nr.analyte_token, '') IN ('sio2', 'silica')
                        THEN 'silica'

                    ELSE NULL
                END AS analyte_key,
                nr.sample_value,
                nr.units
            FROM normalized_rows AS nr
        ),
        latest_results AS (
            SELECT
                mr.thing_id,
                mr.analyte_key,
                mr.sample_value,
                mr.units,
                mr.observation_datetime,
                ROW_NUMBER() OVER (
                    PARTITION BY mr.thing_id, mr.analyte_key
                    ORDER BY mr.observation_datetime DESC NULLS LAST, mr.result_id DESC
                ) AS rn
            FROM mapped_rows AS mr
            WHERE mr.analyte_key IS NOT NULL
        )
        SELECT
            t.id AS id,
            ll.location_id,
            t.name,
            t.thing_type,
            COUNT(*)::integer AS analyte_count,
            MAX(lr.observation_datetime::date) AS latest_chemistry_date,
{static_columns},
{static_unit_columns},
            l.point
        FROM latest_results AS lr
        JOIN thing AS t ON t.id = lr.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE lr.rn = 1
        GROUP BY t.id, ll.location_id, t.name, t.thing_type, l.point
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    required_tables = {
        "thing",
        "location",
        "location_thing_association",
        "NMA_Chemistry_SampleInfo",
        "NMA_MajorChemistry",
    }

    if not required_tables.issubset(existing_tables):
        missing = sorted(t for t in required_tables if t not in existing_tables)
        raise RuntimeError(
            "Cannot create ogc_major_chemistry_results. Missing required tables: "
            + ", ".join(missing)
        )

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_major_chemistry_results"))
    op.execute(
        text("DROP MATERIALIZED VIEW IF EXISTS ogc_normalized_chemistry_results")
    )
    op.execute(text(_create_major_chemistry_results_view()))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_major_chemistry_results IS "
            "'Latest major-chemistry analyte values per location, pivoted into static analyte columns.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_major_chemistry_results_id "
            "ON ogc_major_chemistry_results (id)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_major_chemistry_results"))
    op.execute(
        text("DROP MATERIALIZED VIEW IF EXISTS ogc_normalized_chemistry_results")
    )
