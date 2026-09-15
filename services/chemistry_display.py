"""Build the well-details chemistry display payload from legacy NMA tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import literal, select, union_all
from sqlalchemy.engine import Row, RowMapping
from sqlalchemy.orm import Session

from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_FieldParameters,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
    NMA_Radionuclides,
)
from db.thing import Thing
from schemas.chemistry import (
    ChemistryDisplayGeneralResponse,
    ChemistryDisplayResponse,
    ChemistryDisplayResultResponse,
    ChemistryDisplaySampleResponse,
    ChemistryDisplaySectionResponse,
    ChemistryDisplayStandardResponse,
    ChemistryDisplayStandardsSummaryResponse,
)
from services.legacy_chemistry import canonical_parameter_name

SourceKind = Literal["major", "minor", "radionuclide", "field"]

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
GENERAL_PARAMETER_INDEX = {
    name: index for index, name in enumerate(GENERAL_PARAMETER_ORDER)
}
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


EPA_PRIMARY_INORGANIC = "EPA primary inorganic chemicals table"
EPA_SECONDARY = "EPA secondary standards table"
EPA_LIMITS = {
    "arsenic": Limit(primary_mcl=0.010, basis=EPA_PRIMARY_INORGANIC),
    "fluoride": Limit(
        primary_mcl=4.0,
        secondary_smcl=2.0,
        basis="EPA primary and secondary standards",
    ),
    "iron": Limit(secondary_smcl=0.3, basis=EPA_SECONDARY),
    "manganese": Limit(secondary_smcl=0.05, basis=EPA_SECONDARY),
    "total dissolved solids": Limit(secondary_smcl=500.0, basis=EPA_SECONDARY),
    "nitrate (as n)": Limit(primary_mcl=10.0, basis=EPA_PRIMARY_INORGANIC),
    "sulfate": Limit(secondary_smcl=250.0, basis=EPA_SECONDARY),
    "chloride": Limit(secondary_smcl=250.0, basis=EPA_SECONDARY),
    "ph": Limit(secondary_smcl=(6.5, 8.5), unit="pH", basis=EPA_SECONDARY),
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
) -> ChemistryDisplayResponse | None:
    public_thing_id = session.scalar(
        select(Thing.id).where(
            Thing.id == thing_id,
            Thing.release_status == "public",
        )
    )
    if public_thing_id is None:
        return None

    samples = _get_samples(
        session,
        thing_id=thing_id,
        start_time=start_time,
        end_time=end_time,
    )
    if not samples:
        return None

    selected_sample_id = samples[0].id
    sample_ids = [sample.id for sample in samples]
    sample_responses = [_sample_response(sample) for sample in samples]

    sections: dict[str, list[ChemistryDisplayResultResponse]] = {
        "field": [],
        "general": [],
        "tracer": [],
        "additional": [],
    }

    for result in _get_results(session, sample_ids):
        sections[_result_section(result)].append(result)

    current_general_results = [
        result
        for result in sections["general"]
        if result.sample_info_id == selected_sample_id
    ]

    field_results = sections["field"]
    field_parameters = ChemistryDisplaySectionResponse(results=field_results)
    return ChemistryDisplayResponse(
        samples=sample_responses,
        field_parameters=field_parameters,
        general_chemistry=ChemistryDisplayGeneralResponse(
            results=sections["general"],
            standards_summary=_standards_summary(current_general_results),
        ),
        environmental_tracers=ChemistryDisplaySectionResponse(
            results=sections["tracer"]
        ),
        additional_analyses=ChemistryDisplaySectionResponse(
            results=sections["additional"]
        ),
    )


def _get_samples(
    session: Session,
    *,
    thing_id: int,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[Row]:
    query = select(
        NMA_Chemistry_SampleInfo.id,
        NMA_Chemistry_SampleInfo.thing_id,
        NMA_Chemistry_SampleInfo.nma_sample_point_id,
        NMA_Chemistry_SampleInfo.nma_wclab_id,
        NMA_Chemistry_SampleInfo.collection_date,
        NMA_Chemistry_SampleInfo.collection_method,
        NMA_Chemistry_SampleInfo.collected_by,
        NMA_Chemistry_SampleInfo.analyses_agency,
        NMA_Chemistry_SampleInfo.sample_type,
        NMA_Chemistry_SampleInfo.water_type,
        NMA_Chemistry_SampleInfo.data_source,
        NMA_Chemistry_SampleInfo.data_quality,
        NMA_Chemistry_SampleInfo.sample_notes,
    ).where(
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
    return list(session.execute(query))


def _get_results(
    session: Session, sample_ids: list[int]
) -> list[ChemistryDisplayResultResponse]:
    query = union_all(
        *(
            _lab_results_query(NMA_MajorChemistry, "major", sample_ids),
            _lab_results_query(NMA_MinorTraceChemistry, "minor", sample_ids),
            _lab_results_query(NMA_Radionuclides, "radionuclide", sample_ids),
            _field_results_query(sample_ids),
        )
    )
    return sorted(
        (_result_response(row) for row in session.execute(query).mappings()),
        key=_result_sort_key,
    )


def _lab_results_query(model, source: SourceKind, sample_ids: list[int]):
    return select(
        literal(source).label("source"),
        model.id.label("source_id"),
        model.chemistry_sample_info_id.label("sample_info_id"),
        model.analyte.label("analyte"),
        model.symbol.label("symbol"),
        model.sample_value.label("value"),
        model.units.label("unit"),
        model.uncertainty.label("uncertainty"),
        model.analysis_method.label("analysis_method"),
        model.analysis_date.label("analysis_date"),
        model.notes.label("notes"),
        model.analyses_agency.label("analyses_agency"),
    ).where(model.chemistry_sample_info_id.in_(sample_ids))


def _field_results_query(sample_ids: list[int]):
    return select(
        literal("field").label("source"),
        NMA_FieldParameters.id.label("source_id"),
        NMA_FieldParameters.chemistry_sample_info_id.label("sample_info_id"),
        NMA_FieldParameters.field_parameter.label("analyte"),
        NMA_FieldParameters.field_parameter.label("symbol"),
        NMA_FieldParameters.sample_value.label("value"),
        NMA_FieldParameters.units.label("unit"),
        literal(None).label("uncertainty"),
        literal(None).label("analysis_method"),
        literal(None).label("analysis_date"),
        NMA_FieldParameters.notes.label("notes"),
        NMA_FieldParameters.analyses_agency.label("analyses_agency"),
    ).where(NMA_FieldParameters.chemistry_sample_info_id.in_(sample_ids))


def _result_response(row: RowMapping) -> ChemistryDisplayResultResponse:
    source = row["source"]
    symbol = row["symbol"]
    analyte = row["analyte"]
    value = row["value"]
    unit = row["unit"]
    parameter_name = canonical_parameter_name(symbol or analyte)
    return ChemistryDisplayResultResponse(
        id=f"{source}-{row['source_id']}",
        sample_info_id=row["sample_info_id"],
        source=source,
        parameter_key=_parameter_key(source, parameter_name, symbol),
        parameter_name=parameter_name,
        analyte=analyte,
        symbol=symbol,
        value=value,
        unit=unit,
        uncertainty=row["uncertainty"],
        analysis_method=row["analysis_method"],
        analysis_date=row["analysis_date"],
        notes=row["notes"],
        analyses_agency=row["analyses_agency"],
        standard=_standard_for_result(parameter_name, value, unit),
    )


def _sample_response(sample: Row) -> ChemistryDisplaySampleResponse:
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


def _standards_summary(
    results: list[ChemistryDisplayResultResponse],
) -> ChemistryDisplayStandardsSummaryResponse:
    standards = [result.standard for result in results if result.standard]
    compared = [
        standard
        for standard in standards
        if standard.status not in {"no_limit", "not_compared"}
    ]
    return ChemistryDisplayStandardsSummaryResponse(
        above_mcl_count=sum(
            1 for standard in standards if standard.status == "above_mcl"
        ),
        above_smcl_count=sum(
            1 for standard in standards if standard.status == "above_smcl"
        ),
        compared_parameter_count=len(compared),
        latest_analysis_date=_latest_analysis_date(results),
    )


def _standard_for_result(
    parameter_name: str | None,
    result_value: float | None,
    result_unit: str | None,
) -> ChemistryDisplayStandardResponse:
    name = (parameter_name or "").strip().lower()
    limit = EPA_LIMITS.get(name)
    if limit is None:
        return ChemistryDisplayStandardResponse(
            status="no_limit",
            label="No EPA limit",
        )

    value = _value_in_limit_unit(result_value, result_unit, limit.unit)
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
) -> date | None:
    values = list(filter(None, (result.analysis_date for result in results)))
    if not values:
        return None
    latest = max(values, key=_analysis_date_sort_key)
    return latest.date() if isinstance(latest, datetime) else latest


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
    return None


def _limit_value(
    value: float | tuple[float, float] | None,
) -> float | str | None:
    if isinstance(value, tuple):
        return f"{value[0]}-{value[1]}"
    return value


def _result_section(
    result: ChemistryDisplayResultResponse,
) -> Literal["field", "general", "tracer", "additional"]:
    if result.source == "field":
        return "field"
    if (result.parameter_name or "").lower() in GENERAL_PARAMETERS:
        return "general"
    symbol = (result.symbol or result.analyte or "").strip().lower()
    if symbol in TRACER_SYMBOLS:
        return "tracer"
    return "additional"


def _parameter_key(
    source: SourceKind, parameter_name: str | None, symbol: str | None
) -> str:
    raw = parameter_name or symbol or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return f"{source}_{slug}"


def _result_sort_key(
    result: ChemistryDisplayResultResponse,
) -> tuple[int, str, str]:
    index = GENERAL_PARAMETER_INDEX.get(
        result.parameter_name or "",
        len(GENERAL_PARAMETER_ORDER),
    )
    return (index, result.parameter_name or "", result.id)
