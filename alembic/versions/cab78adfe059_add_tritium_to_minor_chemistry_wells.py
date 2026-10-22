"""add tritium to the minor chemistry well layers

The isotope results ingest (services/chemistry_isotopes.py) loads tritium
into NMA_MinorTraceChemistry as analyte `3H`, in TU, and the legacy table
already held about 660 such rows. ogc_minor_chemistry_wells and its internal
twin had columns for H2r, O18r, C13r, C14 and C14 age but none for tritium,
so it was reachable through /chemistry/results and missing from the map
layers.

This revision adds `tritium` and `tritium_units`. The view normalizes
analyte names to lowercase alphanumerics, so `3H` arrives as the token `3h`.
A column name can't start with a digit, so the column takes the analyte's
name, as fluoride and barium do, rather than its code.

Everything else is carried over unchanged from f4a5b6c7d8e9 (public) and
2d3c3a268652 (internal): the latest value per well and analyte, the
release_status filter on the public view, the comments and the unique id
index. One builder now serves both views, so the public and internal
definitions can't drift apart in this revision. The analyte column list is
now a plain list of names rather than the earlier identical (key, column)
pairs; the SQL it generates is the same.

Both are materialized views, so they are dropped and rebuilt, which also
populates them. The downgrade rebuilds them from the two earlier revision
files rather than from a copy here.

Revision ID: cab78adfe059
Revises: a3b4c5d6e7f8
Create Date: 2026-10-19 12:00:00.000000
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "cab78adfe059"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLIC_VIEW = "ogc_minor_chemistry_wells"
INTERNAL_VIEW = "ogc_internal_minor_chemistry_wells"

# Same comments f4a5b6c7d8e9 and 2d3c3a268652 set.
VIEW_COMMENTS = {
    PUBLIC_VIEW: (
        "Latest minor/trace chemistry analyte values for water wells, "
        "pivoted into static analyte columns."
    ),
    INTERNAL_VIEW: (
        "Unfiltered latest minor/trace chemistry analyte values for water "
        "wells, pivoted into static analyte columns, for the internal "
        "pygeoapi mount."
    ),
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

# The mapped_rows CASE already turns each analyte token into its column name,
# so one string serves as both the analyte_key filter and the column name. The
# earlier revisions carried it as an identical (key, column) pair.
STATIC_ANALYTE_COLUMNS_MINOR: list[str] = [
    "h2r",
    "o18r",
    "c13r",
    "c14",
    "c14_years",
    "tritium",
    "fluoride",
    "barium",
    "barium_total",
    "copper",
    "copper_total",
    "zinc",
    "zinc_total",
    "molybdenum",
    "molybdenum_total",
    "silica",
    "silicon",
    "silicon_total",
    "manganese",
    "manganese_total",
    "iron",
    "iron_total",
    "strontium",
    "strontium_total",
    "chromium",
    "chromium_total",
    "boron",
    "boron_total",
    "uranium",
    "uranium_total",
    "lithium",
    "lithium_total",
    "silver",
    "silver_total",
    "antimony",
    "antimony_total",
    "beryllium",
    "beryllium_total",
    "lead",
    "lead_total",
    "thallium",
    "thallium_total",
    "bromide",
    "selenium",
    "selenium_total",
    "vanadium",
    "vanadium_total",
    "aluminum",
    "aluminum_total",
    "arsenic",
    "arsenic_total",
    "nickel",
    "nickel_total",
    "cadmium",
    "cadmium_total",
    "cobalt",
    "cobalt_total",
    "phosphate",
    "nitrite",
    "nitrate",
    "nitrate_as_n",
    "thorium",
    "thorium_total",
    "tin",
    "tin_total",
    "mercury",
    "mercury_total",
    "titanium",
    "titanium_total",
]


def _minor_chemistry_value_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.sample_value) FILTER "
                f"(WHERE lr.analyte_key = '{column}') AS {column}"
            )
            for column in STATIC_ANALYTE_COLUMNS_MINOR
        ]
    )


def _minor_chemistry_unit_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.units) FILTER "
                f"(WHERE lr.analyte_key = '{column}') AS {column}_units"
            )
            for column in STATIC_ANALYTE_COLUMNS_MINOR
        ]
    )


def _create_minor_chemistry_wells_view(view_name: str, public_only: bool) -> str:
    value_columns = _minor_chemistry_value_columns()
    unit_columns = _minor_chemistry_unit_columns()
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW {view_name} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        chemistry_rows AS (
            SELECT
                csi.thing_id,
                mtc.id AS result_id,
                COALESCE(mtc.analysis_date::timestamp, csi."CollectionDate") AS observation_datetime,
                trim(mtc.analyte) AS analyte_name,
                mtc.sample_value::double precision AS sample_value,
                mtc.units AS units
            FROM "NMA_MinorTraceChemistry" AS mtc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mtc.chemistry_sample_info_id
            JOIN thing AS t ON t.id = csi.thing_id
            WHERE
                mtc.sample_value IS NOT NULL
                AND t.thing_type = 'water well'{release_filter}
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
                    WHEN coalesce(nr.analyte_token, '') = '3h' THEN 'tritium'

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


def _rebuild(create_public, create_internal) -> None:
    for view_name, create in (
        (PUBLIC_VIEW, create_public),
        (INTERNAL_VIEW, create_internal),
    ):
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
        op.execute(text(create()))
        op.execute(
            text(
                f"COMMENT ON MATERIALIZED VIEW {view_name} IS "
                f"'{VIEW_COMMENTS[view_name]}'"
            )
        )
        # Unique id index: required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
        op.execute(text(f"CREATE UNIQUE INDEX ux_{view_name}_id ON {view_name} (id)"))


def _load_revision_module(filename: str, module_name: str):
    # Restore the earlier definitions from their own files rather than a copy
    # here that could drift from them.
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade() -> None:
    _rebuild(
        lambda: _create_minor_chemistry_wells_view(PUBLIC_VIEW, public_only=True),
        lambda: _create_minor_chemistry_wells_view(INTERNAL_VIEW, public_only=False),
    )


def downgrade() -> None:
    public = _load_revision_module(
        "f4a5b6c7d8e9_apply_public_release_status_filter_to_ogc_views.py",
        "_ogc_public_views",
    )
    internal = _load_revision_module(
        "2d3c3a268652_create_internal_ogc_views.py",
        "_ogc_internal_views",
    )
    _rebuild(
        lambda: public._create_minor_chemistry_wells_view(public_only=True),
        lambda: internal._create_minor_chemistry_wells_view(public_only=False),
    )
