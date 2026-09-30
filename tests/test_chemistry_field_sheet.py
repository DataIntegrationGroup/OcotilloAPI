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
"""Tests for reading the chemistry field spreadsheet
(services/chemistry_field_sheet.py)."""

import io

import pytest
from openpyxl import Workbook

from services import chemistry_field_sheet
from services.chemistry_drive import XLSX_MIME
from services.chemistry_field_sheet import (
    GOOGLE_SHEET_MIME,
    FieldSheetError,
    SheetTable,
    parse_sheet_reference,
    read_google_spreadsheet,
    read_local_export,
    read_xlsx_bytes,
    write_failed_rows_workbook,
    write_loadable_copy,
)

SHEET_ID = "1VerJIFpytUZJwyAUa6HeyqUEFZsWdUG1"


def _xlsx_bytes(tabs: dict[str, list[list]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in tabs.items():
        worksheet = workbook.create_sheet(title=title)
        for row in rows:
            worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# --- reference parsing ---------------------------------------------------------


def test_parse_reference_from_url_keeps_gid():
    reference = parse_sheet_reference(
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid=1878349160#gid=1878349160"
    )
    assert reference.spreadsheet_id == SHEET_ID
    assert reference.gid == 1878349160


def test_parse_reference_from_bare_id():
    reference = parse_sheet_reference(SHEET_ID)
    assert reference.spreadsheet_id == SHEET_ID
    assert reference.gid is None


@pytest.mark.parametrize("value", ["", "   ", "https://example.com/not a sheet"])
def test_parse_reference_rejects_junk(value):
    with pytest.raises(FieldSheetError):
        parse_sheet_reference(value)


# --- row shaping ---------------------------------------------------------------


def test_rows_carry_worksheet_row_numbers_and_skip_blanks():
    content = _xlsx_bytes(
        {
            "Sample Info": [
                ["PointID", "CollectionDate"],
                ["MG-030", "2026-01-05"],
                [None, None],
                ["MG-031", "2026-01-06"],
            ]
        }
    )
    (table,) = read_xlsx_bytes(content)

    assert table.title == "Sample Info"
    assert table.header == ["PointID", "CollectionDate"]
    assert [r["PointID"] for r in table.rows] == ["MG-030", "MG-031"]
    # Row 3 is blank and dropped, so the second record is worksheet row 4.
    assert [table.row_number(r) for r in table.rows] == [2, 4]


def test_short_rows_are_padded_to_the_header():
    content = _xlsx_bytes(
        {"Sample Info": [["PointID", "CollectionDate", "Notes"], ["MG-030"]]}
    )
    (table,) = read_xlsx_bytes(content)

    assert table.rows[0]["CollectionDate"] is None
    assert table.rows[0]["Notes"] is None


def test_empty_tab_yields_no_rows():
    (table,) = read_xlsx_bytes(_xlsx_bytes({"Sample Info": []}))
    assert table.header == []
    assert table.rows == []


# --- tab selection -------------------------------------------------------------


def test_tab_selection_ignores_case_and_whitespace():
    content = _xlsx_bytes(
        {
            "Sample Info": [["PointID"], ["MG-030"]],
            "Field Parameters": [["PointID"], ["MG-030"]],
        }
    )
    (table,) = read_xlsx_bytes(content, tabs=["  field parameters "])
    assert table.title == "Field Parameters"


def test_missing_tab_names_the_tabs_present():
    content = _xlsx_bytes({"Sample Info": [["PointID"], ["MG-030"]]})
    with pytest.raises(FieldSheetError) as exc:
        read_xlsx_bytes(content, tabs=["Field Parameters"])
    assert "Field Parameters" in str(exc.value)
    assert "Sample Info" in str(exc.value)


# --- local exports -------------------------------------------------------------


def test_read_local_csv(tmp_path):
    path = tmp_path / "field-parameters.csv"
    path.write_text("PointID,FieldParameter,SampleValue\nMG-030,pH,7.2\n")

    (table,) = read_local_export(path)

    assert table.title == "field-parameters"
    assert table.rows[0]["FieldParameter"] == "pH"
    assert table.row_number(table.rows[0]) == 2


def test_read_local_csv_strips_bom(tmp_path):
    path = tmp_path / "field-parameters.csv"
    path.write_bytes("PointID,FieldParameter\nMG-030,pH\n".encode("utf-8-sig"))

    (table,) = read_local_export(path)

    assert table.header[0] == "PointID"


def test_read_local_xlsx(tmp_path):
    path = tmp_path / "field.xlsx"
    path.write_bytes(_xlsx_bytes({"Sample Info": [["PointID"], ["MG-030"]]}))

    (table,) = read_local_export(path)

    assert table.rows[0]["PointID"] == "MG-030"


def test_unsupported_local_file_type(tmp_path):
    path = tmp_path / "field.numbers"
    path.write_bytes(b"nope")
    with pytest.raises(FieldSheetError):
        read_local_export(path)


# --- Google-hosted sources -----------------------------------------------------


class _FakeExecute:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeValues:
    def __init__(self, by_range):
        self._by_range = by_range
        self.requested = []

    def get(self, spreadsheetId, range, **kwargs):
        self.requested.append(range)
        return _FakeExecute({"values": self._by_range.get(range, [])})


class _FakeSpreadsheets:
    def __init__(self, metadata, values):
        self._metadata = metadata
        self._values = values

    def get(self, spreadsheetId, fields=None):
        return _FakeExecute(self._metadata)

    def values(self):
        return self._values


class _FakeSheetsService:
    def __init__(self, metadata, by_range):
        self._values = _FakeValues(by_range)
        self._spreadsheets = _FakeSpreadsheets(metadata, self._values)

    def spreadsheets(self):
        return self._spreadsheets


class _FakeFiles:
    def __init__(self, metadata, media=b""):
        self._metadata = metadata
        self._media = media

    def get(self, fileId, fields=None, supportsAllDrives=False):
        return _FakeExecute(self._metadata)


class _FakeDriveService:
    def __init__(self, metadata):
        self._files = _FakeFiles(metadata)

    def files(self):
        return self._files


def test_native_sheet_read_by_gid():
    drive = _FakeDriveService(
        {"id": SHEET_ID, "name": "AMP Chemistry", "mimeType": GOOGLE_SHEET_MIME}
    )
    sheets = _FakeSheetsService(
        {
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Sample Info", "index": 0}},
                {
                    "properties": {
                        "sheetId": 1878349160,
                        "title": "Field Parameters",
                        "index": 1,
                    }
                },
            ]
        },
        {"'Field Parameters'": [["PointID", "FieldParameter"], ["MG-030", "pH"]]},
    )

    tables = read_google_spreadsheet(
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid=1878349160",
        drive_service=drive,
        sheets_service=sheets,
    )

    assert [t.title for t in tables] == ["Field Parameters"]
    assert tables[0].rows[0]["FieldParameter"] == "pH"


def test_native_sheet_unknown_gid_is_reported():
    drive = _FakeDriveService(
        {"id": SHEET_ID, "name": "AMP Chemistry", "mimeType": GOOGLE_SHEET_MIME}
    )
    sheets = _FakeSheetsService(
        {
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Sample Info", "index": 0}}
            ]
        },
        {},
    )

    with pytest.raises(FieldSheetError) as exc:
        read_google_spreadsheet(
            f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid=999",
            drive_service=drive,
            sheets_service=sheets,
        )
    assert "gid=999" in str(exc.value)


def test_xlsx_uploaded_to_drive_is_downloaded_not_read_through_sheets(monkeypatch):
    """The Sheets API cannot read an uploaded .xlsx, so those go via Drive bytes."""
    drive = _FakeDriveService(
        {"id": SHEET_ID, "name": "AMP Chemistry.xlsx", "mimeType": XLSX_MIME}
    )
    content = _xlsx_bytes({"Field Parameters": [["PointID"], ["MG-030"]]})
    downloaded = {}

    def fake_download(file_id, service=None):
        downloaded["file_id"] = file_id
        return content

    monkeypatch.setattr(chemistry_field_sheet, "download_drive_file", fake_download)

    tables = read_google_spreadsheet(SHEET_ID, drive_service=drive)

    assert downloaded["file_id"] == SHEET_ID
    assert [t.title for t in tables] == ["Field Parameters"]


def test_unsupported_drive_mime_type():
    drive = _FakeDriveService(
        {"id": SHEET_ID, "name": "notes.pdf", "mimeType": "application/pdf"}
    )
    with pytest.raises(FieldSheetError):
        read_google_spreadsheet(SHEET_ID, drive_service=drive)


def test_row_number_key_is_not_a_spreadsheet_column():
    """The row number rides along in the record, so it must not clash."""
    assert SheetTable.ROW_NUMBER_KEY.startswith("__")


# ------------------------- failed-row reports ----------------------------------

_INFO_HEADER = ["WellPointID", "SamplePointID", "CollectionDate"]
_PARAMS_HEADER = ["SamplePointID", "Time", "pHf"]


def _export(path, info_title="ChemistrySampleInfo"):
    """A field-sheet export with two sample rows, one reading, and a lab tab."""
    path.write_bytes(
        _xlsx_bytes(
            {
                info_title: [
                    _INFO_HEADER,
                    ["WL-1", "WL-1A", "2025-06-10"],
                    ["WL-1", "WL-1B", None],
                ],
                "FieldParameters": [_PARAMS_HEADER, ["WL-1B", "2025-06-10 10:00", 7.1]],
                "GenChemResults": [["WellPointID", "Ca"], ["WL-1", 12.5]],
            }
        )
    )
    return path


_FAILED = [
    {
        "tab": "ChemistrySampleInfo",
        "row": 3,
        "sample_point_id": "WL-1B",
        "reason": "Missing CollectionDate",
        "caused_by": None,
    },
    {
        "tab": "FieldParameters",
        "row": 2,
        "sample_point_id": "WL-1B",
        "reason": "its ChemistrySampleInfo row 3 failed: Missing CollectionDate",
        "caused_by": {"tab": "ChemistrySampleInfo", "row": 3},
    },
]


def _values(sheet):
    return [[cell.value for cell in row] for row in sheet.iter_rows()]


def test_failed_rows_workbook_lists_each_row_with_why_and_what_it_held(tmp_path):
    from openpyxl import load_workbook

    info, params, _lab = read_local_export(_export(tmp_path / "sheet.xlsx"))
    out = write_failed_rows_workbook(
        {"ChemistrySampleInfo": info, "FieldParameters": params},
        _FAILED,
        tmp_path / "failed.xlsx",
    )

    workbook = load_workbook(out)
    assert workbook.sheetnames == ["ChemistrySampleInfo", "FieldParameters"]
    assert _values(workbook["ChemistrySampleInfo"]) == [
        ["Source row", "Why it failed", *_INFO_HEADER],
        [3, "Missing CollectionDate", "WL-1", "WL-1B", None],
    ]
    assert _values(workbook["FieldParameters"])[1][:3] == [
        2,
        "its ChemistrySampleInfo row 3 failed: Missing CollectionDate",
        "WL-1B",
    ]


@pytest.mark.parametrize("info_title", ["ChemistrySampleInfo", "Sample Info"])
def test_loadable_copy_blanks_failed_rows_and_keeps_the_rest_in_place(
    tmp_path, info_title
):
    from openpyxl import load_workbook

    source = _export(tmp_path / "sheet.xlsx", info_title)
    out = write_loadable_copy(
        source,
        {"ChemistrySampleInfo": info_title, "FieldParameters": "FieldParameters"},
        _FAILED,
        tmp_path / "loadable.xlsx",
    )

    workbook = load_workbook(out)

    def row(title, number):
        # By position: a blanked last row isn't stored at all, and reads back
        # as empty cells, which is what the reader sees too.
        return [workbook[title].cell(number, c).value for c in range(1, 4)]

    assert row(info_title, 2) == ["WL-1", "WL-1A", "2025-06-10"]
    assert row(info_title, 3) == [None, None, None]
    assert row("FieldParameters", 2) == [None, None, None]
    assert _values(workbook["GenChemResults"]) == [
        ["WellPointID", "Ca"],
        ["WL-1", 12.5],
    ]
    # Read back, the blank rows drop out and the surviving row keeps its number.
    reread, _params, _lab = read_local_export(out)
    assert [r[SheetTable.ROW_NUMBER_KEY] for r in reread.rows] == [2]
    # The export it came from is untouched.
    assert _values(load_workbook(source)[info_title])[2] == ["WL-1", "WL-1B", None]


def test_loadable_copy_needs_an_xlsx_and_a_new_file(tmp_path):
    source = _export(tmp_path / "sheet.xlsx")
    csv_export = tmp_path / "sheet.csv"
    csv_export.write_text("WellPointID\nWL-1\n")
    titles = {"ChemistrySampleInfo": "ChemistrySampleInfo"}

    with pytest.raises(FieldSheetError, match="needs an .xlsx"):
        write_loadable_copy(csv_export, titles, _FAILED, tmp_path / "out.xlsx")
    with pytest.raises(FieldSheetError, match="must be a new file"):
        write_loadable_copy(source, titles, _FAILED, source)


# ============= EOF =============================================
