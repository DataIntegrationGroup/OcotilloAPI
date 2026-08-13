"""rebuild the EDR water-chemistry views on the legacy NMA chemistry tables

ogc_water_chemistry (z9a0b1c2d3e4) and its internal mirror (2d3c3a268652) read
the normalized chain -- observation -> sample -> field_activity -> field_event
-> thing. Nothing populates that chain with analyte data: per
docs/chemistry-ingestion-runbook.md, the live ingestion path
(services/chemistry_lims.py, services/chemistry_drive.py, `oco water-chemistry
bulk-upload`) writes only to the legacy NMA_* tables. So the EDR collection is
advertised in /ogcapi/collections and returns an empty FeatureCollection, while
ogc_major_chemistry_results and ogc_minor_chemistry_wells -- both built on the
same legacy tables -- serve thousands of rows.

This revision repoints both EDR chemistry views at the legacy tables, at the
per-result grain EDR needs (one row per analyte measurement, not the per-well
summary the pivot views produce). Four families are unioned, all sharing the
same shape via NMA_Chemistry_SampleInfo:

    NMA_MajorChemistry       "Analyte"/"Symbol", "SampleValue", "Units"
    NMA_MinorTraceChemistry  analyte/symbol, sample_value, units
    NMA_Radionuclides        "Analyte"/"Symbol", "SampleValue", "Units"
    NMA_FieldParameters      "FieldParameter", "SampleValue", "Units"

This is interim. When chemistry lands in the normalized Sample/Observation
model, the views move back and the EDR contract does not change -- consumers
see the same collection, parameter-names, and CoverageJSON either way.

Three deliberate differences from the pivot views, each of which would
otherwise be a silent surprise:

* No thing_type filter. ogc_major_chemistry_results restricts to
  thing_type = 'water well' because it is a wells layer; this is a chemistry
  collection, so chemistry collected at a spring belongs in it. thing_type is
  carried as a column instead, so a consumer can tell a well from a spring
  rather than having the distinction silently dropped -- the EDR provider
  surfaces it on /locations features when the backing view has the column.
* Publication is gated on thing.release_status = 'public' (the convention
  f4a5b6c7d8e9 established for the legacy-backed views) AND on
  NMA_Chemistry_SampleInfo."PublicRelease" not being explicitly false. The
  pivot views ignore PublicRelease; honouring it here errs toward
  withholding, and NULL is treated as "not suppressed" so the two layers stay
  consistent on the rows that carry no opinion.
* parameter_name is the raw trimmed legacy analyte text, falling back to the
  symbol. The pivot views canonicalize analytes through long CASE blocks, but
  those cover only the subset they expose as columns. Raw text keeps every
  analyte reachable at the cost of aliases appearing as separate
  parameter-names ("Ca" and "Calcium" both surface). That is ADR3's open
  "chemistry parameter cardinality" question; canonicalizing is follow-up work
  and changes only the parameter-name vocabulary, not this plumbing.

Rows without a usable timestamp are dropped: EDR needs a time axis, and
COALESCE(analysis date, collection date) is the best available. Field
parameters carry no analysis date of their own, so they ride on the sample's
CollectionDate.

Both are MATERIALIZED views, matching ogc_major_chemistry_results and
ogc_minor_chemistry_wells. A plain view would be re-planned on every request
across a four-way UNION of the full legacy result tables, and the provider's
get_fields() runs SELECT DISTINCT parameter_name, unit at provider
construction -- a full scan per request, against tables that already hold far
more than the pivot views' per-well row counts suggest. Indexes cover the
provider's three filter columns (thing_id, datetime, parameter_name), and the
unique index on id is what allows CONCURRENTLY refreshes.

The cost is staleness: the nightly pg_cron job discovers every materialized
view from the catalog (x2y3z4a5b6c7), so these refresh with the rest, and
services/materialized_views.py lists them for `oco refresh-materialized-views`
after an ad-hoc chemistry ingestion. That is the same freshness contract the
existing chemistry layers already have.

Revision ID: d9e0f1a2b3c4
Revises: b7c8d9e0f1a2
Create Date: 2026-08-13 15:40:00.000000
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "NMA_Chemistry_SampleInfo",
    "NMA_MajorChemistry",
    "NMA_MinorTraceChemistry",
    "NMA_Radionuclides",
    "NMA_FieldParameters",
    "thing",
    "location",
    "location_thing_association",
}

PUBLIC_VIEW = "ogc_water_chemistry"
INTERNAL_VIEW = "ogc_internal_water_chemistry"

VIEW_COMMENTS = {
    PUBLIC_VIEW: (
        "Public water-chemistry analyses (by analyte) for EDR, sourced from "
        "the legacy NMA chemistry tables."
    ),
    INTERNAL_VIEW: (
        "All water-chemistry analyses (by analyte) for internal EDR, sourced "
        "from the legacy NMA chemistry tables."
    ),
}

# Same latest-location shape the other ogc_* views use (d5e6f7a8b9c0).
_LATEST_LOCATION_CTE = """
    SELECT DISTINCT ON (lta.thing_id)
        lta.thing_id,
        lta.location_id,
        lta.effective_start
    FROM location_thing_association AS lta
    WHERE lta.effective_end IS NULL
    ORDER BY lta.thing_id, lta.effective_start DESC
"""


def _result_family(
    *,
    id_prefix: str,
    table: str,
    analyte_column: str,
    value_column: str,
    unit_column: str,
    date_column: str | None,
) -> str:
    """One SELECT over a legacy chemistry table, normalized to a common shape.

    ``date_column`` is None for NMA_FieldParameters, which has no analysis
    date of its own and falls back to the sample's CollectionDate.
    """
    observed_at = (
        f'COALESCE(r.{date_column}, csi."CollectionDate")'
        if date_column
        else 'csi."CollectionDate"'
    )
    return f"""
        SELECT
            '{id_prefix}-' || r.id                  AS id,
            csi.id                                  AS sample_id,
            csi.thing_id                            AS thing_id,
            csi."PublicRelease"                     AS sample_public_release,
            {observed_at}                           AS datetime,
            r.{value_column}::double precision      AS value,
            r.{unit_column}                         AS unit,
            NULLIF(trim({analyte_column}), '')      AS parameter_name
        FROM "{table}" AS r
        JOIN "NMA_Chemistry_SampleInfo" AS csi
            ON csi.id = r.chemistry_sample_info_id
        WHERE r.{value_column} IS NOT NULL
    """


def _result_families() -> str:
    families = [
        _result_family(
            id_prefix="maj",
            table="NMA_MajorChemistry",
            analyte_column='COALESCE(r."Analyte", r."Symbol")',
            value_column='"SampleValue"',
            unit_column='"Units"',
            date_column='"AnalysisDate"',
        ),
        _result_family(
            id_prefix="min",
            table="NMA_MinorTraceChemistry",
            analyte_column="COALESCE(r.analyte, r.symbol)",
            value_column="sample_value",
            unit_column="units",
            date_column="analysis_date",
        ),
        _result_family(
            id_prefix="rad",
            table="NMA_Radionuclides",
            analyte_column='COALESCE(r."Analyte", r."Symbol")',
            value_column='"SampleValue"',
            unit_column='"Units"',
            date_column='"AnalysisDate"',
        ),
        _result_family(
            id_prefix="fld",
            table="NMA_FieldParameters",
            analyte_column='r."FieldParameter"',
            value_column='"SampleValue"',
            unit_column='"Units"',
            date_column=None,
        ),
    ]
    return "\n        UNION ALL\n".join(families)


def _create_water_chemistry_view(view_name: str, public_only: bool) -> str:
    release_filter = (
        """
          AND t.release_status = 'public'
          AND results.sample_public_release IS NOT FALSE"""
        if public_only
        else ""
    )
    return f"""
        CREATE MATERIALIZED VIEW {view_name} AS
        WITH latest_location AS (
        {_LATEST_LOCATION_CTE}
        ),
        results AS (
        {_result_families()}
        )
        SELECT
            results.id                          AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            t.thing_type                        AS thing_type,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            results.datetime                    AS datetime,
            results.value                       AS value,
            results.unit                        AS unit,
            results.parameter_name              AS parameter_name,
            results.sample_id                   AS sample_id,
            t.release_status                    AS release_status
        FROM results
        JOIN thing AS t ON t.id = results.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE results.parameter_name IS NOT NULL
          AND results.datetime IS NOT NULL{release_filter}
    """


def _load_revision_module(filename: str, module_name: str):
    path = Path(__file__).with_name(filename)
    if not path.exists():
        raise RuntimeError(
            f"Cannot restore the previous EDR chemistry views: {filename} is "
            "missing from alembic/versions."
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _drop_view_or_materialized_view(view_name: str) -> None:
    # DROP VIEW IF EXISTS only suppresses "relation does not exist" -- Postgres
    # still raises WrongObjectType if the relation is a materialized view, so
    # check the actual kind first.
    bind = op.get_bind()
    relkind = bind.execute(
        text("SELECT relkind FROM pg_class WHERE oid = to_regclass(:name)"),
        {"name": view_name},
    ).scalar()
    if relkind == "m":
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
    elif relkind == "v":
        op.execute(text(f"DROP VIEW IF EXISTS {view_name}"))


def _check_required_tables() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing
    if missing:
        raise RuntimeError(
            "Cannot rebuild the EDR water-chemistry views. Missing required "
            f"tables: {sorted(missing)}"
        )


def _create_indexes(view_name: str) -> None:
    # The unique index is what lets REFRESH MATERIALIZED VIEW CONCURRENTLY run
    # (`oco refresh-materialized-views --concurrently`); Postgres refuses
    # without one. id is unique by construction -- each family prefixes its own
    # primary key.
    op.execute(text(f"CREATE UNIQUE INDEX ux_{view_name}_id ON {view_name} (id)"))
    # The provider filters on thing_id (locations / position), datetime
    # (interval), and parameter_name (parameter-name), so each gets an index.
    op.execute(text(f"CREATE INDEX ix_{view_name}_thing_id ON {view_name} (thing_id)"))
    op.execute(text(f"CREATE INDEX ix_{view_name}_datetime ON {view_name} (datetime)"))
    op.execute(
        text(
            f"CREATE INDEX ix_{view_name}_parameter_name "
            f"ON {view_name} (parameter_name)"
        )
    )


def upgrade() -> None:
    _check_required_tables()

    for view_name, public_only in ((PUBLIC_VIEW, True), (INTERNAL_VIEW, False)):
        _drop_view_or_materialized_view(view_name)
        op.execute(text(_create_water_chemistry_view(view_name, public_only)))
        _create_indexes(view_name)
        op.execute(
            text(
                f"COMMENT ON MATERIALIZED VIEW {view_name} IS "
                f"'{VIEW_COMMENTS[view_name]}'"
            )
        )


def downgrade() -> None:
    # Restore the normalized-model definitions from the revisions that own
    # them, rather than a copy that could drift from those files.
    edr = _load_revision_module(
        "z9a0b1c2d3e4_add_edr_water_views.py", "_edr_water_views"
    )
    internal = _load_revision_module(
        "2d3c3a268652_create_internal_ogc_views.py", "_internal_ogc_views"
    )

    _drop_view_or_materialized_view(PUBLIC_VIEW)
    op.execute(text(edr._create_water_chemistry_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_water_chemistry IS "
            "'Public water-chemistry analyses (by analyte) for EDR.'"
        )
    )

    _drop_view_or_materialized_view(INTERNAL_VIEW)
    op.execute(text(internal._create_internal_water_chemistry_view()))
