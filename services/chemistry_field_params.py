# ===============================================================================
# Copyright 2026 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
"""
Ingest the AMP chemistry field spreadsheet -- the ``ChemistrySampleInfo`` and
``FieldParameters`` tabs -- into ``NMA_Chemistry_SampleInfo`` and
``NMA_FieldParameters``.

This is the field half of chemistry ingestion. The lab half already arrives as
a LIMS workbook through :mod:`services.chemistry_lims`, and the two meet at the
sample: a well visit recorded in the spreadsheet and a lab batch for the same
visit must end up on one ``NMA_Chemistry_SampleInfo`` row, not two. They are
matched on **well PointID plus collection date**, because the spreadsheet
carries no lab id -- the field crew writes it down before the sample reaches a
lab.

Shape of the two tabs
---------------------
``ChemistrySampleInfo`` is one row per sample: the well (``WellPointID``), the
lettered sample point (``SamplePointID``), and the visit's metadata.

``FieldParameters`` is one row per sample with each measured quantity in its own
column (``pHf``, ``T (C)``, ``CF (uS/cm)``, ...). The legacy table is long --
one row per measurement -- so each populated cell becomes its own
``NMA_FieldParameters`` row. See :data:`FIELD_PARAMETER_COLUMNS`.

Idempotency and failure
-----------------------
Re-running is safe: a sample already recorded for the well at that collection
date is reused rather than duplicated, and a field parameter already recorded
for that sample is skipped. As in the LIMS ingest, any data-quality problem
aborts the whole import and nothing is written, so a spreadsheet is never half
loaded.

The public entrypoints are :func:`import_field_tables` (tables in hand),
:func:`sync_field_sheet` (Google Drive) and :func:`upload_field_export`
(a local ``.xlsx``/``.csv`` export).
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import NMA_Chemistry_SampleInfo, NMA_FieldParameters
from db.engine import session_ctx
from domain.values import to_datetime, to_float
from services.chemistry_field_sheet import (
    FieldSheetError,
    SheetTable,
    read_google_spreadsheet,
    read_local_export,
)
from services.ingest_raw_zone import (
    archive_tables,
    raw_zone_url,
    read_snapshot,
)
from services.chemistry_lims import (
    ChemistryUploadResult,
    _existing_suffix_ints,
    _int_to_suffix,
    resolve_thing_id,
    split_pointid,
)

DEFAULT_AGENCY = "NMBGMR"

SAMPLE_INFO_TAB = "ChemistrySampleInfo"
FIELD_PARAMETERS_TAB = "FieldParameters"

# Tabs this ingest reads. The workbook also carries lab results
# (``GenChemResults``, ``IsotopeResults``); those are the LIMS ingest's
# business and are left alone here.
FIELD_SHEET_TABS = (SAMPLE_INFO_TAB, FIELD_PARAMETERS_TAB)

SHEET_ID_ENV_VAR = "CHEMISTRY_FIELD_SHEET_ID"

FIELD_SHEET_DATASET = "chemistry_field_sheet"
"""Raw-zone dataset holding the archived tabs."""


class FieldParamsMappingError(ValueError):
    """A spreadsheet row could not be normalized into a sample or measurement."""


@dataclass(frozen=True)
class FieldParameterColumn:
    """One measured column of the ``FieldParameters`` tab.

    ``symbol`` is the legacy ``FieldParameter`` code (the vocabulary in
    :mod:`services.legacy_chemistry`), and ``units`` is what the value is
    stored as -- normalized here rather than taken from the column heading, so
    field rows read the same as the lab rows the LIMS ingest writes.
    """

    header: str
    symbol: str
    units: str


FIELD_PARAMETER_COLUMNS: tuple[FieldParameterColumn, ...] = (
    FieldParameterColumn("pHf", "pHf", "pH"),
    FieldParameterColumn("T (C)", "T", "°C"),
    FieldParameterColumn("CF (uS/cm)", "CF", "µS/cm"),
    FieldParameterColumn("DO (mg/L)", "DO", "mg/L"),
    FieldParameterColumn("ORP (mV)", "ORP", "mV"),
    # No legacy AMP symbol exists for pumped discharge -- it is not in the
    # NM_Aquifer FieldParameters vocabulary -- so this ingest introduces one
    # rather than dropping a measurement the field crew recorded.
    FieldParameterColumn("Discharge rate (gpm)", "Q", "gpm"),
)


def _normalize_header(value: Any) -> str:
    """Normalize a heading for matching: casefold, drop any parenthetical.

    The template's headings carry hints to whoever is typing -- "SampleType
    (SD)", "CollectedBy (GR = grab??)" -- which are prone to being reworded.
    Matching on the part before the parenthesis keeps a reworded hint from
    silently dropping a column.
    """
    text = str(value or "")
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", "", text.casefold())
    return text


_FIELD_PARAMETER_LOOKUP = {
    _normalize_header(column.header): column for column in FIELD_PARAMETER_COLUMNS
}

# ChemistrySampleInfo heading -> the attribute it feeds.
_SAMPLE_INFO_FIELDS = {
    "analysisagency": "analyses_agency",
    "analysesagency": "analyses_agency",
    "sampletype": "sample_type",
    "collectionmethod": "collection_method",
    "collectedby": "collected_by",
    "datasource": "data_source",
    "samplenotes": "sample_notes",
    "watertype": "water_type",
}

# CollectedBy is a 5-character code column in the legacy schema.
_COLLECTED_BY_MAX = 5

# NM_Aquifer's LU_CollectionMethod, meaning -> code. The sheet may hold either;
# the meaning is preferred because "F" and "H" are both faucets, and a crew
# reading the letter alone cannot tell the well head from the house. The column
# stores the code, which is what every legacy NMA_Chemistry_SampleInfo row
# holds, so a sheet row and a legacy row for the same visit compare equal when
# filling blanks.
COLLECTION_METHODS: dict[str, str] = {
    "Bailer": "B",
    "Faucet at well head": "F",
    "Grab sample": "G",
    "Faucet or outlet at house": "H",
    "Pump": "P",
    "Thief sampler": "T",
    "Unknown": "U",
}

_COLLECTION_METHOD_BY_MEANING = {
    meaning.casefold(): code for meaning, code in COLLECTION_METHODS.items()
}
_COLLECTION_METHOD_CODES = frozenset(COLLECTION_METHODS.values())


# --- cell helpers --------------------------------------------------------------


def _cell(record: dict, *headings: str) -> Any:
    """First non-empty value among ``headings``, matched on normalized headers."""
    wanted = {_normalize_header(h) for h in headings}
    for key, value in record.items():
        if key == SheetTable.ROW_NUMBER_KEY:
            continue
        if _normalize_header(key) not in wanted:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> float | None:
    """A field reading. Lenient: the field tabs have no qualifier column, so a
    qualifier typed into the value is stripped rather than failing the row."""
    return to_float(value, lenient=True)


def _to_datetime(value: Any) -> datetime | None:
    """A collection or measurement time, as the crew actually writes them."""
    return to_datetime(value, pad_single_digit_hour=True)


def _collection_method_code(value: Any) -> str:
    """The legacy code for a collection method, written out or as the code.

    The meaning is preferred, but the legacy letter is accepted too, since
    crews trained on the old template still write it. Case and spacing are
    forgiven either way.
    """
    written = " ".join(str(value).split())
    code = _COLLECTION_METHOD_BY_MEANING.get(written.casefold())
    if code is not None:
        return code
    if written.upper() in _COLLECTION_METHOD_CODES:
        return written.upper()

    allowed = ", ".join(repr(m) for m in COLLECTION_METHODS)
    raise FieldParamsMappingError(
        f"CollectionMethod {written!r} is not a known collection method; "
        f"use one of {allowed}, or its legacy code"
    )


# --- row normalization ---------------------------------------------------------


def _reject_unassigned_pointid(pointid: str) -> None:
    """Refuse a PointID the crew has not been given yet.

    Rows come back from the field written ``WL-####`` when the well has no
    identifier assigned. Those are real samples with real readings, so they are
    reported by name -- not skipped, and certainly not loaded against a made-up
    well -- and the run is blocked until someone assigns the PointID.
    """
    if "#" in pointid:
        raise FieldParamsMappingError(
            f"PointID {pointid!r} has no well identifier assigned yet; assign one "
            "in the spreadsheet before ingesting this row"
        )


def prep_sample_info(record: dict) -> dict:
    """Normalize one ``ChemistrySampleInfo`` row.

    Raises :class:`FieldParamsMappingError` when the row cannot be loaded.
    """
    well_pointid = _cell(record, "WellPointID", "PointID")
    sample_point_id = _cell(record, "SamplePointID")

    if not well_pointid and not sample_point_id:
        raise FieldParamsMappingError("Missing WellPointID")

    if not well_pointid:
        # Only the lettered sample point was filled in; the well is its base.
        well_pointid, _ = split_pointid(str(sample_point_id).strip())

    well_pointid = str(well_pointid).strip()
    _reject_unassigned_pointid(well_pointid)

    supplied_suffix = None
    if sample_point_id:
        sample_point_id = str(sample_point_id).strip()
        base, supplied_suffix = split_pointid(sample_point_id)
        if base != well_pointid:
            raise FieldParamsMappingError(
                f"SamplePointID {sample_point_id!r} does not belong to well "
                f"{well_pointid!r}"
            )

    collection_date = _cell(record, "CollectionDate", "SampleDate")
    parsed_date = _to_datetime(collection_date)
    if collection_date is not None and parsed_date is None:
        raise FieldParamsMappingError(
            f"CollectionDate {collection_date!r} is not a recognizable date"
        )
    if parsed_date is None:
        # The collection date is what a field sample is matched on, both against
        # the lab batch and against a previous run of this import. Without one
        # the row cannot be reconciled with anything, so it is not loadable.
        raise FieldParamsMappingError("Missing CollectionDate")

    attributes: dict[str, Any] = {}
    for heading, attribute in _SAMPLE_INFO_FIELDS.items():
        value = _cell(record, heading)
        if value is None:
            continue
        attributes[attribute] = str(value).strip() if isinstance(value, str) else value

    if "collection_method" in attributes:
        attributes["collection_method"] = _collection_method_code(
            attributes["collection_method"]
        )

    collected_by = attributes.get("collected_by")
    if collected_by is not None and len(str(collected_by)) > _COLLECTED_BY_MAX:
        raise FieldParamsMappingError(
            f"CollectedBy {collected_by!r} is longer than {_COLLECTED_BY_MAX} "
            "characters, which is all the column holds"
        )

    # Staff has no column of its own in the legacy schema, and dropping the
    # names would lose the only record of who was on site, so it is folded into
    # the notes under its own label.
    staff = _cell(record, "Staff")
    if staff:
        note = f"Staff: {str(staff).strip()}"
        existing = attributes.get("sample_notes")
        attributes["sample_notes"] = f"{note}\n{existing}" if existing else note

    attributes.setdefault("analyses_agency", DEFAULT_AGENCY)

    return {
        "row_number": record.get(SheetTable.ROW_NUMBER_KEY),
        "well_pointid": well_pointid,
        "sample_point_id": sample_point_id or None,
        "supplied_suffix": supplied_suffix,
        "collection_date": parsed_date,
        "attributes": attributes,
    }


def prep_field_parameters(record: dict) -> dict:
    """Normalize one ``FieldParameters`` row into its measurements."""
    sample_point_id = _cell(record, "SamplePointID", "PointID")
    if not sample_point_id:
        raise FieldParamsMappingError("Missing SamplePointID")
    sample_point_id = str(sample_point_id).strip()
    _reject_unassigned_pointid(sample_point_id)

    measured_at = _to_datetime(_cell(record, "Time", "MeasurementTime"))

    measurements = []
    unreadable = []
    for key, value in record.items():
        if key == SheetTable.ROW_NUMBER_KEY:
            continue
        column = _FIELD_PARAMETER_LOOKUP.get(_normalize_header(key))
        if column is None:
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        number = _to_float(value)
        if number is None:
            unreadable.append(f"{column.header}={value!r}")
            continue
        measurements.append(
            {
                "symbol": column.symbol,
                "units": column.units,
                "value": number,
            }
        )

    if unreadable:
        raise FieldParamsMappingError(
            f"{sample_point_id}: non-numeric reading(s) {', '.join(unreadable)}"
        )

    return {
        "row_number": record.get(SheetTable.ROW_NUMBER_KEY),
        "sample_point_id": sample_point_id,
        "measured_at": measured_at,
        "measurements": measurements,
    }


# --- table selection -----------------------------------------------------------


def _looks_like_sample_info(table: SheetTable) -> bool:
    keys = {_normalize_header(h) for h in table.header}
    return "wellpointid" in keys or {"samplepointid", "collectiondate"} <= keys


def _looks_like_field_parameters(table: SheetTable) -> bool:
    keys = {_normalize_header(h) for h in table.header}
    return bool(keys & set(_FIELD_PARAMETER_LOOKUP)) and "samplepointid" in keys


def select_tables(
    tables: Sequence[SheetTable],
) -> tuple[SheetTable | None, SheetTable | None]:
    """Pick the sample-info and field-parameter tabs out of a workbook.

    Tab titles are matched first, then the header row, so a renamed tab is still
    found and a CSV export of a single tab (whose "title" is a filename) works
    the same way.
    """
    sample_info = None
    field_params = None
    for table in tables:
        title = _normalize_header(table.title)
        if title == _normalize_header(SAMPLE_INFO_TAB):
            sample_info = table
        elif title == _normalize_header(FIELD_PARAMETERS_TAB):
            field_params = table

    for table in tables:
        if (
            sample_info is None
            and table is not field_params
            and _looks_like_sample_info(table)
        ):
            sample_info = table
        elif (
            field_params is None
            and table is not sample_info
            and _looks_like_field_parameters(table)
        ):
            field_params = table

    return sample_info, field_params


# --- persistence ---------------------------------------------------------------


def _find_existing_sample(
    session: Session, thing_id: int, collection_date: datetime
) -> tuple[NMA_Chemistry_SampleInfo | None, str | None]:
    """The sample already recorded for this well at this collection date.

    Matching is on the well and the date because that is all the field sheet
    knows -- there is no lab id until the batch comes back. An exact timestamp
    match wins; failing that, a sample on the same calendar day is treated as
    the same visit, since the sheet's time and the lab's time for one visit
    routinely differ by minutes. Two samples on the same day are ambiguous and
    are reported rather than guessed at.
    """
    exact = session.scalars(
        select(NMA_Chemistry_SampleInfo).where(
            NMA_Chemistry_SampleInfo.thing_id == thing_id,
            NMA_Chemistry_SampleInfo.collection_date == collection_date,
        )
    ).all()
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, "more than one sample already recorded at that exact time"

    same_day = session.scalars(
        select(NMA_Chemistry_SampleInfo).where(
            NMA_Chemistry_SampleInfo.thing_id == thing_id,
            func.date(NMA_Chemistry_SampleInfo.collection_date)
            == collection_date.date(),
        )
    ).all()
    if len(same_day) == 1:
        return same_day[0], None
    if len(same_day) > 1:
        points = ", ".join(sorted(s.nma_sample_point_id or "?" for s in same_day))
        return None, (
            f"{len(same_day)} samples already recorded on "
            f"{collection_date.date().isoformat()} ({points}); cannot tell which "
            "one this row belongs to"
        )
    return None, None


def _apply_attributes(
    sample: NMA_Chemistry_SampleInfo, attributes: dict, label: str
) -> list[str]:
    """Fill blank columns on an existing sample; never overwrite a value.

    A field sheet is re-typed and re-sent, so it is not authoritative over what
    is already stored. A disagreement is reported for a human to settle.
    """
    warnings = []
    for attribute, value in attributes.items():
        current = getattr(sample, attribute, None)
        if current in (None, ""):
            setattr(sample, attribute, value)
        elif str(current).strip() != str(value).strip():
            warnings.append(
                f"{label}: {attribute} is {current!r} in the database but "
                f"{value!r} in the spreadsheet; kept the database value."
            )
    return warnings


def import_field_tables(
    tables: Sequence[SheetTable],
    *,
    dry_run: bool = False,
    raw: dict | None = None,
) -> ChemistryUploadResult:
    """Load the field spreadsheet's two tabs into the NMA chemistry tables.

    ``dry_run`` does every lookup and check and then rolls back, so an operator
    can see exactly what a real run would write.
    """
    sample_info_table, field_params_table = select_tables(tables)
    if sample_info_table is None and field_params_table is None:
        return _result(
            processed=0,
            imported=0,
            validation_errors=[
                "Found neither a ChemistrySampleInfo nor a FieldParameters tab. "
                f"Tabs seen: {', '.join(t.title for t in tables) or 'none'}."
            ],
            raw=raw,
        )

    validation_errors: list[str] = []
    warnings: list[str] = []

    sample_rows: list[dict] = []
    for record in sample_info_table.rows if sample_info_table else []:
        try:
            sample_rows.append(prep_sample_info(record))
        except FieldParamsMappingError as exc:
            validation_errors.append(
                f"{SAMPLE_INFO_TAB} row {record.get(SheetTable.ROW_NUMBER_KEY)}: {exc}"
            )

    param_rows: list[dict] = []
    for record in field_params_table.rows if field_params_table else []:
        try:
            param_rows.append(prep_field_parameters(record))
        except FieldParamsMappingError as exc:
            validation_errors.append(
                f"{FIELD_PARAMETERS_TAB} row "
                f"{record.get(SheetTable.ROW_NUMBER_KEY)}: {exc}"
            )

    processed = len(sample_rows) + len(param_rows)

    samples_created: list[dict] = []
    samples_matched: list[dict] = []
    skipped_parameters: list[dict] = []
    imported = 0

    with session_ctx() as session:
        # Resolve every well up front so an unknown PointID is reported once.
        thing_ids: dict[str, int | None] = {}
        for row in sample_rows:
            pointid = row["well_pointid"]
            if pointid not in thing_ids:
                thing_ids[pointid] = resolve_thing_id(session, pointid)
        for pointid, thing_id in sorted(thing_ids.items()):
            if thing_id is None:
                validation_errors.append(
                    f"WellPointID {pointid}: no matching Thing (well) found"
                )

        if validation_errors:
            return _result(
                processed=processed,
                imported=0,
                validation_errors=validation_errors,
                warnings=warnings,
                raw=raw,
            )

        # sample point id -> the sample it names, for the FieldParameters join.
        samples_by_point: dict[str, NMA_Chemistry_SampleInfo] = {}
        used_suffixes: dict[int, set[int]] = {}

        for row in sample_rows:
            thing_id = thing_ids[row["well_pointid"]]
            label = f"{SAMPLE_INFO_TAB} row {row['row_number']}"

            existing, ambiguity = _find_existing_sample(
                session, thing_id, row["collection_date"]
            )
            if ambiguity:
                validation_errors.append(f"{label}: {row['well_pointid']} {ambiguity}")
                continue

            if existing is not None:
                warnings.extend(_apply_attributes(existing, row["attributes"], label))
                supplied = row["sample_point_id"]
                if supplied and existing.nma_sample_point_id != supplied:
                    warnings.append(
                        f"{label}: spreadsheet calls this sample {supplied}, "
                        f"the database calls it {existing.nma_sample_point_id}; "
                        "matched on well and collection date."
                    )
                samples_by_point[supplied or existing.nma_sample_point_id] = existing
                if existing.nma_sample_point_id:
                    samples_by_point.setdefault(existing.nma_sample_point_id, existing)
                samples_matched.append(
                    {
                        "sample_point_id": existing.nma_sample_point_id,
                        "pointid": row["well_pointid"],
                        "collection_date": row["collection_date"].isoformat(),
                    }
                )
                continue

            base = row["well_pointid"]
            if thing_id not in used_suffixes:
                used_suffixes[thing_id] = _existing_suffix_ints(session, thing_id, base)
            next_int = (
                max(used_suffixes[thing_id]) + 1 if used_suffixes[thing_id] else 1
            )
            used_suffixes[thing_id].add(next_int)
            computed = _int_to_suffix(next_int)
            sample_point_id = f"{base}{computed}"

            supplied_suffix = row["supplied_suffix"]
            if supplied_suffix is not None and supplied_suffix != computed:
                # The computed incrementor wins because it cannot collide with a
                # sample point already in the database, but the disagreement is
                # surfaced so a human can reconcile it.
                warnings.append(
                    f"{label}: spreadsheet supplied sample point "
                    f"{base}{supplied_suffix}, but the next free incrementor is "
                    f"{computed}; loaded as {sample_point_id}."
                )

            sample = NMA_Chemistry_SampleInfo(
                thing_id=thing_id,
                nma_sample_pt_id=uuid.uuid4(),
                nma_sample_point_id=sample_point_id,
                collection_date=row["collection_date"],
                **row["attributes"],
            )
            session.add(sample)
            session.flush()  # assign sample.id for the FK below

            samples_by_point[sample_point_id] = sample
            if row["sample_point_id"]:
                samples_by_point.setdefault(row["sample_point_id"], sample)
            samples_created.append(
                {
                    "sample_point_id": sample_point_id,
                    "pointid": base,
                    "collection_date": row["collection_date"].isoformat(),
                }
            )

        for row in param_rows:
            label = f"{FIELD_PARAMETERS_TAB} row {row['row_number']}"
            point = row["sample_point_id"]
            sample = samples_by_point.get(point)
            if sample is None:
                sample = _lookup_sample_by_point(session, point)
                if sample is not None:
                    samples_by_point[point] = sample
            if sample is None:
                validation_errors.append(
                    f"{label}: no sample {point} -- it is neither in the "
                    f"{SAMPLE_INFO_TAB} tab nor already in the database"
                )
                continue

            existing_symbols = {
                symbol
                for symbol in session.scalars(
                    select(NMA_FieldParameters.field_parameter).where(
                        NMA_FieldParameters.chemistry_sample_info_id == sample.id
                    )
                ).all()
            }

            notes = (
                f"Measured {row['measured_at'].isoformat()}"
                if row["measured_at"]
                else None
            )
            for measurement in row["measurements"]:
                if measurement["symbol"] in existing_symbols:
                    skipped_parameters.append(
                        {
                            "sample_point_id": sample.nma_sample_point_id,
                            "field_parameter": measurement["symbol"],
                        }
                    )
                    continue
                session.add(
                    NMA_FieldParameters(
                        chemistry_sample_info_id=sample.id,
                        nma_global_id=uuid.uuid4(),
                        nma_sample_point_id=sample.nma_sample_point_id,
                        nma_wclab_id=sample.nma_wclab_id,
                        field_parameter=measurement["symbol"],
                        sample_value=measurement["value"],
                        units=measurement["units"],
                        notes=notes,
                        analyses_agency=sample.analyses_agency or DEFAULT_AGENCY,
                    )
                )
                existing_symbols.add(measurement["symbol"])
                imported += 1

        if validation_errors:
            # Abort the whole import: a spreadsheet is never half loaded.
            session.rollback()
            return _result(
                processed=processed,
                imported=0,
                validation_errors=validation_errors,
                warnings=warnings,
                raw=raw,
            )

        if dry_run:
            session.rollback()
        else:
            session.commit()

    return _result(
        processed=processed,
        imported=imported,
        validation_errors=validation_errors,
        warnings=warnings,
        samples_created=samples_created,
        samples_matched=samples_matched,
        skipped_parameters=skipped_parameters,
        dry_run=dry_run,
        raw=raw,
    )


def _lookup_sample_by_point(
    session: Session, sample_point_id: str
) -> NMA_Chemistry_SampleInfo | None:
    """A sample already in the database under this lettered sample point."""
    return session.scalars(
        select(NMA_Chemistry_SampleInfo).where(
            NMA_Chemistry_SampleInfo.nma_sample_point_id == sample_point_id
        )
    ).first()


# --- entrypoints ---------------------------------------------------------------


def _archive_then_read(
    tables: Sequence[SheetTable],
    *,
    source_label: str,
    raw_url: str | None,
) -> tuple[list[SheetTable], dict]:
    """Archive what was read, then read it back and map *that*.

    The round trip is the point: what gets loaded is provably what was kept, and
    the replay path is exercised on every run rather than the first time someone
    needs it.
    """
    extract = archive_tables(
        tables,
        dataset=FIELD_SHEET_DATASET,
        source_label=source_label,
        raw_url=raw_url,
    )
    archived = read_snapshot(FIELD_SHEET_DATASET, extract.load_id, raw_url=extract.url)
    return archived, {
        "load_id": extract.load_id,
        "url": extract.url,
        "dataset": extract.dataset,
        "rows_archived": extract.total_rows,
    }


def sync_field_sheet(
    reference: str | None = None,
    *,
    dry_run: bool = False,
    archive: bool = True,
    raw_url: str | None = None,
) -> ChemistryUploadResult:
    """Ingest the field spreadsheet from Google Drive.

    ``reference`` is a spreadsheet URL or file id; it defaults to
    ``$CHEMISTRY_FIELD_SHEET_ID``. Unless ``archive`` is off, the tabs are
    written to the raw zone first and the load is mapped from that snapshot.
    """
    reference = reference or os.environ.get(SHEET_ID_ENV_VAR, "").strip()
    if not reference:
        raise FieldSheetError(
            f"No spreadsheet given. Pass --sheet-id, or set {SHEET_ID_ENV_VAR}."
        )
    tables = read_google_spreadsheet(reference, tabs=None)

    raw = None
    # A dry run writes nothing anywhere, the archive included -- an operator
    # checking what would happen should not leave a snapshot behind.
    if archive and not dry_run:
        tables, raw = _archive_then_read(
            tables, source_label=reference, raw_url=raw_url
        )
    return import_field_tables(tables, dry_run=dry_run, raw=raw)


def upload_field_export(
    paths: Iterable[Path | str],
    *,
    dry_run: bool = False,
    archive: bool = True,
    raw_url: str | None = None,
) -> ChemistryUploadResult:
    """Ingest downloaded ``.xlsx``/``.csv`` copies of the field spreadsheet.

    More than one path is accepted because a CSV export holds a single tab, so
    the two tabs arrive as two files.
    """
    paths = [Path(path) for path in paths]
    tables: list[SheetTable] = []
    for path in paths:
        tables.extend(read_local_export(path))

    raw = None
    if archive and not dry_run:  # see sync_field_sheet
        tables, raw = _archive_then_read(
            tables,
            source_label=", ".join(path.name for path in paths),
            raw_url=raw_url,
        )
    return import_field_tables(tables, dry_run=dry_run, raw=raw)


def replay_field_sheet(
    load_id: str | None = None,
    *,
    dry_run: bool = False,
    raw_url: str | None = None,
) -> ChemistryUploadResult:
    """Ingest an archived snapshot again, without reading the source.

    This is what a mapping fix is tested against: the same rows the original run
    saw, including whatever was wrong with them. The load is still idempotent,
    so replaying a snapshot that already loaded writes nothing.
    """
    tables = read_snapshot(FIELD_SHEET_DATASET, load_id, raw_url=raw_url)
    resolved = load_id or "latest"
    return import_field_tables(
        tables,
        dry_run=dry_run,
        raw={
            "load_id": resolved,
            "url": raw_zone_url(raw_url),
            "dataset": FIELD_SHEET_DATASET,
            "replayed": True,
        },
    )


# --- result shaping ------------------------------------------------------------


def _result(
    *,
    processed: int,
    imported: int,
    validation_errors: list[str],
    warnings: list[str] | None = None,
    samples_created: list[dict] | None = None,
    samples_matched: list[dict] | None = None,
    skipped_parameters: list[dict] | None = None,
    dry_run: bool = False,
    raw: dict | None = None,
) -> ChemistryUploadResult:
    warnings = warnings or []
    samples_created = samples_created or []
    samples_matched = samples_matched or []
    skipped_parameters = skipped_parameters or []
    rows_with_issues = len(validation_errors) + len(warnings) + len(skipped_parameters)
    payload = {
        "summary": {
            "total_rows_processed": processed,
            "total_rows_imported": imported,
            "validation_errors_or_warnings": rows_with_issues,
            "samples_created": len(samples_created),
            "samples_matched": len(samples_matched),
            "parameters_skipped": len(skipped_parameters),
            "dry_run": dry_run,
        },
        "validation_errors": validation_errors,
        "warnings": warnings,
        "samples_created": samples_created,
        "samples_matched": samples_matched,
        "skipped_parameters": skipped_parameters,
        "raw": raw or {},
    }
    stderr_parts = []
    if validation_errors:
        stderr_parts.append("\n".join(validation_errors))
    if warnings:
        stderr_parts.append("\n".join(warnings))
    return ChemistryUploadResult(
        exit_code=1 if validation_errors else 0,
        stderr="\n".join(stderr_parts),
        payload=payload,
    )


# ============= EOF =============================================
