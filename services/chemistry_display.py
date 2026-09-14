"""Build the well-details chemistry display payload from legacy NMA tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_FieldParameters,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
)
from db.thing import Thing
from schemas.chemistry import (
    ChemistryDisplayCrosstabColumnResponse,
    ChemistryDisplayCrosstabResponse,
    ChemistryDisplayCrosstabRowResponse,
    ChemistryDisplayResponse,
    ChemistryDisplayResultResponse,
    ChemistryDisplaySampleResponse,
    ChemistryDisplayStandardResponse,
    ChemistryDisplayStandardsSummaryResponse,
    ChemistryDisplayTabResponse,
)
from services.legacy_chemistry import canonical_parameter_name

SourceKind = Literal["major", "minor", "field"]

GENERAL_PARAMETER_ORDER = [
    "Arsenic",
    "Bicarbonate",
    "Calcium",
    "Chloride",
    "Fluoride",
    "Ion Balance",
    "Iron",
    "Magnesium",
    "Manganese",
    "Nitrate (as N)",
    "Potassium",
    "Sodium",
    "Sulfate",
    "Total Dissolved Solids",
    "pH",
    "Uranium (total, by ICP-MS)",
    "Uranium, total, unfiltered",
]
GENERAL_PARAMETERS = {name.lower() for name in GENERAL_PARAMETER_ORDER}
TRACER_SYMBOLS = {
    "3h",
    "h2r",
    "o18r",
    "o17r",
    "c13r",
    "c14",
    "c14_years",
    "sf6",
    "cfc11",
    "cfc12",
    "cfc113",
    "cfc113_12",
    "sr87:sr86",
    "d18o-so4",
    "d34s-so4",
}


@dataclass(frozen=True)
class Limit:
    primary_mcl: float | None = None
    secondary_smcl: float | tuple[float, float] | None = None
    unit: str = "mg/L"
    basis: str = "EPA drinking-water standards"


EPA_LIMITS = {
    "arsenic": Limit(
        primary_mcl=0.010,
        basis="EPA primary inorganic chemicals table",
    ),
    "fluoride": Limit(
        primary_mcl=4.0,
        secondary_smcl=2.0,
        basis="EPA primary and secondary standards",
    ),
    "iron": Limit(
        secondary_smcl=0.3,
        basis="EPA secondary standards table",
    ),
    "manganese": Limit(
        secondary_smcl=0.05,
        basis="EPA secondary standards table",
    ),
    "total dissolved solids": Limit(
        secondary_smcl=500.0, basis="EPA secondary standards table"
    ),
    "nitrate (as n)": Limit(
        primary_mcl=10.0, basis="EPA primary inorganic chemicals table"
    ),
    "sulfate": Limit(
        secondary_smcl=250.0,
        basis="EPA secondary standards table",
    ),
    "chloride": Limit(
        secondary_smcl=250.0,
        basis="EPA secondary standards table",
    ),
    "ph": Limit(
        secondary_smcl=(6.5, 8.5),
        unit="pH",
        basis="EPA secondary standards table",
    ),
    "uranium (total, by icp-ms)": Limit(
        primary_mcl=0.030, basis="EPA primary radionuclides table"
    ),
    "uranium, total, unfiltered": Limit(
        primary_mcl=0.030, basis="EPA primary radionuclides table"
    ),
}


def build_chemistry_display_payload(
    session: Session,
    *,
    thing_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sample_info_id: int | None = None,
) -> ChemistryDisplayResponse | None:
    thing = session.get(Thing, thing_id)
    if thing is None or thing.release_status != "public":
        return None

    samples = _get_samples(
        session,
        thing_id=thing_id,
        start_time=start_time,
        end_time=end_time,
    )
    if not samples:
        return None

    selected = _select_sample(samples, sample_info_id)
    if selected is None:
        return None

    sample_ids = [sample.id for sample in samples]
    sample_responses = [_sample_response(sample) for sample in samples]
    results = _get_results(session, sample_ids)
    tabs = {
        "field_parameters": _tab_payload(
            sample_responses,
            selected.id,
            [result for result in results if result.source == "field"],
        ),
        "general_chemistry": _tab_payload(
            sample_responses,
            selected.id,
            [result for result in results if _is_general_chemistry(result)],
            include_standards_summary=True,
        ),
        "environmental_tracers": _tab_payload(
            sample_responses,
            selected.id,
            [result for result in results if _is_environmental_tracer(result)],
        ),
        "additional_analyses": _tab_payload(
            sample_responses,
            selected.id,
            [
                result
                for result in results
                if result.source != "field"
                and not _is_general_chemistry(result)
                and not _is_environmental_tracer(result)
            ],
        ),
    }

    return ChemistryDisplayResponse(
        thing_id=thing_id,
        selected_sample_info_id=selected.id,
        samples=sample_responses,
        sample_note=selected.sample_notes,
        tabs=tabs,
    )


def _get_samples(
    session: Session,
    *,
    thing_id: int,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[NMA_Chemistry_SampleInfo]:
    query = select(NMA_Chemistry_SampleInfo).where(
        NMA_Chemistry_SampleInfo.thing_id == thing_id,
        NMA_Chemistry_SampleInfo.public_release.is_(True),
    )
    if start_time is not None:
        collection_date = NMA_Chemistry_SampleInfo.collection_date
        query = query.where(collection_date >= start_time)
    if end_time is not None:
        collection_date = NMA_Chemistry_SampleInfo.collection_date
        query = query.where(collection_date < end_time)

    query = query.order_by(
        NMA_Chemistry_SampleInfo.collection_date.desc().nullslast(),
        NMA_Chemistry_SampleInfo.id.desc(),
    )
    return list(session.scalars(query))


def _select_sample(
    samples: list[NMA_Chemistry_SampleInfo], sample_info_id: int | None
) -> NMA_Chemistry_SampleInfo | None:
    if sample_info_id is None:
        return samples[0]
    return next(
        (sample for sample in samples if sample.id == sample_info_id),
        None,
    )


def _get_results(
    session: Session, sample_ids: list[int]
) -> list[ChemistryDisplayResultResponse]:
    results: list[ChemistryDisplayResultResponse] = []
    major_rows = session.scalars(
        select(NMA_MajorChemistry).where(
            NMA_MajorChemistry.chemistry_sample_info_id.in_(sample_ids)
        )
    )
    minor_rows = session.scalars(
        select(NMA_MinorTraceChemistry).where(
            NMA_MinorTraceChemistry.chemistry_sample_info_id.in_(sample_ids)
        )
    )
    field_rows = session.scalars(
        select(NMA_FieldParameters).where(
            NMA_FieldParameters.chemistry_sample_info_id.in_(sample_ids)
        )
    )

    results.extend(_lab_result("major", row) for row in major_rows)
    results.extend(_lab_result("minor", row) for row in minor_rows)
    results.extend(_field_result(row) for row in field_rows)
    return sorted(results, key=_result_sort_key)


def _lab_result(source: SourceKind, row) -> ChemistryDisplayResultResponse:
    parameter_name = canonical_parameter_name(row.symbol or row.analyte)
    result = ChemistryDisplayResultResponse(
        id=f"{source}-{row.id}",
        sample_info_id=row.chemistry_sample_info_id,
        source=source,
        parameter_key=_parameter_key(source, parameter_name, row.symbol),
        parameter_name=parameter_name,
        analyte=row.analyte,
        symbol=row.symbol,
        value=row.sample_value,
        unit=row.units,
        uncertainty=row.uncertainty,
        analysis_method=row.analysis_method,
        analysis_date=row.analysis_date,
        notes=row.notes,
        analyses_agency=row.analyses_agency,
    )
    return result.model_copy(update={"standard": _standard_for_result(result)})


def _field_result(row: NMA_FieldParameters) -> ChemistryDisplayResultResponse:
    parameter_name = canonical_parameter_name(row.field_parameter)
    return ChemistryDisplayResultResponse(
        id=f"field-{row.id}",
        sample_info_id=row.chemistry_sample_info_id,
        source="field",
        parameter_key=_parameter_key(
            "field",
            parameter_name,
            row.field_parameter,
        ),
        parameter_name=parameter_name,
        analyte=row.field_parameter,
        symbol=row.field_parameter,
        value=row.sample_value,
        unit=row.units,
        notes=row.notes,
        analyses_agency=row.analyses_agency,
    )


def _sample_response(
    sample: NMA_Chemistry_SampleInfo,
) -> ChemistryDisplaySampleResponse:
    date_label = (
        sample.collection_date.strftime("%b %d, %Y")
        if sample.collection_date is not None
        else "undated"
    )
    label = f"{sample.nma_sample_point_id} - {date_label}"
    return ChemistryDisplaySampleResponse(
        id=sample.id,
        thing_id=sample.thing_id,
        label=label,
        nma_sample_point_id=sample.nma_sample_point_id,
        nma_wclab_id=sample.nma_wclab_id,
        collection_date=sample.collection_date,
        collection_method=sample.collection_method,
        collected_by=sample.collected_by,
        analyses_agency=sample.analyses_agency,
        sample_type=sample.sample_type,
        water_type=sample.water_type,
        data_source=sample.data_source,
        data_quality=sample.data_quality,
        sample_notes=sample.sample_notes,
    )


def _tab_payload(
    samples: list[ChemistryDisplaySampleResponse],
    selected_sample_id: int,
    results: list[ChemistryDisplayResultResponse],
    *,
    include_standards_summary: bool = False,
) -> ChemistryDisplayTabResponse:
    current_results = []
    for result in results:
        if result.sample_info_id == selected_sample_id:
            current_results.append(result)
    standards_summary = None
    if include_standards_summary:
        standards_summary = _standards_summary(current_results)

    return ChemistryDisplayTabResponse(
        current_results=current_results,
        results=results,
        crosstab=_crosstab(samples, results),
        standards_summary=standards_summary,
    )


def _crosstab(
    samples: list[ChemistryDisplaySampleResponse],
    results: list[ChemistryDisplayResultResponse],
) -> ChemistryDisplayCrosstabResponse:
    columns_by_key = {}
    for result in results:
        columns_by_key.setdefault(
            result.parameter_key,
            ChemistryDisplayCrosstabColumnResponse(
                parameter_key=result.parameter_key,
                parameter_name=result.parameter_name,
                symbol=result.symbol,
                unit=result.unit,
            ),
        )

    values_by_sample: dict[int, dict[str, ChemistryDisplayResultResponse]] = {
        sample.id: {} for sample in samples
    }
    for result in results:
        values_by_sample.setdefault(result.sample_info_id, {})[
            result.parameter_key
        ] = result

    rows = [
        ChemistryDisplayCrosstabRowResponse(
            sample_info_id=sample.id,
            sample_label=sample.label,
            collection_date=sample.collection_date,
            values=values_by_sample.get(sample.id, {}),
            sample_notes=sample.sample_notes,
        )
        for sample in reversed(samples)
    ]
    return ChemistryDisplayCrosstabResponse(
        columns=sorted(columns_by_key.values(), key=_column_sort_key),
        rows=rows,
    )


def _standards_summary(
    current_results: list[ChemistryDisplayResultResponse],
) -> ChemistryDisplayStandardsSummaryResponse:
    standards = []
    for result in current_results:
        if result.standard:
            standards.append(result.standard)
    compared = [
        standard
        for standard in standards
        if standard.status not in {"no_limit", "not_compared"}
    ]
    latest_analysis_date = _latest_analysis_date(current_results)
    return ChemistryDisplayStandardsSummaryResponse(
        above_mcl_count=sum(
            1 for standard in standards if standard.status == "above_mcl"
        ),
        above_smcl_count=sum(
            1 for standard in standards if standard.status == "above_smcl"
        ),
        compared_parameter_count=len(compared),
        latest_analysis_date=latest_analysis_date,
    )


def _standard_for_result(
    result: ChemistryDisplayResultResponse,
) -> ChemistryDisplayStandardResponse:
    name = (result.parameter_name or "").strip().lower()
    limit = EPA_LIMITS.get(name)
    if limit is None:
        return ChemistryDisplayStandardResponse(
            status="no_limit",
            label="No EPA limit",
        )

    value = _value_in_limit_unit(result.value, result.unit, limit.unit)
    if value is None:
        return ChemistryDisplayStandardResponse(
            status="not_compared",
            label="Not compared",
            primary_mcl=limit.primary_mcl,
            secondary_smcl=_limit_value(limit.secondary_smcl),
            unit=limit.unit,
            basis=limit.basis,
        )

    if limit.primary_mcl is not None:
        if value > limit.primary_mcl:
            status = "above_mcl"
            label = "Above MCL"
        elif _above_secondary_limit(value, limit.secondary_smcl):
            status = "above_smcl"
            label = "Above SMCL"
        else:
            status = "below_mcl"
            label = "Below MCL"
    elif isinstance(limit.secondary_smcl, tuple):
        low, high = limit.secondary_smcl
        if low <= value <= high:
            status = "within_smcl"
            label = "Within SMCL"
        else:
            status = "above_smcl"
            label = "Outside SMCL"
    elif limit.secondary_smcl is not None:
        if value > limit.secondary_smcl:
            status = "above_smcl"
            label = "Above SMCL"
        else:
            status = "below_smcl"
            label = "Below SMCL"
    else:
        status = "no_limit"
        label = "No EPA limit"

    return ChemistryDisplayStandardResponse(
        status=status,
        label=label,
        primary_mcl=limit.primary_mcl,
        secondary_smcl=_limit_value(limit.secondary_smcl),
        unit=limit.unit,
        basis=limit.basis,
    )


def _latest_analysis_date(
    results: list[ChemistryDisplayResultResponse],
) -> date | datetime | None:
    values = []
    for result in results:
        if result.analysis_date is not None:
            values.append(result.analysis_date)
    if not values:
        return None
    return max(values, key=_analysis_date_sort_key)


def _analysis_date_sort_key(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _above_secondary_limit(
    value: float,
    secondary_smcl: float | tuple[float, float] | None,
) -> bool:
    if isinstance(secondary_smcl, tuple):
        low, high = secondary_smcl
        return not low <= value <= high
    if secondary_smcl is not None:
        return value > secondary_smcl
    return False


def _value_in_limit_unit(
    value: float | None, unit: str | None, limit_unit: str
) -> float | None:
    if value is None:
        return None

    normalized_unit = (unit or "").strip().lower().replace("µ", "u")
    normalized_limit_unit = limit_unit.lower()
    if normalized_limit_unit == "ph":
        return value
    if normalized_unit in {"mg/l", "mg/liter", "milligrams/liter"}:
        return value
    if normalized_unit in {"ug/l", "µg/l", "micrograms/liter"}:
        return value / 1000
    if normalized_unit == "" and normalized_limit_unit == "mg/l":
        return value
    return None


def _limit_value(
    value: float | tuple[float, float] | None,
) -> float | str | None:
    if isinstance(value, tuple):
        return f"{value[0]}-{value[1]}"
    return value


def _is_general_chemistry(result: ChemistryDisplayResultResponse) -> bool:
    return (result.parameter_name or "").lower() in GENERAL_PARAMETERS


def _is_environmental_tracer(result: ChemistryDisplayResultResponse) -> bool:
    symbol = (result.symbol or result.analyte or "").strip().lower()
    return symbol in TRACER_SYMBOLS


def _parameter_key(
    source: SourceKind, parameter_name: str | None, symbol: str | None
) -> str:
    raw = parameter_name or symbol or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return f"{source}_{slug}"


def _result_sort_key(
    result: ChemistryDisplayResultResponse,
) -> tuple[int, str, str]:
    try:
        index = GENERAL_PARAMETER_ORDER.index(result.parameter_name or "")
    except ValueError:
        index = len(GENERAL_PARAMETER_ORDER)
    return (index, result.parameter_name or "", result.id)


def _column_sort_key(
    column: ChemistryDisplayCrosstabColumnResponse,
) -> tuple[int, str]:
    try:
        index = GENERAL_PARAMETER_ORDER.index(column.parameter_name or "")
    except ValueError:
        index = len(GENERAL_PARAMETER_ORDER)
    return (index, column.parameter_name or "")
