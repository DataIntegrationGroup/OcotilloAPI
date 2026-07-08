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
"""Tests for the LIMS chemistry ingestion service (services/chemistry_lims.py)."""

from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import delete, select

from db.engine import session_ctx
from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
)
from services.chemistry_lims import (
    _int_to_suffix,
    _suffix_to_int,
    bulk_upload_chemistry,
    dedupe_records,
    prep_record,
)

LIMS_HEADER = [
    "Param",
    "Results_Units",
    "Dilution",
    "AnalysisTime",
    "SampleNumber",
    "CustomerSampleNumber",
    "SamplePointID",
    "Method",
    "Test",
    "ReportedND",
    "LowerLimit",
    "SampleDate",
]


def _write_workbook(path: Path, rows: list[dict]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(LIMS_HEADER)
    for row in rows:
        ws.append([row.get(col) for col in LIMS_HEADER])
    wb.save(path)
    return path


def _lims_row(param, value, *, pointid="Test Well", method="EPA 200.7", **overrides):
    row = {
        "Param": param,
        "Results_Units": "mg/L",
        "Dilution": 1,
        "AnalysisTime": "2024-06-15",
        "SampleNumber": "LAB-1",
        "CustomerSampleNumber": pointid,
        "SamplePointID": pointid,
        "Method": method,
        "Test": "Trace Metals",
        "ReportedND": value,
        "LowerLimit": 0.01,
        "SampleDate": "2024-06-01",
    }
    row.update(overrides)
    return row


@pytest.fixture()
def _cleanup_chemistry():
    """Remove any sample-info (and cascaded analytes) created during a test."""
    yield
    with session_ctx() as session:
        session.execute(
            delete(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.nma_wclab_id.like("LAB-%")
            )
        )
        session.commit()


# ------------------------- pure-function tests -------------------------------


def test_prep_record_maps_analyte_and_table():
    rec = prep_record(_lims_row("calcium", "12.5"))
    assert rec["analyte"] == "Ca"
    assert rec["table"] == "MajorChemistry"
    assert rec["sample_value"] == 12.5
    assert rec["symbol"] is None


def test_prep_record_non_detect_uses_lower_limit_times_dilution():
    rec = prep_record(_lims_row("lead", "ND", Dilution=2, LowerLimit=0.01))
    assert rec["analyte"] == "Pb"
    assert rec["table"] == "MinorandTraceChemistry"
    assert rec["symbol"] == "<"
    assert rec["sample_value"] == pytest.approx(0.02)


def test_prep_record_unmapped_analyte_raises():
    from services.chemistry_lims import ChemistryMappingError

    with pytest.raises(ChemistryMappingError):
        prep_record(_lims_row("unobtanium", "1.0"))


def test_dedupe_prefers_epa_200_7():
    rows = [
        prep_record(_lims_row("calcium", "10", method="EPA 6010")),
        prep_record(_lims_row("calcium", "11", method="EPA 200.7")),
    ]
    deduped = dedupe_records(rows)
    assert len(deduped) == 1
    assert deduped[0]["sample_value"] == 11.0


@pytest.mark.parametrize(
    "suffix,number",
    [("A", 1), ("B", 2), ("Z", 26), ("AA", 27), ("AB", 28), ("AZ", 52), ("BA", 53)],
)
def test_suffix_bijective_base26_roundtrip(suffix, number):
    assert _suffix_to_int(suffix) == number
    assert _int_to_suffix(number) == suffix


# ------------------------- ingestion tests -----------------------------------


def test_bulk_upload_inserts_major_and_minor(
    tmp_path, water_well_thing, _cleanup_chemistry
):
    path = _write_workbook(
        tmp_path / "lims.xlsx",
        [_lims_row("calcium", "12.5"), _lims_row("arsenic", "0.3")],
    )

    result = bulk_upload_chemistry(path)

    assert result.exit_code == 0, result.stderr
    assert result.payload["summary"]["total_rows_imported"] == 2

    with session_ctx() as session:
        info = session.scalars(
            select(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.thing_id == water_well_thing.id
            )
        ).one()
        major = session.scalars(
            select(NMA_MajorChemistry).where(
                NMA_MajorChemistry.chemistry_sample_info_id == info.id
            )
        ).all()
        minor = session.scalars(
            select(NMA_MinorTraceChemistry).where(
                NMA_MinorTraceChemistry.chemistry_sample_info_id == info.id
            )
        ).all()

    assert {m.analyte for m in major} == {"Ca"}
    assert {m.analyte for m in minor} == {"As"}
    # First sample for the well -> base PointID + "A".
    assert info.nma_sample_point_id == "Test WellA"
    assert {m.nma_sample_point_id for m in major} == {"Test WellA"}


def test_bulk_upload_skips_duplicate_lab_sample(
    tmp_path, water_well_thing, _cleanup_chemistry
):
    # Same WCLab_ID (SampleNumber) uploaded twice -> second run is idempotent.
    rows = [_lims_row("calcium", "12.5", SampleNumber="LAB-1")]
    _write_workbook(tmp_path / "first.xlsx", rows)
    first = bulk_upload_chemistry(tmp_path / "first.xlsx")
    assert first.exit_code == 0, first.stderr
    assert first.payload["summary"]["samples_created"] == 1

    _write_workbook(tmp_path / "second.xlsx", rows)
    second = bulk_upload_chemistry(tmp_path / "second.xlsx")

    # Idempotent: no failure, nothing imported, reported as skipped.
    assert second.exit_code == 0
    assert second.payload["summary"]["total_rows_imported"] == 0
    assert second.payload["summary"]["samples_skipped"] == 1
    assert second.payload["skipped_duplicates"][0]["wclab_id"] == "LAB-1"

    with session_ctx() as session:
        rows_ca = session.scalars(
            select(NMA_MajorChemistry).where(NMA_MajorChemistry.analyte == "Ca")
        ).all()
    assert len(rows_ca) == 1  # not duplicated


def test_bulk_upload_appends_new_lab_sample_with_next_suffix(
    tmp_path, water_well_thing, _cleanup_chemistry
):
    # A different WCLab_ID for the same well -> a new lettered sample point.
    _write_workbook(
        tmp_path / "first.xlsx", [_lims_row("calcium", "12.5", SampleNumber="LAB-1")]
    )
    first = bulk_upload_chemistry(tmp_path / "first.xlsx")
    assert first.exit_code == 0, first.stderr
    assert first.payload["created_samples"][0]["sample_point_id"] == "Test WellA"

    _write_workbook(
        tmp_path / "second.xlsx", [_lims_row("calcium", "9.9", SampleNumber="LAB-2")]
    )
    second = bulk_upload_chemistry(tmp_path / "second.xlsx")
    assert second.exit_code == 0, second.stderr
    assert second.payload["created_samples"][0]["sample_point_id"] == "Test WellB"

    with session_ctx() as session:
        infos = session.scalars(
            select(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.thing_id == water_well_thing.id
            )
        ).all()
    assert {i.nma_sample_point_id for i in infos} == {"Test WellA", "Test WellB"}


def test_bulk_upload_two_lab_samples_in_one_file_get_a_and_b(
    tmp_path, water_well_thing, _cleanup_chemistry
):
    # Two distinct lab samples in a single workbook -> A and B in one run.
    _write_workbook(
        tmp_path / "lims.xlsx",
        [
            _lims_row("calcium", "12.5", SampleNumber="LAB-1"),
            _lims_row("calcium", "9.9", SampleNumber="LAB-2"),
        ],
    )
    result = bulk_upload_chemistry(tmp_path / "lims.xlsx")
    assert result.exit_code == 0, result.stderr
    assert result.payload["summary"]["samples_created"] == 2

    with session_ctx() as session:
        infos = session.scalars(
            select(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.thing_id == water_well_thing.id
            )
        ).all()
    assert {i.nma_sample_point_id for i in infos} == {"Test WellA", "Test WellB"}


def test_bulk_upload_reports_missing_thing(tmp_path, _cleanup_chemistry):
    path = _write_workbook(
        tmp_path / "lims.xlsx",
        [_lims_row("calcium", "12.5", pointid="NO-SUCH-WELL")],
    )

    result = bulk_upload_chemistry(path)

    assert result.exit_code == 1
    assert result.payload["summary"]["total_rows_imported"] == 0
    assert any("no matching Thing" in e for e in result.payload["validation_errors"])


def test_bulk_upload_reports_unmapped_analyte(
    tmp_path, water_well_thing, _cleanup_chemistry
):
    path = _write_workbook(
        tmp_path / "lims.xlsx",
        [_lims_row("calcium", "12.5"), _lims_row("unobtanium", "9.9")],
    )

    result = bulk_upload_chemistry(path)

    # Unmapped analyte is a validation error -> whole file aborts, nothing imported.
    assert result.exit_code == 1
    assert result.payload["summary"]["total_rows_imported"] == 0
    assert any("Unmapped analyte" in e for e in result.payload["validation_errors"])


# ============= EOF =============================================
