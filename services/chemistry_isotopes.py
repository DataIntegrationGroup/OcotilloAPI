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
Ingest the ``IsotopeResults`` tab of the AMP chemistry field spreadsheet into
``NMA_MinorTraceChemistry``.

Isotope results are lab data, but not the LIMS ingest's kind: they come from
several labs (NMBGMR, Beta Analytic, the University of Miami Tritium Laboratory),
each reporting in its own format, and someone types them into the same workbook
the crew uses for sample info and field parameters. They arrive weeks or months
after the sample, so this is its own command rather than part of the field-sheet
ingest: sample info and field parameters load as soon as they are entered, and
the isotope tab loads whenever its results come back.

Shape of the tab
----------------
One row per (sample, lab), one column per measurement, with a qualifier and an
uncertainty column beside the measurements that have them. The legacy table is
long, so each populated value cell becomes its own row. See
:data:`ISOTOPE_COLUMNS`.

Results are tied to their sample by the **field sample ID** (``RA-092A``, the
well plus the crew's letter), the same key the field-sheet and LIMS ingests
match on. The tab has no collection date to check a match against, so this
ingest never creates a sample: the sample must already be recorded, by the
field sheet or the LIMS ingest.

Idempotency and failure
-----------------------
A result's identity is its sample, analyte and lab, so two labs reporting the
same analyte for one sample are both kept. A result already stored with the same
value, qualifier, uncertainty and units is skipped, so re-running a sheet loads
nothing twice. One that differs stops the run for review: it may be a lab
re-analysis rather than a typo, and a person decides which value stands. As with
the other chemistry ingests, any failed row aborts the whole import and nothing
is written.

The public entrypoints are :func:`import_isotope_table` (tables in hand),
:func:`sync_isotope_sheet` (Google Drive), :func:`upload_isotope_export` (a
local ``.xlsx``/``.csv`` export) and :func:`replay_isotope_sheet` (an archived
snapshot).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlalchemy import select

from db import NMA_MinorTraceChemistry
from db.engine import session_ctx
from domain.values import to_datetime, to_float
from services.chemistry_field_params import (
    SHEET_ID_ENV_VAR,
    FieldParamsMappingError,
    _cell,
    _find_named_sample,
    _normalize_header,
    _reject_unassigned_pointid,
)
from services.chemistry_field_sheet import (
    FieldSheetError,
    SheetTable,
    read_google_spreadsheet,
    read_local_export,
    write_failed_rows_workbook,
    write_loadable_copy,
)
from services.chemistry_lims import (
    ChemistryUploadResult,
    resolve_thing_id,
    split_pointid,
)
from services.ingest_raw_zone import archive_then_read, raw_zone_url, read_snapshot

ISOTOPE_TAB = "IsotopeResults"

ISOTOPE_DATASET = "chemistry_isotope_results"
"""Raw-zone dataset holding the archived tab.

Kept apart from the field sheet's dataset so ``--replay latest`` on one command
never picks up the other's snapshot.
"""

# Headings that hold the field sample ID. The template calls the column
# WellPointID, but what it holds is the lettered field sample ID.
_SAMPLE_ID_HEADINGS = ("SamplePointID", "WellPointID")

# The legacy column is String(25).
_LAB_ID_MAX = 25

QUALIFIERS = frozenset({"<", ">"})


class IsotopeMappingError(ValueError):
    """A spreadsheet row could not be normalized into isotope results."""


@dataclass(frozen=True)
class IsotopeColumn:
    """One measured column of the ``IsotopeResults`` tab.

    ``analyte`` is the legacy ``LU_MinorTraceAnalyte`` code, and ``units`` the
    legacy abbreviation stored with it (see
    :data:`services.legacy_chemistry.LEGACY_UNITS`) -- normalized here rather
    than taken from the heading, so new rows read the same as the legacy ones.
    ``qualifier`` and ``uncertainty`` name the columns beside it, when it has
    them.
    """

    header: str
    analyte: str
    units: str
    qualifier: str | None = None
    uncertainty: str | None = None


ISOTOPE_COLUMNS: tuple[IsotopeColumn, ...] = (
    IsotopeColumn(
        "Age (years)",
        "C14_years",
        "yrs",
        qualifier="Age_Qualifier",
        uncertainty="Age_Uncertainty (years)",
    ),
    IsotopeColumn(
        "pMC (pmc)",
        "C14",
        "pmc",
        qualifier="pMC_Qualifier",
        uncertainty="pMC_Uncertainty (pmc)",
    ),
    IsotopeColumn("C13r (pm)", "C13r", "pm"),
    IsotopeColumn("H2r (pm)", "H2r", "pm", uncertainty="H2r_Uncertainty (pm)"),
    IsotopeColumn("O18r (pm)", "O18r", "pm", uncertainty="O18r_Uncertainty (pm)"),
    IsotopeColumn("Tritium Units (TU)", "3H", "TU", uncertainty="Tritium_error"),
)

# The labs results are accepted from, as stored in analyses_agency. The lab is
# part of a result's identity, so a misspelled one ("Beta Analytics") would be
# stored beside the real result instead of matching it. Add a lab here when one
# starts reporting.
ISOTOPE_LABS: tuple[str, ...] = (
    "NMBGMR",
    "Beta Analytic",
    "University of Miami Tritium Laboratory",
)


def _lab_key(value: Any) -> str:
    """A lab name for comparing: casefolded, with spacing collapsed."""
    return " ".join(str(value or "").split()).casefold()


_LABS_BY_KEY = {_lab_key(lab): lab for lab in ISOTOPE_LABS}

_VALUE_HEADINGS = frozenset(_normalize_header(c.header) for c in ISOTOPE_COLUMNS)

# Every heading this ingest reads. Anything else on the tab is skipped, and the
# report names it: a lab reporting a new measurement gets a new column, and
# without a warning its results would never load and nobody would know.
_KNOWN_HEADINGS = frozenset(
    _normalize_header(heading)
    for heading in (
        *_SAMPLE_ID_HEADINGS,
        "AnalysisLab",
        "AnalysisDate",
        "ChemistryLabID",
        *(
            heading
            for column in ISOTOPE_COLUMNS
            for heading in (column.header, column.qualifier, column.uncertainty)
            if heading
        ),
    )
)


# --- row normalization ---------------------------------------------------------


def _lab_id(value: Any) -> str | None:
    """A lab's own sample id, as text.

    Lab ids are names, not numbers -- other labs send ``885-44878-1`` and
    ``260404-01`` -- but a sheet cell holding only digits reads back as a float,
    which must not be stored as ``765646.0``.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text:
        return None
    if len(text) > _LAB_ID_MAX:
        raise IsotopeMappingError(
            f"ChemistryLabID {text!r} is longer than {_LAB_ID_MAX} characters, "
            "which is all the column holds"
        )
    return text


def _filled(value: Any) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())


def prep_isotope_row(record: dict) -> dict:
    """Normalize one ``IsotopeResults`` row into its results.

    Raises :class:`IsotopeMappingError` when the row cannot be loaded. A row
    with no result cells at all comes back with an empty ``results`` list: it
    writes nothing, but it is not wrong.
    """
    row_number = record.get(SheetTable.ROW_NUMBER_KEY)

    # Read the result cells first: a row that holds none is reported as empty
    # whatever else it says, since there is nothing in it to load.
    cells = []
    for column in ISOTOPE_COLUMNS:
        value = _cell(record, column.header)
        qualifier = _cell(record, column.qualifier) if column.qualifier else None
        uncertainty = _cell(record, column.uncertainty) if column.uncertainty else None
        if value is None and qualifier is None and uncertainty is None:
            continue
        cells.append((column, value, qualifier, uncertainty))

    sample_point_id = _cell(record, *_SAMPLE_ID_HEADINGS)
    if not cells:
        return {
            "row_number": row_number,
            "sample_point_id": (
                str(sample_point_id).strip() if sample_point_id else None
            ),
            "results": [],
        }

    if not sample_point_id:
        raise IsotopeMappingError("Missing SamplePointID")
    sample_point_id = str(sample_point_id).strip()
    try:
        _reject_unassigned_pointid(sample_point_id)
    except FieldParamsMappingError as exc:
        raise IsotopeMappingError(str(exc)) from exc
    # The field sample ID is how a result finds its sample. Without the crew's
    # letter it names the well, not one of the well's samples.
    base, letter = split_pointid(sample_point_id)
    if letter is None:
        raise IsotopeMappingError(
            f"SamplePointID {sample_point_id!r} has no sample letter; use the "
            f"field sample ID (for example {sample_point_id}A)"
        )

    lab_cell = _cell(record, "AnalysisLab")
    if lab_cell is None:
        raise IsotopeMappingError(f"{sample_point_id}: Missing AnalysisLab")
    lab = _LABS_BY_KEY.get(_lab_key(lab_cell))
    if lab is None:
        allowed = ", ".join(repr(name) for name in ISOTOPE_LABS)
        raise IsotopeMappingError(
            f"{sample_point_id}: AnalysisLab {lab_cell!r} is not a known lab; use "
            f"one of {allowed}, or have engineering add it to ISOTOPE_LABS"
        )

    analysis_cell = _cell(record, "AnalysisDate")
    analysis_date = to_datetime(analysis_cell)
    if analysis_cell is not None and analysis_date is None:
        raise IsotopeMappingError(
            f"{sample_point_id}: AnalysisDate {analysis_cell!r} is not a "
            "recognizable date"
        )

    lab_id = _lab_id(_cell(record, "ChemistryLabID"))

    results = []
    problems = []
    for column, value, qualifier, uncertainty in cells:
        if value is None:
            # A qualifier or uncertainty with no value beside it qualifies
            # nothing; it is most likely a value typed into the wrong column.
            filled = [
                heading
                for heading, cell in (
                    (column.qualifier, qualifier),
                    (column.uncertainty, uncertainty),
                )
                if cell is not None
            ]
            problems.append(f"{' and '.join(filled)} filled but {column.header} blank")
            continue

        # Strict: the qualifier has its own column, so a value carrying one is
        # a typing mistake, not a result to strip and promote.
        number = to_float(value)
        if number is None:
            problems.append(f"{column.header}={value!r} is not a number")
            continue

        symbol = None
        if qualifier is not None:
            symbol = str(qualifier).strip()
            if symbol not in QUALIFIERS:
                problems.append(
                    f"{column.qualifier}={qualifier!r} is not one of "
                    f"{', '.join(sorted(QUALIFIERS))}"
                )
                continue

        error = None
        if uncertainty is not None:
            error = to_float(uncertainty)
            if error is None:
                problems.append(f"{column.uncertainty}={uncertainty!r} is not a number")
                continue

        results.append(
            {
                "analyte": column.analyte,
                "units": column.units,
                "value": number,
                "symbol": symbol,
                "uncertainty": error,
            }
        )

    if problems:
        raise IsotopeMappingError(f"{sample_point_id}: {'; '.join(problems)}")

    return {
        "row_number": row_number,
        "sample_point_id": sample_point_id,
        "well_pointid": base,
        "lab": lab,
        "analysis_date": analysis_date,
        "lab_id": lab_id,
        "results": results,
    }


# --- table selection -----------------------------------------------------------


def _looks_like_isotope_results(table: SheetTable) -> bool:
    keys = {_normalize_header(h) for h in table.header}
    has_sample_id = bool(keys & {_normalize_header(h) for h in _SAMPLE_ID_HEADINGS})
    return has_sample_id and "analysislab" in keys and bool(keys & _VALUE_HEADINGS)


def select_isotope_table(tables: Sequence[SheetTable]) -> SheetTable | None:
    """Pick the ``IsotopeResults`` tab out of a workbook.

    The tab title is matched first, then the header row, so a renamed tab is
    still found and a CSV export of the tab (whose "title" is a filename) works
    the same way. ``GenChemResults`` shares the identifying columns but none of
    the isotope ones, so it is never mistaken for this tab.
    """
    for table in tables:
        if _normalize_header(table.title) == _normalize_header(ISOTOPE_TAB):
            return table
    for table in tables:
        if _looks_like_isotope_results(table):
            return table
    return None


# --- persistence ---------------------------------------------------------------


def _same_number(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def _same_result(a: dict, b: dict) -> bool:
    """Whether two of the sheet's results say the same thing."""
    return (
        _same_number(a["value"], b["value"])
        and a["symbol"] == b["symbol"]
        and a["units"] == b["units"]
        and _same_number(a["uncertainty"], b["uncertainty"])
    )


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _differences(stored: NMA_MinorTraceChemistry, result: dict) -> list[str]:
    """How a stored result differs from the sheet's, in words."""
    differences = []
    if not _same_number(stored.sample_value, result["value"]):
        differences.append(
            f"value {stored.sample_value!r} stored, {result['value']!r} here"
        )
    if _text(stored.symbol) != result["symbol"]:
        differences.append(
            f"qualifier {_text(stored.symbol)!r} stored, {result['symbol']!r} here"
        )
    if not _same_number(stored.uncertainty, result["uncertainty"]):
        differences.append(
            f"uncertainty {stored.uncertainty!r} stored, "
            f"{result['uncertainty']!r} here"
        )
    if _text(stored.units) != result["units"]:
        differences.append(
            f"units {_text(stored.units)!r} stored, {result['units']!r} here"
        )
    return differences


def import_isotope_table(
    tables: Sequence[SheetTable],
    *,
    dry_run: bool = False,
    raw: dict | None = None,
) -> ChemistryUploadResult:
    """Load the ``IsotopeResults`` tab into ``NMA_MinorTraceChemistry``.

    ``dry_run`` does every lookup and check and then rolls back, so an operator
    can see exactly what a real run would write.
    """
    table = select_isotope_table(tables)
    if table is None:
        return _result(
            processed=0,
            imported=0,
            validation_errors=[
                f"Found no {ISOTOPE_TAB} tab. Tabs seen: "
                f"{', '.join(t.title for t in tables) or 'none'}."
            ],
            raw=raw,
        )

    validation_errors: list[str] = []
    warnings: list[str] = []
    unread = [
        heading
        for heading in table.header
        if heading and _normalize_header(heading) not in _KNOWN_HEADINGS
    ]
    if unread:
        warnings.append(
            f"{ISOTOPE_TAB}: this ingest doesn't read the column(s) "
            f"{', '.join(repr(h) for h in unread)}, so nothing in them was "
            "loaded. If they hold results, ask engineering to add them to "
            "ISOTOPE_COLUMNS."
        )
    # Every row that stops the run, as data: the CLI writes these out, and one
    # pass has to find them all, so no stage stops at the first failure.
    failed_rows: list[dict] = []
    failed_row_numbers: set[int | None] = set()

    def fail(row, reason, *, point=None):
        failed_rows.append(
            {
                "tab": ISOTOPE_TAB,
                "row": row,
                "sample_point_id": point,
                "reason": reason,
                "caused_by": None,
            }
        )
        failed_row_numbers.add(row)
        validation_errors.append(f"{ISOTOPE_TAB} row {row}: {reason}")

    rows: list[dict] = []
    empty_rows: list[dict] = []
    for record in table.rows:
        try:
            row = prep_isotope_row(record)
        except IsotopeMappingError as exc:
            point = _cell(record, *_SAMPLE_ID_HEADINGS)
            fail(
                record.get(SheetTable.ROW_NUMBER_KEY),
                str(exc),
                point=str(point).strip() if point else None,
            )
            continue
        if row["results"]:
            rows.append(row)
        else:
            empty_rows.append(
                {
                    "row": row["row_number"],
                    "sample_point_id": row["sample_point_id"],
                    "analysis_lab": _cell(record, "AnalysisLab"),
                }
            )

    processed = len(table.rows)

    # One result per (sample, analyte, lab). The same one on two rows is either
    # a harmless repeat, which loads once, or two different answers, where
    # nothing says which row is right -- so every row involved fails.
    seen: dict[tuple[str, str, str], tuple[dict, dict]] = {}
    conflicts: dict[int | None, list[str]] = {}
    for row in rows:
        kept = []
        for result in row["results"]:
            key = (row["sample_point_id"], result["analyte"], row["lab"])
            if key not in seen:
                seen[key] = (row, result)
                kept.append(result)
                continue
            first_row, first = seen[key]
            label = f"{key[0]} {key[1]} from {key[2]}"
            if _same_result(first, result):
                warnings.append(
                    f"{ISOTOPE_TAB} row {row['row_number']}: {label} repeats row "
                    f"{first_row['row_number']}; loaded once."
                )
                continue
            for this, other in ((row, first_row), (first_row, row)):
                conflicts.setdefault(this["row_number"], []).append(
                    f"{label} is also on row {other['row_number']} with a different "
                    "result; delete the wrong one"
                )
        row["results"] = kept
    for row_number, reasons in conflicts.items():
        point = next(
            r["sample_point_id"] for r in rows if r["row_number"] == row_number
        )
        fail(row_number, "; ".join(reasons), point=point)
    rows = [r for r in rows if r["row_number"] not in failed_row_numbers]

    imported = 0
    loaded: list[dict] = []
    skipped_results: list[dict] = []

    with session_ctx() as session:
        thing_ids: dict[str, int | None] = {}
        for row in rows:
            point = row["sample_point_id"]
            base = row["well_pointid"]
            if base not in thing_ids:
                thing_ids[base] = resolve_thing_id(session, base)
            thing_id = thing_ids[base]
            if thing_id is None:
                fail(
                    row["row_number"],
                    f"{point}: no matching Thing (well) {base} found",
                    point=point,
                )
                continue

            sample, problem = _find_named_sample(session, thing_id, point)
            if problem:
                fail(row["row_number"], f"{base} {problem}", point=point)
                continue
            if sample is None:
                # The tab has no collection date, so a sample made from it could
                # never be matched by the field sheet or the LIMS ingest, which
                # both require one. The sample comes from ChemistrySampleInfo.
                fail(
                    row["row_number"],
                    f"no sample {point} -- load its ChemistrySampleInfo row "
                    "with `oco water-chemistry field-upload` first",
                    point=point,
                )
                continue

            analysis_date = row["analysis_date"]
            if sample.collection_date is None:
                warnings.append(
                    f"{ISOTOPE_TAB} row {row['row_number']}: {point} has no "
                    "collection date, so these results have no date unless "
                    "their analysis date gives one."
                )
            elif (
                analysis_date is not None
                and analysis_date.date() < sample.collection_date.date()
            ):
                fail(
                    row["row_number"],
                    f"{point} was collected on "
                    f"{sample.collection_date.date().isoformat()}, but "
                    f"{row['lab']} analysed it on "
                    f"{analysis_date.date().isoformat()}. Correct whichever "
                    "date is wrong, or the SamplePointID if it names the wrong "
                    "sample.",
                    point=point,
                )
                continue

            stored_by_analyte: dict[str, list[NMA_MinorTraceChemistry]] = {}
            for stored in session.scalars(
                select(NMA_MinorTraceChemistry).where(
                    NMA_MinorTraceChemistry.chemistry_sample_info_id == sample.id,
                    NMA_MinorTraceChemistry.analyte.in_(
                        [r["analyte"] for r in row["results"]]
                    ),
                )
            ).all():
                if _lab_key(stored.analyses_agency) == _lab_key(row["lab"]):
                    stored_by_analyte.setdefault(stored.analyte, []).append(stored)

            new = []
            problems = []
            for result in row["results"]:
                stored = stored_by_analyte.get(result["analyte"], [])
                if len(stored) > 1:
                    problems.append(
                        f"{result['analyte']} from {row['lab']} is stored "
                        f"{len(stored)} times for {point}; cannot tell which "
                        "one this is"
                    )
                elif stored:
                    differences = _differences(stored[0], result)
                    if differences:
                        # Possibly a re-analysis the lab was asked for. Either
                        # way a person decides which value stands, so the stored
                        # one is never overwritten from here.
                        problems.append(
                            f"{result['analyte']} from {row['lab']} is already "
                            f"stored for {point} and differs: "
                            f"{', '.join(differences)}. Review it with the lab; "
                            "a stored result is corrected by hand"
                        )
                    else:
                        skipped_results.append(
                            {
                                "sample_point_id": point,
                                "analyte": result["analyte"],
                                "analysis_lab": row["lab"],
                            }
                        )
                else:
                    new.append(result)
            if problems:
                fail(row["row_number"], "; ".join(problems), point=point)
                continue

            for result in new:
                # Only chemistry_sample_info_id ties the result to its sample.
                # The nma_* audit columns (GlobalID, the sample's legacy UUID)
                # hold NM_Aquifer's values and stay empty on new rows.
                session.add(
                    NMA_MinorTraceChemistry(
                        chemistry_sample_info_id=sample.id,
                        nma_sample_point_id=sample.nma_sample_point_id,
                        analyte=result["analyte"],
                        symbol=result["symbol"],
                        sample_value=result["value"],
                        units=result["units"],
                        uncertainty=result["uncertainty"],
                        analysis_date=(analysis_date.date() if analysis_date else None),
                        analyses_agency=row["lab"],
                        # The lab's id goes on its own results. The sample's
                        # single nma_WCLab_ID belongs to the LIMS ingest, which
                        # only adopts a sample whose slot is still empty.
                        nma_wclab_id=row["lab_id"],
                    )
                )
                loaded.append(
                    {
                        "sample_point_id": point,
                        "analyte": result["analyte"],
                        "analysis_lab": row["lab"],
                    }
                )
                imported += 1

        if validation_errors:
            # Abort the whole import: a spreadsheet is never half loaded.
            session.rollback()
            return _result(
                processed=processed,
                imported=0,
                validation_errors=validation_errors,
                warnings=warnings,
                failed_rows=failed_rows,
                empty_rows=empty_rows,
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
        failed_rows=failed_rows,
        loaded=loaded,
        skipped_results=skipped_results,
        empty_rows=empty_rows,
        dry_run=dry_run,
        raw=raw,
    )


# --- entrypoints ---------------------------------------------------------------


def _archive_isotope_table(
    tables: Sequence[SheetTable], *, source_label: str, raw_url: str | None
) -> tuple[list[SheetTable], dict | None]:
    """Archive the isotope tab alone, then map from the archive.

    Only the tab this ingest reads is kept: the field-sheet ingest archives its
    own tabs under its own dataset. A workbook with no isotope tab archives
    nothing, and the import reports the missing tab.
    """
    table = select_isotope_table(tables)
    if table is None:
        return list(tables), None
    return archive_then_read(
        [table],
        dataset=ISOTOPE_DATASET,
        source_label=source_label,
        raw_url=raw_url,
    )


def sync_isotope_sheet(
    reference: str | None = None,
    *,
    dry_run: bool = False,
    archive: bool = True,
    raw_url: str | None = None,
    failed_rows_path: Path | str | None = None,
) -> ChemistryUploadResult:
    """Ingest the ``IsotopeResults`` tab from Google Drive.

    ``reference`` is a spreadsheet URL or file id; it defaults to
    ``$CHEMISTRY_FIELD_SHEET_ID``, since the tab lives in the field
    spreadsheet. Unless ``archive`` is off, the tab is written to the raw zone
    first and the load is mapped from that snapshot.
    """
    reference = reference or os.environ.get(SHEET_ID_ENV_VAR, "").strip()
    if not reference:
        raise FieldSheetError(
            f"No spreadsheet given. Pass --sheet-id, or set {SHEET_ID_ENV_VAR}."
        )
    tables = read_google_spreadsheet(reference, tabs=None)
    read_tables = tables

    raw = None
    # A dry run writes nothing anywhere, the archive included -- an operator
    # checking what would happen should not leave a snapshot behind.
    if archive and not dry_run:
        tables, raw = _archive_isotope_table(
            tables, source_label=reference, raw_url=raw_url
        )
    result = import_isotope_table(tables, dry_run=dry_run, raw=raw)
    return _write_reports(result, read_tables, failed_rows_path=failed_rows_path)


def upload_isotope_export(
    paths: Iterable[Path | str],
    *,
    dry_run: bool = False,
    archive: bool = True,
    raw_url: str | None = None,
    failed_rows_path: Path | str | None = None,
    loadable_path: Path | str | None = None,
) -> ChemistryUploadResult:
    """Ingest a downloaded ``.xlsx`` (or a ``.csv`` of the one tab).

    ``failed_rows_path`` and ``loadable_path`` write the reports described in
    :func:`_write_reports`; a loadable copy is made from the export itself, so
    it needs a single ``.xlsx``.
    """
    paths = [Path(path) for path in paths]
    if loadable_path and (len(paths) != 1 or paths[0].suffix.lower() != ".xlsx"):
        # Checked before reading, so a mistyped command fails before a run.
        raise FieldSheetError(
            "A loadable copy is made from the export itself, so it needs a "
            "single .xlsx file."
        )
    tables: list[SheetTable] = []
    for path in paths:
        tables.extend(read_local_export(path))
    read_tables = tables

    raw = None
    if archive and not dry_run:  # see sync_isotope_sheet
        tables, raw = _archive_isotope_table(
            tables,
            source_label=", ".join(path.name for path in paths),
            raw_url=raw_url,
        )
    result = import_isotope_table(tables, dry_run=dry_run, raw=raw)
    return _write_reports(
        result,
        read_tables,
        failed_rows_path=failed_rows_path,
        loadable=(paths[0], loadable_path) if loadable_path else None,
    )


def replay_isotope_sheet(
    load_id: str | None = None,
    *,
    dry_run: bool = False,
    raw_url: str | None = None,
    failed_rows_path: Path | str | None = None,
) -> ChemistryUploadResult:
    """Ingest an archived snapshot again, without reading the source.

    The load is idempotent, so replaying a snapshot that already loaded writes
    nothing.
    """
    tables = read_snapshot(ISOTOPE_DATASET, load_id, raw_url=raw_url)
    result = import_isotope_table(
        tables,
        dry_run=dry_run,
        raw={
            "load_id": load_id or "latest",
            "url": raw_zone_url(raw_url),
            "dataset": ISOTOPE_DATASET,
            "replayed": True,
        },
    )
    return _write_reports(result, tables, failed_rows_path=failed_rows_path)


def _write_reports(
    result: ChemistryUploadResult,
    tables: Sequence[SheetTable],
    *,
    failed_rows_path: Path | str | None = None,
    loadable: tuple[Path, Path | str] | None = None,
) -> ChemistryUploadResult:
    """Write the failed row workbook and loadable copy, when a row failed.

    The same two reports as the field sheet's, for this one tab. A failure
    fails the whole sheet row, so the loadable copy holds back every result on
    it until it is fixed.
    """
    failed = result.payload.get("failed_rows", [])
    table = select_isotope_table(tables)
    by_tab = {ISOTOPE_TAB: table} if table is not None else {}
    reports: dict[str, str | None] = {}
    if failed_rows_path:
        reports["failed_rows"] = (
            str(write_failed_rows_workbook(by_tab, failed, failed_rows_path))
            if failed
            else None
        )
    if loadable:
        source, path = loadable
        titles = {tab: t.title for tab, t in by_tab.items()}
        reports["loadable"] = (
            str(write_loadable_copy(source, titles, failed, path)) if failed else None
        )
    result.payload["reports"] = reports
    return result


# --- result shaping ------------------------------------------------------------


def _result(
    *,
    processed: int,
    imported: int,
    validation_errors: list[str],
    warnings: list[str] | None = None,
    failed_rows: list[dict] | None = None,
    loaded: list[dict] | None = None,
    skipped_results: list[dict] | None = None,
    empty_rows: list[dict] | None = None,
    dry_run: bool = False,
    raw: dict | None = None,
) -> ChemistryUploadResult:
    warnings = warnings or []
    failed_rows = failed_rows or []
    loaded = loaded or []
    skipped_results = skipped_results or []
    empty_rows = empty_rows or []
    rows_with_issues = len(validation_errors) + len(warnings)
    payload = {
        "summary": {
            "total_rows_processed": processed,
            "total_rows_imported": imported,
            "validation_errors_or_warnings": rows_with_issues,
            "results_skipped": len(skipped_results),
            "rows_empty": len(empty_rows),
            "rows_failed": len(failed_rows),
            "samples_with_results": len({entry["sample_point_id"] for entry in loaded}),
            "dry_run": dry_run,
        },
        "validation_errors": validation_errors,
        "failed_rows": failed_rows,
        "warnings": warnings,
        "loaded": loaded,
        "skipped_results": skipped_results,
        "empty_rows": empty_rows,
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
