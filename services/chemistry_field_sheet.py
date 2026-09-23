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
Read the AMP chemistry field spreadsheet -- sample info and field parameters --
from Google Drive or from a local export.

Two source shapes reach the same reader:

* A **Google Sheets** document, read through the Sheets API by tab title (or by
  the ``gid`` in the document's URL).
* An **.xlsx workbook uploaded to Drive**, which the Sheets editor opens but the
  Sheets API refuses. Those are downloaded as bytes and read with ``openpyxl``,
  the same path :mod:`services.chemistry_drive` already uses for LIMS
  workbooks. A Drive file id of fewer than 44 characters is usually one of
  these; the mime type reported by Drive is what actually decides.

A local ``.csv`` or ``.xlsx`` export is read directly, so an engineer without
Drive access to the sheet can still run the ingest against a downloaded copy.

Every reader returns :class:`SheetTable` objects: a tab title, its header row,
and one dict per data row carrying the worksheet row number, so a validation
error can name the row the operator sees in the spreadsheet.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from services.chemistry_drive import (
    ChemistryDriveConfigError,
    XLSX_MIME,
    download_drive_file,
    google_credentials,
)

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"

# Both /spreadsheets/d/<id>/ and a bare id are accepted, so an operator can
# paste the browser URL straight from the sheet they are looking at.
_SHEET_ID_RE = re.compile(r"/spreadsheets/d/(?P<id>[A-Za-z0-9_-]+)")
_GID_RE = re.compile(r"[#&?]gid=(?P<gid>\d+)")


class FieldSheetError(Exception):
    """The spreadsheet could not be read (missing tab, unreadable file)."""


@dataclass(frozen=True)
class SheetReference:
    """A spreadsheet to read, and optionally which tab of it."""

    spreadsheet_id: str
    gid: int | None = None


@dataclass
class SheetTable:
    """One tab: its title, header row, and data rows keyed by header."""

    title: str
    header: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)

    ROW_NUMBER_KEY = "__row_number__"

    def row_number(self, row: dict) -> int | None:
        """The worksheet row number this record came from, if known."""
        return row.get(self.ROW_NUMBER_KEY)


def parse_sheet_reference(value: str) -> SheetReference:
    """Turn a spreadsheet URL or bare file id into a :class:`SheetReference`."""
    value = (value or "").strip()
    if not value:
        raise FieldSheetError("No spreadsheet id or URL given.")

    match = _SHEET_ID_RE.search(value)
    spreadsheet_id = match.group("id") if match else value

    gid_match = _GID_RE.search(value)
    gid = int(gid_match.group("gid")) if gid_match else None

    if not re.fullmatch(r"[A-Za-z0-9_-]+", spreadsheet_id):
        raise FieldSheetError(
            f"{value!r} is not a spreadsheet id or a Google Sheets URL."
        )
    return SheetReference(spreadsheet_id=spreadsheet_id, gid=gid)


# --- Google-hosted sources -----------------------------------------------------


@lru_cache(maxsize=1)
def get_sheets_service():
    from googleapiclient.discovery import build

    return build(
        "sheets",
        "v4",
        credentials=google_credentials(SHEETS_SCOPES),
        cache_discovery=False,
    )


@lru_cache(maxsize=1)
def _get_drive_service():
    from googleapiclient.discovery import build

    return build(
        "drive",
        "v3",
        credentials=google_credentials(SHEETS_SCOPES),
        cache_discovery=False,
    )


def describe_spreadsheet(spreadsheet_id: str, drive_service=None) -> dict:
    """Drive metadata for the spreadsheet, with a readable access failure.

    Drive answers ``notFound`` for a file the caller cannot see, so an unshared
    sheet is otherwise indistinguishable from a wrong id.
    """
    from googleapiclient.errors import HttpError

    drive_service = drive_service or _get_drive_service()
    try:
        return (
            drive_service.files()
            .get(
                fileId=spreadsheet_id,
                fields="id, name, mimeType, modifiedTime, md5Checksum",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        if exc.resp.status in (403, 404):
            raise ChemistryDriveConfigError(
                f"Spreadsheet {spreadsheet_id!r} is not accessible. Check the id, "
                "and that the spreadsheet is shared with the account running the "
                "ingest."
            ) from exc
        raise


def read_google_spreadsheet(
    reference: SheetReference | str,
    *,
    tabs: Iterable[str] | None = None,
    drive_service=None,
    sheets_service=None,
) -> list[SheetTable]:
    """Read a Drive-hosted spreadsheet into :class:`SheetTable` objects.

    ``tabs`` selects tabs by title; without it every tab is read, except that a
    ``gid`` carried by the reference narrows a native Google Sheet to the single
    tab the operator had open.
    """
    if isinstance(reference, str):
        reference = parse_sheet_reference(reference)

    meta = describe_spreadsheet(reference.spreadsheet_id, drive_service=drive_service)
    mime = meta.get("mimeType")

    if mime == GOOGLE_SHEET_MIME:
        return _read_native_sheet(
            reference, tabs=tabs, sheets_service=sheets_service or get_sheets_service()
        )

    if mime == XLSX_MIME:
        # An .xlsx living in Drive: the Sheets API rejects it, so read the bytes.
        content = download_drive_file(
            reference.spreadsheet_id, service=drive_service or _get_drive_service()
        )
        return read_xlsx_bytes(content, tabs=tabs)

    raise FieldSheetError(
        f"{meta.get('name', reference.spreadsheet_id)!r} is a {mime!r} file, "
        "which is neither a Google Sheet nor an .xlsx workbook."
    )


def _read_native_sheet(
    reference: SheetReference, *, tabs: Iterable[str] | None, sheets_service
) -> list[SheetTable]:
    metadata = (
        sheets_service.spreadsheets()
        .get(
            spreadsheetId=reference.spreadsheet_id,
            fields="sheets(properties(sheetId,title,index))",
        )
        .execute()
    )
    properties = [s["properties"] for s in metadata.get("sheets", [])]
    titles = [p["title"] for p in properties]

    wanted = _select_titles(titles, tabs)
    if wanted is None:
        if reference.gid is not None:
            by_gid = [p["title"] for p in properties if p["sheetId"] == reference.gid]
            if not by_gid:
                raise FieldSheetError(
                    f"No tab with gid={reference.gid} in this spreadsheet. "
                    f"Tabs: {', '.join(titles) or 'none'}."
                )
            wanted = by_gid
        else:
            wanted = titles

    tables = []
    for title in wanted:
        values = (
            sheets_service.spreadsheets()
            .values()
            # UNFORMATTED_VALUE keeps numbers numeric; a date arrives as a
            # serial number, which the row parser converts.
            .get(
                spreadsheetId=reference.spreadsheet_id,
                range=f"'{title}'",
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            )
            .execute()
        ).get("values", [])
        tables.append(_table_from_values(title, values))
    return tables


# --- local and byte sources ----------------------------------------------------


def read_local_export(
    path: Path | str, *, tabs: Iterable[str] | None = None
) -> list[SheetTable]:
    """Read a downloaded ``.csv`` or ``.xlsx`` copy of the field spreadsheet."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        # A CSV holds a single tab; its name is the file stem so messages read
        # the same whichever source was used.
        text = path.read_bytes().decode("utf-8-sig")
        values = [list(row) for row in csv.reader(io.StringIO(text))]
        return [_table_from_values(path.stem, values)]
    if suffix == ".xlsx":
        return read_xlsx_bytes(path.read_bytes(), tabs=tabs)
    raise FieldSheetError(
        f"Unsupported file type {suffix!r}. Export the spreadsheet as .csv or .xlsx."
    )


def read_xlsx_bytes(
    content: bytes, *, tabs: Iterable[str] | None = None
) -> list[SheetTable]:
    """Read ``.xlsx`` bytes into :class:`SheetTable` objects."""
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(
            filename=io.BytesIO(content), read_only=True, data_only=True
        )
    except Exception as exc:  # openpyxl raises a variety of parse errors
        raise FieldSheetError(f"Could not read workbook: {exc}") from exc

    try:
        titles = workbook.sheetnames
        wanted = _select_titles(titles, tabs) or titles
        tables = []
        for title in wanted:
            worksheet = workbook[title]
            values = [list(row) for row in worksheet.iter_rows(values_only=True)]
            tables.append(_table_from_values(title, values))
        return tables
    finally:
        workbook.close()


# --- shared helpers ------------------------------------------------------------


def _select_titles(titles: list[str], tabs: Iterable[str] | None) -> list[str] | None:
    """Resolve requested tab names against the tabs a spreadsheet actually has.

    Matching ignores case and surrounding whitespace, because the same tab is
    written "Field Parameters", "field parameters", and "Field Parameters "
    across copies of the template.
    """
    if tabs is None:
        return None

    by_key = {_normalize(t): t for t in titles}
    resolved = []
    missing = []
    for wanted in tabs:
        actual = by_key.get(_normalize(wanted))
        if actual is None:
            missing.append(wanted)
        else:
            resolved.append(actual)
    if missing:
        raise FieldSheetError(
            f"Tab(s) not found: {', '.join(repr(m) for m in missing)}. "
            f"Tabs present: {', '.join(titles) or 'none'}."
        )
    return resolved


def _normalize(value: Any) -> str:
    return str(value or "").strip().casefold()


def _table_from_values(title: str, values: list[list[Any]]) -> SheetTable:
    """Build a table from raw row values, treating the first row as the header.

    Rows shorter than the header are padded, because both the Sheets API and a
    CSV export drop trailing empty cells.
    """
    if not values:
        return SheetTable(title=title)

    header = [str(cell).strip() if cell is not None else "" for cell in values[0]]
    rows = []
    for offset, raw in enumerate(values[1:]):
        if all(cell is None or str(cell).strip() == "" for cell in raw):
            continue
        padded = list(raw) + [None] * (len(header) - len(raw))
        record = dict(zip(header, padded))
        # +2: worksheet row 1 is the header and enumerate is 0-based, so this is
        # the row number the operator sees in the spreadsheet.
        record[SheetTable.ROW_NUMBER_KEY] = offset + 2
        rows.append(record)
    return SheetTable(title=title, header=header, rows=rows)


# ============= EOF =============================================
