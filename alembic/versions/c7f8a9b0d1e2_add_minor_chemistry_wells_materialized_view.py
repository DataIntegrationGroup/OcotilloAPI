"""add minor chemistry wells materialized view

Revision ID: c7f8a9b0d1e2
Revises: b6f7a8b9c0d1
Create Date: 2026-03-04 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "c7f8a9b0d1e2"
down_revision: Union[str, Sequence[str], None] = "b6f7a8b9c0d1"
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

STATIC_ANALYTE_COLUMNS: list[tuple[str, str]] = [
    ("h2r", "h2r"),
    ("o18r", "o18r"),
    ("c13r", "c13r"),
    ("c14", "c14"),
    ("c14_years", "c14_years"),
    ("fluoride", "fluoride"),
    ("barium", "barium"),
    ("barium_total", "barium_total"),
    ("copper", "copper"),
    ("copper_total", "copper_total"),
    ("zinc", "zinc"),
    ("zinc_total", "zinc_total"),
    ("molybdenum", "molybdenum"),
    ("molybdenum_total", "molybdenum_total"),
    ("silica", "silica"),
    ("silicon", "silicon"),
    ("silicon_total", "silicon_total"),
    ("manganese", "manganese"),
    ("manganese_total", "manganese_total"),
    ("iron", "iron"),
    ("iron_total", "iron_total"),
    ("strontium", "strontium"),
    ("strontium_total", "strontium_total"),
    ("chromium", "chromium"),
    ("chromium_total", "chromium_total"),
    ("boron", "boron"),
    ("boron_total", "boron_total"),
    ("uranium", "uranium"),
    ("uranium_total", "uranium_total"),
    ("lithium", "lithium"),
    ("lithium_total", "lithium_total"),
    ("silver", "silver"),
    ("silver_total", "silver_total"),
    ("antimony", "antimony"),
    ("antimony_total", "antimony_total"),
    ("beryllium", "beryllium"),
    ("beryllium_total", "beryllium_total"),
    ("lead", "lead"),
    ("lead_total", "lead_total"),
    ("thallium", "thallium"),
    ("thallium_total", "thallium_total"),
    ("bromide", "bromide"),
    ("selenium", "selenium"),
    ("selenium_total", "selenium_total"),
    ("vanadium", "vanadium"),
    ("vanadium_total", "vanadium_total"),
    ("aluminum", "aluminum"),
    ("aluminum_total", "aluminum_total"),
    ("arsenic", "arsenic"),
    ("arsenic_total", "arsenic_total"),
    ("nickel", "nickel"),
    ("nickel_total", "nickel_total"),
    ("cadmium", "cadmium"),
    ("cadmium_total", "cadmium_total"),
    ("cobalt", "cobalt"),
    ("cobalt_total", "cobalt_total"),
    ("phosphate", "phosphate"),
    ("nitrite", "nitrite"),
    ("nitrate", "nitrate"),
    ("nitrate_as_n", "nitrate_as_n"),
    ("thorium", "thorium"),
    ("thorium_total", "thorium_total"),
    ("tin", "tin"),
    ("tin_total", "tin_total"),
    ("mercury", "mercury"),
    ("mercury_total", "mercury_total"),
    ("titanium", "titanium"),
    ("titanium_total", "titanium_total"),
]


def _static_analyte_value_columns() -> str:
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


def _create_minor_chemistry_wells_view() -> str:
    value_columns = _static_analyte_value_columns()
    unit_columns = _static_analyte_unit_columns()

    return f"""
        CREATE MATERIALIZED VIEW ogc_minor_chemistry_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        chemistry_rows AS (
            SELECT
                csi.thing_id,
                mtc.id AS result_id,
                COALESCE(mtc.analysis_date::timestamp, csi."CollectionDate") AS observation_datetime,
                trim(mtc.analyte) AS analyte_name,
                trim(mtc.symbol) AS symbol_name,
                mtc.sample_value::double precision AS sample_value,
                mtc.units AS units
            FROM "NMA_MinorTraceChemistry" AS mtc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mtc.chemistry_sample_info_id
            JOIN thing AS t ON t.id = csi.thing_id
            WHERE
                mtc.sample_value IS NOT NULL
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
                    WHEN coalesce(nr.analyte_token, '') = 'h2r' THEN 'h2r'
                    WHEN coalesce(nr.analyte_token, '') = 'o18r' THEN 'o18r'
                    WHEN coalesce(nr.analyte_token, '') = 'c13r' THEN 'c13r'
                    WHEN coalesce(nr.analyte_token, '') = 'c14' THEN 'c14'
                    WHEN coalesce(nr.analyte_token, '') = 'c14years' THEN 'c14_years'

                    WHEN coalesce(nr.analyte_token, '') = 'f' THEN 'fluoride'
                    WHEN coalesce(nr.analyte_token, '') = 'ba' THEN 'barium'
                    WHEN coalesce(nr.analyte_token, '') = 'batotal' THEN 'barium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'cu' THEN 'copper'
                    WHEN coalesce(nr.analyte_token, '') = 'cutotal' THEN 'copper_total'
                    WHEN coalesce(nr.analyte_token, '') = 'zn' THEN 'zinc'
                    WHEN coalesce(nr.analyte_token, '') = 'zntotal' THEN 'zinc_total'
                    WHEN coalesce(nr.analyte_token, '') = 'mo' THEN 'molybdenum'
                    WHEN coalesce(nr.analyte_token, '') = 'mototal' THEN 'molybdenum_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sio2' THEN 'silica'
                    WHEN coalesce(nr.analyte_token, '') = 'si' THEN 'silicon'
                    WHEN coalesce(nr.analyte_token, '') = 'sitotal' THEN 'silicon_total'
                    WHEN coalesce(nr.analyte_token, '') = 'mn' THEN 'manganese'
                    WHEN coalesce(nr.analyte_token, '') = 'mntotal' THEN 'manganese_total'
                    WHEN coalesce(nr.analyte_token, '') = 'fe' THEN 'iron'
                    WHEN coalesce(nr.analyte_token, '') = 'fetotal' THEN 'iron_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sr' THEN 'strontium'
                    WHEN coalesce(nr.analyte_token, '') = 'srtotal' THEN 'strontium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'cr' THEN 'chromium'
                    WHEN coalesce(nr.analyte_token, '') = 'crtotal' THEN 'chromium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'b' THEN 'boron'
                    WHEN coalesce(nr.analyte_token, '') = 'btotal' THEN 'boron_total'
                    WHEN coalesce(nr.analyte_token, '') = 'u' THEN 'uranium'
                    WHEN coalesce(nr.analyte_token, '') = 'utotal' THEN 'uranium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'li' THEN 'lithium'
                    WHEN coalesce(nr.analyte_token, '') = 'litotal' THEN 'lithium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'ag' THEN 'silver'
                    WHEN coalesce(nr.analyte_token, '') = 'agtotal' THEN 'silver_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sb' THEN 'antimony'
                    WHEN coalesce(nr.analyte_token, '') = 'sbtotal' THEN 'antimony_total'
                    WHEN coalesce(nr.analyte_token, '') = 'be' THEN 'beryllium'
                    WHEN coalesce(nr.analyte_token, '') = 'betotal' THEN 'beryllium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'pb' THEN 'lead'
                    WHEN coalesce(nr.analyte_token, '') = 'pbtotal' THEN 'lead_total'
                    WHEN coalesce(nr.analyte_token, '') = 'tl' THEN 'thallium'
                    WHEN coalesce(nr.analyte_token, '') = 'tltotal' THEN 'thallium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'br' THEN 'bromide'
                    WHEN coalesce(nr.analyte_token, '') = 'se' THEN 'selenium'
                    WHEN coalesce(nr.analyte_token, '') = 'setotal' THEN 'selenium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'v' THEN 'vanadium'
                    WHEN coalesce(nr.analyte_token, '') = 'vtotal' THEN 'vanadium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'al' THEN 'aluminum'
                    WHEN coalesce(nr.analyte_token, '') = 'altotal' THEN 'aluminum_total'
                    WHEN coalesce(nr.analyte_token, '') = 'as' THEN 'arsenic'
                    WHEN coalesce(nr.analyte_token, '') = 'astotal' THEN 'arsenic_total'
                    WHEN coalesce(nr.analyte_token, '') = 'ni' THEN 'nickel'
                    WHEN coalesce(nr.analyte_token, '') = 'nitotal' THEN 'nickel_total'
                    WHEN coalesce(nr.analyte_token, '') = 'cd' THEN 'cadmium'
                    WHEN coalesce(nr.analyte_token, '') = 'cdtotal' THEN 'cadmium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'co' THEN 'cobalt'
                    WHEN coalesce(nr.analyte_token, '') = 'cototal' THEN 'cobalt_total'
                    WHEN coalesce(nr.analyte_token, '') = 'po4' THEN 'phosphate'
                    WHEN coalesce(nr.analyte_token, '') = 'no2' THEN 'nitrite'
                    WHEN coalesce(nr.analyte_token, '') = 'no3' THEN 'nitrate'
                    WHEN coalesce(nr.analyte_token, '') = 'no3n' THEN 'nitrate_as_n'
                    WHEN coalesce(nr.analyte_token, '') = 'th' THEN 'thorium'
                    WHEN coalesce(nr.analyte_token, '') = 'thtotal' THEN 'thorium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sn' THEN 'tin'
                    WHEN coalesce(nr.analyte_token, '') = 'sntotal' THEN 'tin_total'
                    WHEN coalesce(nr.analyte_token, '') = 'hg' THEN 'mercury'
                    WHEN coalesce(nr.analyte_token, '') = 'hgtotal' THEN 'mercury_total'
                    WHEN coalesce(nr.analyte_token, '') = 'ti' THEN 'titanium'
                    WHEN coalesce(nr.analyte_token, '') = 'titotal' THEN 'titanium_total'
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
{value_columns},
{unit_columns},
            l.point
        FROM latest_results AS lr
        JOIN thing AS t ON t.id = lr.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE lr.rn = 1
          AND t.thing_type = 'water well'
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
        "NMA_MinorTraceChemistry",
    }

    if not required_tables.issubset(existing_tables):
        missing = sorted(t for t in required_tables if t not in existing_tables)
        raise RuntimeError(
            "Cannot create ogc_minor_chemistry_wells. Missing required tables: "
            + ", ".join(missing)
        )

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_minor_chemistry_wells"))
    op.execute(text(_create_minor_chemistry_wells_view()))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_minor_chemistry_wells IS "
            "'Latest minor/trace chemistry analyte values for water wells, pivoted into static analyte columns.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_minor_chemistry_wells_id "
            "ON ogc_minor_chemistry_wells (id)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_minor_chemistry_wells"))
