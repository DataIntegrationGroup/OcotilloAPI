"""Build water chemistry result payloads from legacy NMA tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import (
    String,
    asc,
    cast,
    desc,
    func,
    literal,
    select,
    union_all,
)
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_FieldParameters,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
    NMA_Radionuclides,
)
from db.parameter import Parameter
from db.regulatory_limit import RegulatoryLimit
from db.thing import Thing
from schemas.chemistry import (
    WaterChemistryResultResponse,
    WaterChemistryResultStandardResponse,
)
from services.legacy_chemistry import canonical_parameter_name, result_kind

SourceKind = Literal["major", "minor", "radionuclide", "field"]
SOURCE_PREFIXES: dict[SourceKind, str] = {
    "major": "maj",
    "minor": "min",
    "radionuclide": "rad",
    "field": "fld",
}

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
class ResultMetadata:
    source: SourceKind
    source_id: int
    analyte: str | None = None
    symbol: str | None = None
    uncertainty: float | None = None
    analysis_method: str | None = None
    notes: str | None = None
    analyses_agency: str | None = None


EPA_LIMIT_BASIS = "EPA drinking-water standards"
EPA_LIMIT_TYPES = ("MCL", "SMCL")


def build_water_chemistry_results_query(
    *,
    thing_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    exclude_field_duplicate_samples: bool = False,
):
    results = _water_chemistry_results_selectable()
    query = select(results)

    if thing_id is not None:
        query = query.where(results.c.thing_id == thing_id)

    if start_time is not None:
        query = query.where(results.c.observation_datetime >= start_time)

    if end_time is not None:
        query = query.where(results.c.observation_datetime < end_time)

    if exclude_field_duplicate_samples:
        query = query.where(results.c.sample_type.is_distinct_from("FD"))

    sort_columns = {
        "observation_datetime": results.c.observation_datetime,
        "parameter_name": results.c.parameter_name,
        "value": results.c.value,
        "id": results.c.id,
    }
    sort_column = sort_columns.get(sort or "observation_datetime")
    direction = asc if (order or "desc").lower() == "asc" else desc

    # id is the tiebreaker so paging is stable: without it two analytes
    # sharing a timestamp can swap pages between requests and be served twice
    # or never.
    return query.order_by(direction(sort_column), results.c.id)


def enrich_water_chemistry_results(
    session: Session,
    rows,
) -> list[WaterChemistryResultResponse]:
    """Add result metadata to one paginated page of chemistry result rows."""
    rows = list(rows)
    metadata_by_result_id = {}
    rows_missing_metadata = []
    for row in rows:
        result_id = _row_value(row, "id")
        metadata = _metadata_from_row(row)
        if metadata is None:
            rows_missing_metadata.append(row)
        else:
            metadata_by_result_id[result_id] = metadata
    missing_metadata = _metadata_by_result_id(session, rows_missing_metadata)
    metadata_by_result_id.update(missing_metadata)
    metadata_for = metadata_by_result_id.get

    prepared_rows = []
    parameter_names = set()
    for row in rows:
        result_id = _row_value(row, "id")
        metadata = _metadata_from_row(row) or metadata_for(result_id)
        parameter_name = _canonical_parameter_name_for_row(row, metadata)
        if parameter_name:
            parameter_names.add(parameter_name)
        prepared_rows.append((row, metadata, parameter_name))

    limits_by_parameter = _epa_limits_by_names(session, parameter_names)

    responses = []
    for row, metadata, parameter_name in prepared_rows:
        limits = limits_by_parameter.get(parameter_name or "", {})
        response = _water_chemistry_result_response(
            row, metadata, parameter_name, limits
        )
        responses.append(response)
    return responses


def _epa_limits_by_names(
    session: Session,
    parameter_names: set[str],
) -> dict[str, dict[str, RowMapping]]:
    if not parameter_names:
        return {}

    query = (
        select(
            Parameter.parameter_name,
            RegulatoryLimit.limit_type,
            RegulatoryLimit.limit_value,
            RegulatoryLimit.limit_unit,
        )
        .join(Parameter, Parameter.id == RegulatoryLimit.parameter_id)
        .where(
            RegulatoryLimit.limit_source == "EPA",
            RegulatoryLimit.limit_type.in_(EPA_LIMIT_TYPES),
            RegulatoryLimit.release_status == "public",
            Parameter.matrix == "groundwater",
            Parameter.parameter_name.in_(parameter_names),
        )
    )

    limits_by_parameter: dict[str, dict[str, RowMapping]] = {}
    for row in session.execute(query).mappings():
        limits_by_parameter.setdefault(row["parameter_name"], {})[
            row["limit_type"]
        ] = row
    return limits_by_parameter


def _water_chemistry_results_selectable():
    return union_all(
        _lab_water_chemistry_results_query(NMA_MajorChemistry, "major"),
        _lab_water_chemistry_results_query(NMA_MinorTraceChemistry, "minor"),
        _lab_water_chemistry_results_query(NMA_Radionuclides, "radionuclide"),
        _field_water_chemistry_results_query(),
    ).subquery("water_chemistry_results")


def _lab_water_chemistry_results_query(model, source: SourceKind):
    observed_at = NMA_Chemistry_SampleInfo.collection_date
    sample_point_id = NMA_Chemistry_SampleInfo.nma_sample_point_id.label(
        "sample_point_id"
    )
    parameter_name = func.nullif(func.trim(model.analyte), "")
    return (
        select(
            _result_id_expression(source, model.id).label("id"),
            literal(source).label("source"),
            model.id.label("source_id"),
            NMA_Chemistry_SampleInfo.thing_id.label("thing_id"),
            Thing.name.label("station_name"),
            Thing.thing_type.label("thing_type"),
            NMA_Chemistry_SampleInfo.id.label("sample_id"),
            NMA_Chemistry_SampleInfo.sample_type.label("sample_type"),
            sample_point_id,
            parameter_name.label("parameter_name"),
            model.sample_value.label("value"),
            model.units.label("unit"),
            observed_at.label("observation_datetime"),
            model.analysis_date.label("analysis_date"),
            Thing.release_status.label("release_status"),
            model.analyte.label("analyte"),
            model.symbol.label("symbol"),
            model.uncertainty.label("uncertainty"),
            model.analysis_method.label("analysis_method"),
            model.notes.label("notes"),
            model.analyses_agency.label("analyses_agency"),
        )
        .join(
            NMA_Chemistry_SampleInfo,
            NMA_Chemistry_SampleInfo.id == model.chemistry_sample_info_id,
        )
        .join(Thing, Thing.id == NMA_Chemistry_SampleInfo.thing_id)
        .where(
            model.sample_value.isnot(None),
            parameter_name.isnot(None),
            observed_at.isnot(None),
            Thing.release_status == "public",
            NMA_Chemistry_SampleInfo.public_release.isnot(False),
        )
    )


def _field_water_chemistry_results_query():
    observed_at = NMA_Chemistry_SampleInfo.collection_date
    sample_point_id = NMA_Chemistry_SampleInfo.nma_sample_point_id.label(
        "sample_point_id"
    )
    parameter_name = func.nullif(
        func.trim(NMA_FieldParameters.field_parameter),
        "",
    )
    field_sample_id = NMA_FieldParameters.chemistry_sample_info_id
    sample_join = NMA_Chemistry_SampleInfo.id == field_sample_id
    return (
        select(
            _result_id_expression("field", NMA_FieldParameters.id).label("id"),
            literal("field").label("source"),
            NMA_FieldParameters.id.label("source_id"),
            NMA_Chemistry_SampleInfo.thing_id.label("thing_id"),
            Thing.name.label("station_name"),
            Thing.thing_type.label("thing_type"),
            NMA_Chemistry_SampleInfo.id.label("sample_id"),
            NMA_Chemistry_SampleInfo.sample_type.label("sample_type"),
            sample_point_id,
            parameter_name.label("parameter_name"),
            NMA_FieldParameters.sample_value.label("value"),
            NMA_FieldParameters.units.label("unit"),
            observed_at.label("observation_datetime"),
            literal(None).label("analysis_date"),
            Thing.release_status.label("release_status"),
            NMA_FieldParameters.field_parameter.label("analyte"),
            NMA_FieldParameters.field_parameter.label("symbol"),
            literal(None).label("uncertainty"),
            literal(None).label("analysis_method"),
            NMA_FieldParameters.notes.label("notes"),
            NMA_FieldParameters.analyses_agency.label("analyses_agency"),
        )
        .join(
            NMA_Chemistry_SampleInfo,
            sample_join,
        )
        .join(Thing, Thing.id == NMA_Chemistry_SampleInfo.thing_id)
        .where(
            NMA_FieldParameters.sample_value.isnot(None),
            parameter_name.isnot(None),
            observed_at.isnot(None),
            Thing.release_status == "public",
            # NULL means the flag was never recorded, not that the record is
            # withheld. amp_viewer users are permitted to view unset records;
            # only explicit False is dropped.
            NMA_Chemistry_SampleInfo.public_release.isnot(False),
        )
    )


def _result_id_expression(source: SourceKind, source_id):
    return literal(f"{SOURCE_PREFIXES[source]}-") + cast(source_id, String)


def _metadata_by_result_id(
    session: Session,
    rows: list,
) -> dict[str, ResultMetadata]:
    ids_by_source: dict[SourceKind, list[int]] = {
        "major": [],
        "minor": [],
        "radionuclide": [],
        "field": [],
    }
    for row in rows:
        result_id = _row_value(row, "id")
        source_id = _source_id(result_id)
        source = result_kind(result_id)
        if source_id is None or source not in ids_by_source:
            continue
        ids_by_source[source].append(source_id)

    metadata: dict[str, ResultMetadata] = {}
    metadata.update(
        _lab_metadata_by_result_id(
            session, NMA_MajorChemistry, "major", ids_by_source["major"]
        )
    )
    metadata.update(
        _lab_metadata_by_result_id(
            session, NMA_MinorTraceChemistry, "minor", ids_by_source["minor"]
        )
    )
    metadata.update(
        _lab_metadata_by_result_id(
            session,
            NMA_Radionuclides,
            "radionuclide",
            ids_by_source["radionuclide"],
        )
    )
    field_ids = ids_by_source["field"]
    metadata.update(_field_metadata_by_result_id(session, field_ids))
    return metadata


def _source_id(result_id: str | None) -> int | None:
    if not result_id:
        return None
    _, _, raw_source_id = result_id.partition("-")
    try:
        return int(raw_source_id)
    except ValueError:
        return None


def _lab_metadata_by_result_id(
    session: Session,
    model,
    source: SourceKind,
    source_ids: list[int],
) -> dict[str, ResultMetadata]:
    if not source_ids:
        return {}

    query = select(
        model.id.label("source_id"),
        model.analyte,
        model.symbol,
        model.uncertainty,
        model.analysis_method,
        model.notes,
        model.analyses_agency,
    ).where(model.id.in_(source_ids))
    return {
        _result_id(source, row["source_id"]): ResultMetadata(
            source=source,
            source_id=row["source_id"],
            analyte=row["analyte"],
            symbol=row["symbol"],
            uncertainty=row["uncertainty"],
            analysis_method=row["analysis_method"],
            notes=row["notes"],
            analyses_agency=row["analyses_agency"],
        )
        for row in session.execute(query).mappings()
    }


def _field_metadata_by_result_id(
    session: Session,
    source_ids: list[int],
) -> dict[str, ResultMetadata]:
    if not source_ids:
        return {}

    query = select(
        NMA_FieldParameters.id.label("source_id"),
        NMA_FieldParameters.field_parameter.label("field_parameter"),
        NMA_FieldParameters.notes,
        NMA_FieldParameters.analyses_agency,
    ).where(NMA_FieldParameters.id.in_(source_ids))
    return {
        _result_id("field", row["source_id"]): ResultMetadata(
            source="field",
            source_id=row["source_id"],
            analyte=row["field_parameter"],
            symbol=row["field_parameter"],
            notes=row["notes"],
            analyses_agency=row["analyses_agency"],
        )
        for row in session.execute(query).mappings()
    }


def _result_id(source: SourceKind, source_id: int) -> str:
    return f"{SOURCE_PREFIXES[source]}-{source_id}"


def _water_chemistry_result_response(
    row,
    metadata: ResultMetadata | None,
    parameter_name: str | None,
    limits: dict[str, RowMapping],
) -> WaterChemistryResultResponse:
    result_id = _row_value(row, "id")
    source = metadata.source if metadata else result_kind(result_id)
    if source not in SOURCE_PREFIXES:
        source = None
    symbol = metadata.symbol if metadata else None
    standard = standard_for_result(
        _row_value(row, "value"),
        _row_value(row, "unit"),
        limits,
    )

    response_data = {
        "id": result_id,
        "thing_id": _row_value(row, "thing_id"),
        "station_name": _row_value(row, "station_name"),
        "sample_id": _row_value(row, "sample_id"),
        "sample_point_id": _row_value(row, "sample_point_id"),
        "parameter_name": _row_value(row, "parameter_name"),
        "value": _row_value(row, "value"),
        "unit": _row_value(row, "unit"),
        "observation_datetime": _row_value(row, "observation_datetime"),
        "analysis_date": _row_value(row, "analysis_date"),
    }

    response = WaterChemistryResultResponse.model_validate(response_data)
    return response.model_copy(
        update={
            "source": source,
            "parameter_name": parameter_name,
            "parameter_key": (
                parameter_key(source, parameter_name, symbol)
                if source is not None
                else None
            ),
            "analyte": metadata.analyte if metadata else None,
            "symbol": symbol,
            "uncertainty": metadata.uncertainty if metadata else None,
            "analysis_method": metadata.analysis_method if metadata else None,
            "notes": metadata.notes if metadata else None,
            "analyses_agency": metadata.analyses_agency if metadata else None,
            "standard": standard,
            "result_kind": result_kind(result_id),
        }
    )


def _canonical_parameter_name_for_row(
    row,
    metadata: ResultMetadata | None,
) -> str | None:
    if metadata:
        raw_parameter_name = metadata.analyte
    else:
        raw_parameter_name = _row_value(row, "parameter_name")
    return canonical_parameter_name(raw_parameter_name)


def _metadata_from_row(row) -> ResultMetadata | None:
    source = _row_value(row, "source", None)
    source_id = _row_value(row, "source_id", None)
    if source not in SOURCE_PREFIXES or source_id is None:
        return None

    return ResultMetadata(
        source=source,
        source_id=source_id,
        analyte=_row_value(row, "analyte", None),
        symbol=_row_value(row, "symbol", None),
        uncertainty=_row_value(row, "uncertainty", None),
        analysis_method=_row_value(row, "analysis_method", None),
        notes=_row_value(row, "notes", None),
        analyses_agency=_row_value(row, "analyses_agency", None),
    )


def _row_value(row, name: str, default=None):
    if isinstance(row, RowMapping):
        return row.get(name, default)

    mapping = getattr(row, "_mapping", None)
    if mapping is not None and name in mapping:
        return mapping[name]

    return getattr(row, name, default)


def standard_for_result(
    result_value: float | None,
    result_unit: str | None,
    limits: dict[str, RowMapping],
) -> WaterChemistryResultStandardResponse:
    primary_mcl = limits.get("MCL")
    secondary_smcl = limits.get("SMCL")
    if primary_mcl is None and secondary_smcl is None:
        return WaterChemistryResultStandardResponse(
            status="no_limit",
            label="No EPA limit",
        )

    limit_unit = _limit_unit(primary_mcl or secondary_smcl)
    value = _value_in_limit_unit(result_value, result_unit, limit_unit)
    if value is None:
        return WaterChemistryResultStandardResponse(
            status="not_compared",
            label="Not compared",
            primary_mcl=_limit_value(primary_mcl),
            secondary_smcl=_limit_value(secondary_smcl),
            unit=limit_unit,
            basis=EPA_LIMIT_BASIS,
        )

    primary_value = _limit_value(primary_mcl)
    secondary_value = _limit_value(secondary_smcl)
    if primary_value is not None:
        if value > primary_value:
            status = "above_mcl"
            label = "Above MCL"
        elif _above_secondary_limit(value, secondary_value):
            status = "above_smcl"
            label = "Above SMCL"
        else:
            status = "below_mcl"
            label = "Below MCL"
    elif secondary_value is not None:
        if value > secondary_value:
            status = "above_smcl"
            label = "Above SMCL"
        else:
            status = "below_smcl"
            label = "Below SMCL"
    else:
        status = "no_limit"
        label = "No EPA limit"

    return WaterChemistryResultStandardResponse(
        status=status,
        label=label,
        primary_mcl=primary_value,
        secondary_smcl=secondary_value,
        unit=limit_unit,
        basis=EPA_LIMIT_BASIS,
    )


def _above_secondary_limit(
    value: float,
    secondary_smcl: float | None,
) -> bool:
    if secondary_smcl is not None:
        return value > secondary_smcl
    return False


def _value_in_limit_unit(
    value: float | None, unit: str | None, limit_unit: str | None
) -> float | None:
    if value is None or limit_unit is None:
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


def _limit_value(limit: RowMapping | None) -> float | None:
    if limit is None:
        return None
    return float(limit["limit_value"])


def _limit_unit(limit: RowMapping | None) -> str | None:
    if limit is None:
        return None
    return limit["limit_unit"]


def parameter_key(
    source: SourceKind, parameter_name: str | None, symbol: str | None
) -> str:
    raw = parameter_name or symbol or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return f"{source}_{slug}"
