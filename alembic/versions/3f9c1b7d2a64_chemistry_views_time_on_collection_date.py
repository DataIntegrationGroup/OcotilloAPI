"""key the water-chemistry views on when the water was collected

d9e0f1a2b3c4 gave every lab result the time COALESCE(analysis date, collection
date). A lab rarely runs a whole sample on one day -- anions one day, cations
another, trace metals a month later -- so one trip to a well came out as
several points in time. AR-0102 was sampled once in 2019, on Apr 09; its 87
results carried eight different dates between Apr 09 and May 24. Every
consumer of the view inherited that:

* the EDR water_chemistry collection served one sample as eight time steps;
* GET /chemistry/results filtered its start_time/end_time window on analysis
  date, so a sample collected in December and analysed in January was filed
  under the wrong year, and could be split across two;
* the owner-facing chemistry report counted "8 samples" for 2019 and printed
  "arsenic, measured May 24" for water drawn on Apr 09.

This revision flips the precedence: `datetime` is the sample's
CollectionDate, falling back to the analysis date only where no collection
date was recorded (previously the fallback ran the other way). Field
parameters are unchanged -- they only ever had the collection date.

The analysis date is not thrown away. It is carried as its own
`analysis_date` column (NULL for field parameters, which have none), so a
consumer that wants lab turnaround can still read it without it standing in
for the time of sampling.

Everything else -- the four-table union, release gating, id scheme,
indexes, comments -- is carried over from d9e0f1a2b3c4 unchanged. Both views
are materialized, so they are dropped and rebuilt; the rebuild populates
them, and the nightly pg_cron refresh (x2y3z4a5b6c7) discovers them from the
catalog as before.

Revision ID: 3f9c1b7d2a64
Revises: e7f8a9b0c1d2
Create Date: 2026-09-10 11:00:00.000000
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "3f9c1b7d2a64"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLIC_VIEW = "ogc_water_chemistry"
INTERNAL_VIEW = "ogc_internal_water_chemistry"

VIEW_COMMENTS = {
    PUBLIC_VIEW: (
        "Public water-chemistry analyses (by analyte) for EDR, sourced from "
        "the legacy NMA chemistry tables. datetime is the sample collection "
        "date; analysis_date is when the lab ran the result."
    ),
    INTERNAL_VIEW: (
        "All water-chemistry analyses (by analyte) for internal EDR, sourced "
        "from the legacy NMA chemistry tables. datetime is the sample "
        "collection date; analysis_date is when the lab ran the result."
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

    ``date_column`` is the table's analysis date, or None for
    NMA_FieldParameters, which has none.
    """
    if date_column:
        observed_at = f'COALESCE(csi."CollectionDate", r.{date_column})'
        analysis_date = f"r.{date_column}::timestamp"
    else:
        observed_at = 'csi."CollectionDate"'
        analysis_date = "NULL::timestamp"

    return f"""
        SELECT
            '{id_prefix}-' || r.id                  AS id,
            csi.id                                  AS sample_id,
            csi.thing_id                            AS thing_id,
            csi."PublicRelease"                     AS sample_public_release,
            {observed_at}                           AS datetime,
            {analysis_date}                         AS analysis_date,
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
            results.analysis_date               AS analysis_date,
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


def _create_indexes(view_name: str) -> None:
    # Unique id index: required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
    op.execute(text(f"CREATE UNIQUE INDEX ux_{view_name}_id ON {view_name} (id)"))
    op.execute(text(f"CREATE INDEX ix_{view_name}_thing_id ON {view_name} (thing_id)"))
    op.execute(text(f"CREATE INDEX ix_{view_name}_datetime ON {view_name} (datetime)"))
    op.execute(
        text(
            f"CREATE INDEX ix_{view_name}_parameter_name "
            f"ON {view_name} (parameter_name)"
        )
    )


def _rebuild(create_view, create_indexes, comments) -> None:
    for view_name, public_only in ((PUBLIC_VIEW, True), (INTERNAL_VIEW, False)):
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
        op.execute(text(create_view(view_name, public_only)))
        create_indexes(view_name)
        op.execute(
            text(
                f"COMMENT ON MATERIALIZED VIEW {view_name} IS "
                f"'{comments[view_name]}'"
            )
        )


def _load_previous_revision():
    # Restore d9e0f1a2b3c4's definitions from that file rather than a copy
    # here that could drift from it.
    path = Path(__file__).with_name(
        "d9e0f1a2b3c4_edr_water_chemistry_from_legacy_tables.py"
    )
    spec = importlib.util.spec_from_file_location("_edr_chemistry_legacy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade() -> None:
    _rebuild(_create_water_chemistry_view, _create_indexes, VIEW_COMMENTS)


def downgrade() -> None:
    previous = _load_previous_revision()
    _rebuild(
        previous._create_water_chemistry_view,
        previous._create_indexes,
        previous.VIEW_COMMENTS,
    )
