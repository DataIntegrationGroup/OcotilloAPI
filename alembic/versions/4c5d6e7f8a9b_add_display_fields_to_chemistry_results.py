"""add display fields to chemistry results views

The REST /chemistry/results endpoint reads ogc_water_chemistry. The well
details display reads the same legacy tables directly and exposes extra
per-result metadata used for standards comparisons and UI grouping. This
revision carries that raw metadata through the public and internal chemistry
materialized views so /chemistry/results can add the same per-row display
fields without changing its existing paginated shape.

Revision ID: 4c5d6e7f8a9b
Revises: 3f9c1b7d2a64
Create Date: 2026-09-18 12:00:00.000000
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "4c5d6e7f8a9b"
down_revision: Union[str, Sequence[str], None] = "3f9c1b7d2a64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLIC_VIEW = "ogc_water_chemistry"
INTERNAL_VIEW = "ogc_internal_water_chemistry"

VIEW_COMMENTS = {
    PUBLIC_VIEW: (
        "Public water-chemistry analyses (by analyte) for EDR, sourced from "
        "the legacy NMA chemistry tables. datetime is the sample collection "
        "date; analysis_date is when the lab ran the result. Extra legacy "
        "result fields support /chemistry/results display metadata."
    ),
    INTERNAL_VIEW: (
        "All water-chemistry analyses (by analyte) for internal EDR, sourced "
        "from the legacy NMA chemistry tables. datetime is the sample "
        "collection date; analysis_date is when the lab ran the result. "
        "Extra legacy result fields support /chemistry/results display "
        "metadata."
    ),
}

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
    source: str,
    table: str,
    parameter_name_column: str,
    analyte_column: str,
    symbol_column: str | None,
    value_column: str,
    unit_column: str,
    uncertainty_column: str | None,
    analysis_method_column: str | None,
    date_column: str | None,
    notes_column: str | None,
    analyses_agency_column: str | None,
) -> str:
    """One SELECT over a legacy chemistry table, normalized to one shape."""
    if date_column:
        observed_at = f'COALESCE(csi."CollectionDate", r.{date_column})'
        analysis_date = f"r.{date_column}::timestamp"
    else:
        observed_at = 'csi."CollectionDate"'
        analysis_date = "NULL::timestamp"

    symbol = "NULL::text"
    if symbol_column:
        symbol = f"NULLIF(trim({symbol_column}), '')"
    analyte = f"NULLIF(trim({analyte_column}), '')"
    uncertainty = (
        f"r.{uncertainty_column}::double precision"
        if uncertainty_column
        else "NULL::double precision"
    )
    analysis_method = "NULL::text"
    if analysis_method_column:
        analysis_method = f"r.{analysis_method_column}"
    notes = f"r.{notes_column}" if notes_column else "NULL::text"
    analyses_agency = "NULL::text"
    if analyses_agency_column:
        analyses_agency = f"r.{analyses_agency_column}"

    return f"""
        SELECT
            '{id_prefix}-' || r.id                  AS id,
            '{source}'                              AS source,
            csi.id                                  AS sample_id,
            csi.thing_id                            AS thing_id,
            csi."PublicRelease"                     AS sample_public_release,
            {observed_at}                           AS datetime,
            {analysis_date}                         AS analysis_date,
            r.{value_column}::double precision      AS value,
            r.{unit_column}                         AS unit,
            NULLIF(trim({parameter_name_column}), '') AS parameter_name,
            {analyte}                              AS analyte,
            {symbol}                                AS symbol,
            {uncertainty}                           AS uncertainty,
            {analysis_method}                       AS analysis_method,
            {notes}                                 AS notes,
            {analyses_agency}                       AS analyses_agency
        FROM "{table}" AS r
        JOIN "NMA_Chemistry_SampleInfo" AS csi
            ON csi.id = r.chemistry_sample_info_id
        WHERE r.{value_column} IS NOT NULL
    """


def _result_families() -> str:
    families = [
        _result_family(
            id_prefix="maj",
            source="major",
            table="NMA_MajorChemistry",
            parameter_name_column='COALESCE(r."Analyte", r."Symbol")',
            analyte_column='r."Analyte"',
            symbol_column='r."Symbol"',
            value_column='"SampleValue"',
            unit_column='"Units"',
            uncertainty_column='"Uncertainty"',
            analysis_method_column='"AnalysisMethod"',
            date_column='"AnalysisDate"',
            notes_column='"Notes"',
            analyses_agency_column='"AnalysesAgency"',
        ),
        _result_family(
            id_prefix="min",
            source="minor",
            table="NMA_MinorTraceChemistry",
            parameter_name_column="COALESCE(r.analyte, r.symbol)",
            analyte_column="r.analyte",
            symbol_column="r.symbol",
            value_column="sample_value",
            unit_column="units",
            uncertainty_column="uncertainty",
            analysis_method_column="analysis_method",
            date_column="analysis_date",
            notes_column="notes",
            analyses_agency_column="analyses_agency",
        ),
        _result_family(
            id_prefix="rad",
            source="radionuclide",
            table="NMA_Radionuclides",
            parameter_name_column='COALESCE(r."Analyte", r."Symbol")',
            analyte_column='r."Analyte"',
            symbol_column='r."Symbol"',
            value_column='"SampleValue"',
            unit_column='"Units"',
            uncertainty_column='"Uncertainty"',
            analysis_method_column='"AnalysisMethod"',
            date_column='"AnalysisDate"',
            notes_column='"Notes"',
            analyses_agency_column='"AnalysesAgency"',
        ),
        _result_family(
            id_prefix="fld",
            source="field",
            table="NMA_FieldParameters",
            parameter_name_column='r."FieldParameter"',
            analyte_column='r."FieldParameter"',
            symbol_column='r."FieldParameter"',
            value_column='"SampleValue"',
            unit_column='"Units"',
            uncertainty_column=None,
            analysis_method_column=None,
            date_column=None,
            notes_column='"Notes"',
            analyses_agency_column='"AnalysesAgency"',
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
            results.source                      AS source,
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
            results.analyte                     AS analyte,
            results.symbol                      AS symbol,
            results.uncertainty                 AS uncertainty,
            results.analysis_method             AS analysis_method,
            results.notes                       AS notes,
            results.analyses_agency             AS analyses_agency,
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
    unique_id = f"CREATE UNIQUE INDEX ux_{view_name}_id ON {view_name} (id)"
    thing_id = (
        f"CREATE INDEX ix_{view_name}_thing_id ON {view_name} (thing_id)"  # noqa: E501
    )
    observed_at = (
        f"CREATE INDEX ix_{view_name}_datetime ON {view_name} (datetime)"  # noqa: E501
    )
    op.execute(text(unique_id))
    op.execute(text(thing_id))
    op.execute(text(observed_at))
    op.execute(
        text(
            f"CREATE INDEX ix_{view_name}_parameter_name "
            f"ON {view_name} (parameter_name)"
        )
    )


def _rebuild(create_view, create_indexes, comments) -> None:
    views = ((PUBLIC_VIEW, True), (INTERNAL_VIEW, False))
    for view_name, public_only in views:
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
    path = Path(__file__).with_name(
        "3f9c1b7d2a64_chemistry_views_time_on_collection_date.py"
    )
    module_name = "_chemistry_views_previous"
    spec = importlib.util.spec_from_file_location(module_name, path)
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
