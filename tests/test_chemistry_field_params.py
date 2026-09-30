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
"""Tests for the chemistry field-sheet ingest
(services/chemistry_field_params.py)."""

from datetime import datetime

import pytest
from openpyxl import Workbook
from sqlalchemy import delete, select

from db.engine import session_ctx
from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_FieldParameters
from services.chemistry_field_params import (
    FIELD_SHEET_DATASET,
    FieldParamsMappingError,
    import_field_tables,
    prep_field_parameters,
    prep_sample_info,
    replay_field_sheet,
    select_tables,
    upload_field_export,
)
from services.ingest_raw_zone import list_snapshots, read_snapshot
from services.chemistry_field_sheet import SheetTable, read_local_export

WELL = "Test Well"

SAMPLE_INFO_HEADER = [
    "WellPointID",
    "SamplePointID",
    "AnalysisAgency",
    "SampleType (SD)",
    "CollectionDate",
    "CollectionMethod (F = faucet)",
    "CollectedBy (GR = grab??)",
    "Data Source",
    "Staff",
    "Sample Notes",
]

FIELD_PARAMS_HEADER = [
    "SamplePointID",
    "Time",
    "Discharge rate (gpm)",
    "pHf",
    "T (C)",
    "CF (uS/cm)",
    "DO (mg/L)",
    "ORP (mV)",
]


def _sample_info_row(**overrides):
    row = {
        "WellPointID": WELL,
        "SamplePointID": f"{WELL}A",
        "AnalysisAgency": "NMBGMR",
        "SampleType (SD)": "SD",
        "CollectionDate": "2025-06-10T12:05:00",
        "CollectionMethod (F = faucet)": "Faucet at well head",
        "CollectedBy (GR = grab??)": None,
        "Data Source": "NMBGMR",
        "Staff": "Dan Lavery, Sianin Spaur",
        "Sample Notes": "Sampled from spigot",
    }
    row.update(overrides)
    return row


def _field_params_row(**overrides):
    row = {
        "SamplePointID": f"{WELL}A",
        "Time": "2025-06-10T12:07:00",
        "Discharge rate (gpm)": 0.568,
        "pHf": 6.94,
        "T (C)": 15.7,
        "CF (uS/cm)": 783.0,
        "DO (mg/L)": 1.35,
        "ORP (mV)": 78.5,
    }
    row.update(overrides)
    return row


def _table(title: str, header: list[str], rows: list[dict]) -> SheetTable:
    records = []
    for offset, row in enumerate(rows):
        record = {column: row.get(column) for column in header}
        record[SheetTable.ROW_NUMBER_KEY] = offset + 2
        records.append(record)
    return SheetTable(title=title, header=header, rows=records)


def _tables(sample_rows=None, param_rows=None) -> list[SheetTable]:
    return [
        _table(
            "ChemistrySampleInfo",
            SAMPLE_INFO_HEADER,
            [_sample_info_row()] if sample_rows is None else sample_rows,
        ),
        _table(
            "FieldParameters",
            FIELD_PARAMS_HEADER,
            [_field_params_row()] if param_rows is None else param_rows,
        ),
    ]


@pytest.fixture()
def _cleanup_field_chemistry():
    """Remove samples (and cascaded field parameters) created during a test."""
    yield
    with session_ctx() as session:
        session.execute(
            delete(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.nma_sample_point_id.like(f"{WELL}%")
            )
        )
        session.commit()


def _samples():
    with session_ctx() as session:
        return session.scalars(
            select(NMA_Chemistry_SampleInfo)
            .where(NMA_Chemistry_SampleInfo.nma_sample_point_id.like(f"{WELL}%"))
            .order_by(NMA_Chemistry_SampleInfo.id)
        ).all()


def _parameters(sample_id: int):
    with session_ctx() as session:
        return session.scalars(
            select(NMA_FieldParameters)
            .where(NMA_FieldParameters.chemistry_sample_info_id == sample_id)
            .order_by(NMA_FieldParameters.field_parameter)
        ).all()


# ------------------------- pure-function tests -------------------------------


def test_prep_sample_info_reads_headings_with_hints():
    prepped = prep_sample_info(_sample_info_row())

    assert prepped["well_pointid"] == WELL
    assert prepped["collection_date"] == datetime(2025, 6, 10, 12, 5)
    assert prepped["attributes"]["sample_type"] == "SD"
    assert prepped["attributes"]["collection_method"] == "F"
    assert prepped["attributes"]["data_source"] == "NMBGMR"


@pytest.mark.parametrize(
    "written,code",
    [
        ("Bailer", "B"),
        ("Faucet at well head", "F"),
        ("Grab sample", "G"),
        ("Faucet or outlet at house", "H"),
        ("Pump", "P"),
        ("Thief sampler", "T"),
        ("Unknown", "U"),
        # Case and spacing are forgiven.
        ("faucet AT  well head ", "F"),
        # The legacy code itself is accepted too.
        ("F", "F"),
        ("h", "H"),
        (" U ", "U"),
    ],
)
def test_collection_method_is_stored_as_its_legacy_code(written, code):
    prepped = prep_sample_info(
        _sample_info_row(**{"CollectionMethod (F = faucet)": written})
    )
    assert prepped["attributes"]["collection_method"] == code


def test_collection_method_outside_the_vocabulary_is_refused():
    with pytest.raises(FieldParamsMappingError) as exc:
        prep_sample_info(_sample_info_row(**{"CollectionMethod (F = faucet)": "X"}))
    assert "not a known collection method" in str(exc.value)


def test_collection_method_may_be_left_blank():
    prepped = prep_sample_info(
        _sample_info_row(**{"CollectionMethod (F = faucet)": None})
    )
    assert "collection_method" not in prepped["attributes"]


def test_prep_sample_info_folds_staff_into_notes():
    """Staff has no legacy column, and the names are worth more than the space."""
    prepped = prep_sample_info(_sample_info_row())

    notes = prepped["attributes"]["sample_notes"]
    assert notes.startswith("Staff: Dan Lavery, Sianin Spaur")
    assert "Sampled from spigot" in notes


def test_prep_sample_info_requires_a_collection_date():
    with pytest.raises(FieldParamsMappingError):
        prep_sample_info(_sample_info_row(CollectionDate=None))


def test_prep_sample_info_rejects_an_unparseable_date():
    with pytest.raises(FieldParamsMappingError):
        prep_sample_info(_sample_info_row(CollectionDate="last Tuesday"))


def test_prep_sample_info_rejects_a_sample_point_from_another_well():
    with pytest.raises(FieldParamsMappingError) as exc:
        prep_sample_info(_sample_info_row(**{"SamplePointID": "Other WellA"}))
    assert "does not belong" in str(exc.value)


def test_prep_sample_info_rejects_an_overlong_collected_by():
    with pytest.raises(FieldParamsMappingError) as exc:
        prep_sample_info(
            _sample_info_row(**{"CollectedBy (GR = grab??)": "Sianin Spaur"})
        )
    assert "5" in str(exc.value)


def test_prep_sample_info_rejects_an_unassigned_pointid():
    """`WL-####` is a real sample whose well has no identifier yet."""
    with pytest.raises(FieldParamsMappingError) as exc:
        prep_sample_info(
            _sample_info_row(WellPointID="WL-####", **{"SamplePointID": "WL-####A"})
        )
    assert "no well identifier assigned" in str(exc.value)


def test_prep_field_parameters_rejects_an_unassigned_pointid():
    with pytest.raises(FieldParamsMappingError):
        prep_field_parameters(_field_params_row(**{"SamplePointID": "WL-####A"}))


@pytest.mark.parametrize(
    "written,expected",
    [
        ("2025-06-10T12:05:00", datetime(2025, 6, 10, 12, 5)),
        # Hand-typed single-digit hour: not ISO, plainly meant as 02:15.
        ("2025-06-06T2:15:00", datetime(2025, 6, 6, 2, 15)),
        ("2026-03-09 14:04:00", datetime(2026, 3, 9, 14, 4)),
        ("6/10/2025", datetime(2025, 6, 10)),
    ],
)
def test_collection_dates_the_sheet_actually_holds(written, expected):
    assert (
        prep_sample_info(_sample_info_row(CollectionDate=written))["collection_date"]
        == expected
    )


def test_prep_field_parameters_unpivots_columns_to_symbols():
    prepped = prep_field_parameters(_field_params_row())

    by_symbol = {m["symbol"]: m for m in prepped["measurements"]}
    assert by_symbol["pHf"]["value"] == 6.94
    assert by_symbol["pHf"]["units"] == "pH"
    assert by_symbol["T"]["units"] == "°C"
    assert by_symbol["CF"]["units"] == "µS/cm"
    assert by_symbol["DO"]["value"] == 1.35
    assert by_symbol["ORP"]["value"] == 78.5
    assert by_symbol["Q"]["units"] == "gpm"


def test_prep_field_parameters_skips_empty_cells():
    prepped = prep_field_parameters(
        _field_params_row(**{"DO (mg/L)": None, "ORP (mV)": ""})
    )
    symbols = {m["symbol"] for m in prepped["measurements"]}
    assert "DO" not in symbols
    assert "ORP" not in symbols


def test_prep_field_parameters_rejects_a_non_numeric_reading():
    with pytest.raises(FieldParamsMappingError) as exc:
        prep_field_parameters(_field_params_row(pHf="meter broken"))
    assert "pHf" in str(exc.value)


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_prep_field_parameters_requires_a_time(blank):
    """Without a Time, nothing shows the readings reached the right visit."""
    with pytest.raises(FieldParamsMappingError, match="Missing Time"):
        prep_field_parameters(_field_params_row(Time=blank))


@pytest.mark.parametrize("written", ["12:07", "noonish", "2025-13-40 12:07"])
def test_prep_field_parameters_rejects_an_unparseable_time(written):
    """Reported as the value typed, not as blank, so the right cell gets fixed."""
    with pytest.raises(FieldParamsMappingError, match="not a recognizable date"):
        prep_field_parameters(_field_params_row(Time=written))


def test_select_tables_finds_renamed_tabs_by_their_headers():
    tables = [
        _table("Sheet1", SAMPLE_INFO_HEADER, [_sample_info_row()]),
        _table("Sheet2", FIELD_PARAMS_HEADER, [_field_params_row()]),
    ]
    sample_info, field_params = select_tables(tables)

    assert sample_info.title == "Sheet1"
    assert field_params.title == "Sheet2"


def test_select_tables_ignores_lab_result_tabs():
    tables = _tables() + [
        _table("GenChemResults", ["WellPointID", "AnalysisDate", "Ca (mg/L)"], [])
    ]
    sample_info, field_params = select_tables(tables)

    assert sample_info.title == "ChemistrySampleInfo"
    assert field_params.title == "FieldParameters"


# ------------------------- ingestion tests -----------------------------------


def test_import_creates_sample_and_field_parameters(
    water_well_thing, _cleanup_field_chemistry
):
    result = import_field_tables(_tables())

    assert result.exit_code == 0, result.stderr
    (sample,) = _samples()
    assert sample.nma_sample_point_id == f"{WELL}A"
    assert sample.collection_date == datetime(2025, 6, 10, 12, 5)
    assert sample.sample_type == "SD"
    assert sample.collection_method == "F"

    parameters = _parameters(sample.id)
    assert {p.field_parameter for p in parameters} == {
        "pHf",
        "T",
        "CF",
        "DO",
        "ORP",
        "Q",
    }
    assert result.payload["summary"]["total_rows_imported"] == 6
    assert result.payload["summary"]["samples_created"] == 1


def test_measurement_time_is_kept_in_the_notes(
    water_well_thing, _cleanup_field_chemistry
):
    import_field_tables(_tables())

    (sample,) = _samples()
    assert all("2025-06-10T12:07:00" in p.notes for p in _parameters(sample.id))


def test_rerunning_loads_nothing_twice(water_well_thing, _cleanup_field_chemistry):
    import_field_tables(_tables())
    second = import_field_tables(_tables())

    assert second.exit_code == 0, second.stderr
    assert len(_samples()) == 1
    (sample,) = _samples()
    assert len(_parameters(sample.id)) == 6
    assert second.payload["summary"]["total_rows_imported"] == 0
    assert second.payload["summary"]["samples_matched"] == 1
    assert second.payload["summary"]["parameters_skipped"] == 6


def test_a_second_visit_becomes_its_own_sample(
    water_well_thing, _cleanup_field_chemistry
):
    import_field_tables(_tables())
    import_field_tables(
        _tables(
            sample_rows=[
                _sample_info_row(
                    CollectionDate="2025-09-02T09:00:00",
                    **{"SamplePointID": f"{WELL}B"},
                )
            ],
            param_rows=[
                _field_params_row(
                    **{"SamplePointID": f"{WELL}B", "Time": "2025-09-02T09:05:00"}
                )
            ],
        )
    )

    points = [s.nma_sample_point_id for s in _samples()]
    assert points == [f"{WELL}A", f"{WELL}B"]


# A FieldParameters row finds its sample by SamplePointID alone. These cover the
# ways a visit's readings could reach another visit's sample through that name.
SECOND_VISIT = "2025-09-02T09:00:00"


def _second_visit_params(point: str):
    return _field_params_row(
        **{"SamplePointID": point, "Time": "2025-09-02T09:05:00", "pHf": 7.5}
    )


def _first_visit_ph():
    first = _samples()[0]
    return {p.field_parameter: p.sample_value for p in _parameters(first.id)}["pHf"]


def test_a_new_visit_with_no_sample_point_aborts(
    water_well_thing, _cleanup_field_chemistry
):
    """With no name for the new sample, the readings row had to guess one, and
    a guess naming the earlier visit loaded its readings there."""
    import_field_tables(_tables())

    result = import_field_tables(
        _tables(
            sample_rows=[
                _sample_info_row(CollectionDate=SECOND_VISIT, **{"SamplePointID": None})
            ],
            param_rows=[_second_visit_params(f"{WELL}A")],
        )
    )

    assert result.exit_code == 1
    errors = result.payload["validation_errors"]
    assert any("Missing SamplePointID" in e for e in errors)
    assert [s.nma_sample_point_id for s in _samples()] == [f"{WELL}A"]
    assert _first_visit_ph() == 6.94


def test_a_blank_sample_point_aborts_even_for_a_recorded_visit(
    water_well_thing, _cleanup_field_chemistry
):
    """Only the field sample ID identifies a sample, so it's never guessed."""
    import_field_tables(_tables())

    result = import_field_tables(
        _tables(sample_rows=[_sample_info_row(**{"SamplePointID": None})])
    )

    assert result.exit_code == 1
    assert any(
        "Missing SamplePointID" in e for e in result.payload["validation_errors"]
    )
    assert len(_samples()) == 1


def test_two_visits_in_one_sheet_claiming_one_sample_point_abort(
    water_well_thing, _cleanup_field_chemistry
):
    """Neither row can be assumed right, so both are reported and neither loads."""
    result = import_field_tables(
        _tables(
            sample_rows=[
                _sample_info_row(),
                _sample_info_row(CollectionDate=SECOND_VISIT),
            ],
            param_rows=[_field_params_row(), _second_visit_params(f"{WELL}A")],
        )
    )

    assert result.exit_code == 1
    errors = result.payload["validation_errors"]
    assert any(
        e.startswith("ChemistrySampleInfo row 2:")
        and "dated 2025-06-10 here but also used on row 3 (2025-09-02)" in e
        for e in errors
    )
    assert any(
        e.startswith("ChemistrySampleInfo row 3:")
        and "dated 2025-09-02 here but also used on row 2 (2025-06-10)" in e
        for e in errors
    )
    assert not any("already belongs to" in e for e in errors)
    assert _samples() == []


def test_a_new_visit_reusing_an_earlier_visits_sample_point_aborts(
    water_well_thing, _cleanup_field_chemistry
):
    import_field_tables(_tables())

    result = import_field_tables(
        _tables(
            sample_rows=[_sample_info_row(CollectionDate=SECOND_VISIT)],
            param_rows=[_second_visit_params(f"{WELL}A")],
        )
    )

    assert result.exit_code == 1
    assert any(
        f"{WELL}A already belongs to the 2025-06-10 visit" in e
        for e in result.payload["validation_errors"]
    )
    assert [s.nma_sample_point_id for s in _samples()] == [f"{WELL}A"]
    assert _first_visit_ph() == 6.94


def test_a_matched_visit_named_after_another_visit_aborts(
    water_well_thing, _cleanup_field_chemistry
):
    """The name would point the earlier visit's readings at this visit too."""
    import_field_tables(_tables())
    import_field_tables(
        _tables(
            sample_rows=[
                _sample_info_row(
                    CollectionDate=SECOND_VISIT, **{"SamplePointID": f"{WELL}B"}
                )
            ],
            param_rows=[_second_visit_params(f"{WELL}B")],
        )
    )

    # The 2025-09-02 row now says A, which is the 2025-06-10 visit's name.
    result = import_field_tables(
        _tables(
            sample_rows=[_sample_info_row(CollectionDate=SECOND_VISIT)],
            param_rows=[_second_visit_params(f"{WELL}A")],
        )
    )

    assert result.exit_code == 1
    assert any(
        f"{WELL}A already belongs to the 2025-06-10 visit" in e
        and f"{WELL} already uses A, B" in e
        for e in result.payload["validation_errors"]
    )
    assert _first_visit_ph() == 6.94


def test_readings_naming_an_earlier_visit_abort(
    water_well_thing, _cleanup_field_chemistry
):
    """The sample-info row is right; only the readings row has the old letter."""
    import_field_tables(_tables())

    result = import_field_tables(
        _tables(
            sample_rows=[
                _sample_info_row(
                    CollectionDate=SECOND_VISIT, **{"SamplePointID": f"{WELL}B"}
                )
            ],
            param_rows=[_second_visit_params(f"{WELL}A")],
        )
    )

    assert result.exit_code == 1
    assert any(
        "collected on 2025-06-10" in e and "taken on 2025-09-02" in e
        for e in result.payload["validation_errors"]
    )
    assert [s.nma_sample_point_id for s in _samples()] == [f"{WELL}A"]
    assert _first_visit_ph() == 6.94


def test_readings_dated_a_different_day_from_their_visit_abort(
    water_well_thing, _cleanup_field_chemistry
):
    """A mistyped month on one tab: the kind of error the check exists for."""
    result = import_field_tables(
        _tables(param_rows=[_field_params_row(Time="2025-05-10T12:07:00")])
    )

    assert result.exit_code == 1
    assert any(
        "collected on 2025-06-10" in e and "taken on 2025-05-10" in e
        for e in result.payload["validation_errors"]
    )
    assert _samples() == []


def test_readings_later_on_the_same_day_load(
    water_well_thing, _cleanup_field_chemistry
):
    """Only the day is compared, never the time of day."""
    result = import_field_tables(
        _tables(param_rows=[_field_params_row(Time="2025-06-10T17:45:00")])
    )

    assert result.exit_code == 0, result.stderr
    (sample,) = _samples()
    assert len(_parameters(sample.id)) == 6


# Two samples at one well on one day: a duplicate minutes apart, or a split at
# the same timestamp. Matching on the well and day alone folded the second into
# the first and dropped its readings as already recorded.


def _same_day_pair(b_time: str):
    """A at 10:05 and B at ``b_time`` on 2025-06-10, with distinct pH readings."""
    return _tables(
        sample_rows=[
            _sample_info_row(CollectionDate="2025-06-10T10:05:00"),
            _sample_info_row(
                CollectionDate=f"2025-06-10T{b_time}",
                **{"SamplePointID": f"{WELL}B"},
            ),
        ],
        param_rows=[
            _field_params_row(Time="2025-06-10T10:05:00", pHf=7.0),
            _field_params_row(
                **{
                    "SamplePointID": f"{WELL}B",
                    "Time": f"2025-06-10T{b_time}",
                    "pHf": 8.0,
                }
            ),
        ],
    )


def _ph_by_point():
    return {
        s.nma_sample_point_id: {
            p.field_parameter: p.sample_value for p in _parameters(s.id)
        }["pHf"]
        for s in _samples()
    }


@pytest.mark.parametrize("b_time", ["10:18:00", "10:05:00"], ids=["duplicate", "split"])
def test_a_second_sample_on_the_same_day_is_its_own_sample(
    b_time, water_well_thing, _cleanup_field_chemistry
):
    result = import_field_tables(_same_day_pair(b_time))

    assert result.exit_code == 0, result.stderr
    assert result.payload["summary"]["samples_created"] == 2
    assert _ph_by_point() == {f"{WELL}A": 7.0, f"{WELL}B": 8.0}


@pytest.mark.parametrize("b_time", ["10:18:00", "10:05:00"], ids=["duplicate", "split"])
def test_rerunning_a_same_day_pair_loads_nothing_twice(
    b_time, water_well_thing, _cleanup_field_chemistry
):
    """A split's identical times left only the names to tell them apart."""
    import_field_tables(_same_day_pair(b_time))
    second = import_field_tables(_same_day_pair(b_time))

    assert second.exit_code == 0, second.stderr
    assert second.payload["summary"]["samples_created"] == 0
    assert second.payload["summary"]["samples_matched"] == 2
    assert second.payload["summary"]["total_rows_imported"] == 0
    assert _ph_by_point() == {f"{WELL}A": 7.0, f"{WELL}B": 8.0}


def _lab_sample(thing_id: int, point: str = f"{WELL}A"):
    """A sample as the LIMS ingest leaves it: a lab id and a date-only date."""
    with session_ctx() as session:
        session.add(
            NMA_Chemistry_SampleInfo(
                thing_id=thing_id,
                nma_sample_point_id=point,
                nma_wclab_id="LAB-1",
                collection_date=datetime(2025, 6, 10),
            )
        )
        session.commit()


@pytest.mark.parametrize("a_first", [True, False], ids=["A-row-first", "B-row-first"])
def test_a_duplicate_does_not_take_the_lab_sample_its_pair_names(
    a_first, water_well_thing, _cleanup_field_chemistry
):
    """The lab sample goes to the row naming it, whichever row comes first."""
    _lab_sample(water_well_thing.id)
    tables = _same_day_pair("10:18:00")
    if not a_first:
        tables[0].rows.reverse()

    result = import_field_tables(tables)

    assert result.exit_code == 0, result.stderr
    assert result.payload["summary"]["samples_matched"] == 1
    assert result.payload["summary"]["samples_created"] == 1
    lab_ids = {s.nma_sample_point_id: s.nma_wclab_id for s in _samples()}
    assert lab_ids == {f"{WELL}A": "LAB-1", f"{WELL}B": None}
    assert _ph_by_point() == {f"{WELL}A": 7.0, f"{WELL}B": 8.0}


def test_a_different_letter_is_a_different_sample(
    water_well_thing, _cleanup_field_chemistry
):
    """The lab's WL-A and the sheet's WL-B share a day, but not a field sample."""
    _lab_sample(water_well_thing.id)
    result = import_field_tables(
        _tables(
            sample_rows=[_sample_info_row(**{"SamplePointID": f"{WELL}B"})],
            param_rows=[_field_params_row(**{"SamplePointID": f"{WELL}B"})],
        )
    )

    assert result.exit_code == 0, result.stderr
    assert result.payload["warnings"] == []
    lab, field = _samples()
    assert (lab.nma_sample_point_id, lab.nma_wclab_id) == (f"{WELL}A", "LAB-1")
    assert _parameters(lab.id) == []
    assert field.nma_sample_point_id == f"{WELL}B"
    assert len(_parameters(field.id)) == 6


def test_a_sample_the_lab_ingest_already_created_is_reused(
    water_well_thing, _cleanup_field_chemistry
):
    """The lab batch and the field visit are one sample, matched on well + date."""
    with session_ctx() as session:
        session.add(
            NMA_Chemistry_SampleInfo(
                thing_id=water_well_thing.id,
                nma_sample_point_id=f"{WELL}A",
                nma_wclab_id="LAB-1",
                collection_date=datetime(2025, 6, 10, 12, 5),
            )
        )
        session.commit()

    result = import_field_tables(_tables())

    assert result.exit_code == 0, result.stderr
    (sample,) = _samples()
    assert sample.nma_wclab_id == "LAB-1"
    assert result.payload["summary"]["samples_created"] == 0
    assert result.payload["summary"]["samples_matched"] == 1
    # The field readings hang off the lab's sample, and carry its lab id.
    assert {p.nma_wclab_id for p in _parameters(sample.id)} == {"LAB-1"}


def test_matching_is_by_calendar_day_when_the_times_differ(
    water_well_thing, _cleanup_field_chemistry
):
    """The sheet's time and the lab's time for one visit differ by minutes."""
    with session_ctx() as session:
        session.add(
            NMA_Chemistry_SampleInfo(
                thing_id=water_well_thing.id,
                nma_sample_point_id=f"{WELL}A",
                nma_wclab_id="LAB-1",
                collection_date=datetime(2025, 6, 10, 14, 30),
            )
        )
        session.commit()

    result = import_field_tables(_tables())

    assert len(_samples()) == 1
    assert result.payload["summary"]["samples_matched"] == 1


def test_existing_values_are_not_overwritten_but_are_reported(
    water_well_thing, _cleanup_field_chemistry
):
    with session_ctx() as session:
        session.add(
            NMA_Chemistry_SampleInfo(
                thing_id=water_well_thing.id,
                nma_sample_point_id=f"{WELL}A",
                collection_date=datetime(2025, 6, 10, 12, 5),
                sample_type="GW",
            )
        )
        session.commit()

    result = import_field_tables(_tables())

    (sample,) = _samples()
    assert sample.sample_type == "GW"
    assert any("sample_type" in w for w in result.payload["warnings"])


def test_a_legacy_collection_method_code_agrees_with_its_meaning(
    water_well_thing, _cleanup_field_chemistry
):
    """Legacy rows hold "F"; the sheet says "Faucet at well head". Same thing."""
    with session_ctx() as session:
        session.add(
            NMA_Chemistry_SampleInfo(
                thing_id=water_well_thing.id,
                nma_sample_point_id=f"{WELL}A",
                collection_date=datetime(2025, 6, 10, 12, 5),
                collection_method="F",
            )
        )
        session.commit()

    result = import_field_tables(_tables())

    assert result.exit_code == 0, result.stderr
    (sample,) = _samples()
    assert sample.collection_method == "F"
    assert not any("collection_method" in w for w in result.payload["warnings"])


def test_unknown_well_aborts_the_whole_import(
    water_well_thing, _cleanup_field_chemistry
):
    result = import_field_tables(
        _tables(
            sample_rows=[
                _sample_info_row(),
                _sample_info_row(
                    WellPointID="No Such Well", **{"SamplePointID": "No Such WellA"}
                ),
            ]
        )
    )

    assert result.exit_code == 1
    assert any("No Such Well" in e for e in result.payload["validation_errors"])
    # Nothing is written, not even the row that was fine.
    assert _samples() == []


def test_field_parameters_for_an_unknown_sample_abort_the_import(
    water_well_thing, _cleanup_field_chemistry
):
    result = import_field_tables(
        _tables(param_rows=[_field_params_row(**{"SamplePointID": "Test WellZ"})])
    )

    assert result.exit_code == 1
    assert any("Test WellZ" in e for e in result.payload["validation_errors"])
    assert _samples() == []


def test_dry_run_writes_nothing(water_well_thing, _cleanup_field_chemistry):
    result = import_field_tables(_tables(), dry_run=True)

    assert result.exit_code == 0, result.stderr
    assert result.payload["summary"]["dry_run"] is True
    assert result.payload["summary"]["samples_created"] == 1
    assert _samples() == []


def test_upload_from_a_downloaded_workbook(
    tmp_path, water_well_thing, _cleanup_field_chemistry
):
    workbook = Workbook()
    workbook.remove(workbook.active)
    info = workbook.create_sheet("ChemistrySampleInfo")
    info.append(SAMPLE_INFO_HEADER)
    info.append([_sample_info_row().get(c) for c in SAMPLE_INFO_HEADER])
    params = workbook.create_sheet("FieldParameters")
    params.append(FIELD_PARAMS_HEADER)
    params.append([_field_params_row().get(c) for c in FIELD_PARAMS_HEADER])
    path = tmp_path / "field.xlsx"
    workbook.save(path)

    # Archiving is covered below; this is about reading the file.
    result = upload_field_export([path], archive=False)

    assert result.exit_code == 0, result.stderr
    (sample,) = _samples()
    assert len(_parameters(sample.id)) == 6


def test_upload_from_one_csv_per_tab(
    tmp_path, water_well_thing, _cleanup_field_chemistry
):
    info_path = tmp_path / "info.csv"
    info_path.write_text(
        ",".join(SAMPLE_INFO_HEADER)
        + "\n"
        + ",".join(
            str(_sample_info_row().get(c) or "") for c in SAMPLE_INFO_HEADER
        ).replace("Dan Lavery, Sianin Spaur", "Dan Lavery")
        + "\n"
    )
    params_path = tmp_path / "params.csv"
    params_path.write_text(
        ",".join(FIELD_PARAMS_HEADER)
        + "\n"
        + ",".join(str(_field_params_row().get(c) or "") for c in FIELD_PARAMS_HEADER)
        + "\n"
    )

    # Each CSV holds one tab, so both are read and pooled.
    tables = read_local_export(info_path) + read_local_export(params_path)
    sample_info, field_params = select_tables(tables)
    assert sample_info is not None and field_params is not None

    result = upload_field_export([info_path, params_path], archive=False)

    assert result.exit_code == 0, result.stderr
    (sample,) = _samples()
    assert len(_parameters(sample.id)) == 6


# ------------------------- raw zone -------------------------------------------


@pytest.fixture()
def raw_zone(tmp_path, monkeypatch):
    """A raw zone on disk, with dlt's own state kept out of the developer's home."""
    monkeypatch.setenv("DLT_DATA_DIR", str(tmp_path / "dlt"))
    return (tmp_path / "raw").resolve().as_uri()


def _workbook(tmp_path, sample_rows=None, param_rows=None):
    workbook = Workbook()
    workbook.remove(workbook.active)
    info = workbook.create_sheet("ChemistrySampleInfo")
    info.append(SAMPLE_INFO_HEADER)
    for row in sample_rows if sample_rows is not None else [_sample_info_row()]:
        info.append([row.get(c) for c in SAMPLE_INFO_HEADER])
    params = workbook.create_sheet("FieldParameters")
    params.append(FIELD_PARAMS_HEADER)
    for row in param_rows if param_rows is not None else [_field_params_row()]:
        params.append([row.get(c) for c in FIELD_PARAMS_HEADER])
    path = tmp_path / "field.xlsx"
    workbook.save(path)
    return path


def test_upload_archives_what_it_read_then_loads_that(
    tmp_path, raw_zone, water_well_thing, _cleanup_field_chemistry
):
    """What gets loaded is what was archived, not a second read of the source."""
    result = upload_field_export([_workbook(tmp_path)], raw_url=raw_zone)

    assert result.exit_code == 0, result.stderr
    raw = result.payload["raw"]
    assert raw["load_id"]
    assert raw["dataset"] == FIELD_SHEET_DATASET
    assert raw["rows_archived"] == 2

    (sample,) = _samples()
    assert len(_parameters(sample.id)) == 6


def test_replay_reloads_a_snapshot_without_the_source(
    tmp_path, raw_zone, water_well_thing, _cleanup_field_chemistry
):
    """A mapping fix is retested against the rows the original run saw."""
    path = _workbook(tmp_path)
    first = upload_field_export([path], raw_url=raw_zone)
    load_id = first.payload["raw"]["load_id"]

    # The source is gone; the archive is not.
    path.unlink()
    with session_ctx() as session:
        session.execute(
            delete(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.nma_sample_point_id.like(f"{WELL}%")
            )
        )
        session.commit()

    replayed = replay_field_sheet(load_id, raw_url=raw_zone)

    assert replayed.exit_code == 0, replayed.stderr
    (sample,) = _samples()
    assert len(_parameters(sample.id)) == 6
    assert replayed.payload["raw"]["replayed"] is True


def test_replay_is_still_idempotent(
    tmp_path, raw_zone, water_well_thing, _cleanup_field_chemistry
):
    load_id = upload_field_export([_workbook(tmp_path)], raw_url=raw_zone).payload[
        "raw"
    ]["load_id"]

    again = replay_field_sheet(load_id, raw_url=raw_zone)

    assert again.payload["summary"]["total_rows_imported"] == 0
    assert again.payload["summary"]["parameters_skipped"] == 6
    assert len(_samples()) == 1


def test_a_dry_run_leaves_no_snapshot_behind(
    tmp_path, raw_zone, water_well_thing, _cleanup_field_chemistry
):
    """Checking what would happen should not write to the archive either."""
    result = upload_field_export([_workbook(tmp_path)], dry_run=True, raw_url=raw_zone)

    assert result.exit_code == 0, result.stderr
    assert result.payload["raw"] == {}
    assert list_snapshots(FIELD_SHEET_DATASET, raw_url=raw_zone) == []
    assert _samples() == []


def test_archiving_can_be_skipped(
    tmp_path, raw_zone, water_well_thing, _cleanup_field_chemistry
):
    result = upload_field_export([_workbook(tmp_path)], archive=False, raw_url=raw_zone)

    assert result.exit_code == 0, result.stderr
    assert result.payload["raw"] == {}
    assert list_snapshots(FIELD_SHEET_DATASET, raw_url=raw_zone) == []
    assert len(_samples()) == 1


def test_the_archive_keeps_a_bad_row_as_written(
    tmp_path, raw_zone, water_well_thing, _cleanup_field_chemistry
):
    """A run that aborts still archives: that is the record of what arrived."""
    path = _workbook(
        tmp_path, sample_rows=[_sample_info_row(CollectionDate=None)], param_rows=[]
    )
    result = upload_field_export([path], raw_url=raw_zone)

    assert result.exit_code == 1
    assert result.payload["raw"]["load_id"]
    (archived,) = read_snapshot(FIELD_SHEET_DATASET, raw_url=raw_zone)
    assert archived.rows[0]["CollectionDate"] is None


# ------------------- matching by field sample ID (#970) ------------------------
#
# The field sample ID (SamplePointID) is authoritative: a row reaches only the
# record with its own name, and a new record takes that name. Different letters
# are different field samples, even on the same day.


def _named_row(point: str, collected: str):
    return _sample_info_row(CollectionDate=collected, **{"SamplePointID": point})


def _named_reading(point: str, taken: str, ph: float):
    return _field_params_row(**{"SamplePointID": point, "Time": taken, "pHf": ph})


def _stored_sample(thing_id: int, point: str, collected: datetime | None):
    with session_ctx() as session:
        session.add(
            NMA_Chemistry_SampleInfo(
                thing_id=thing_id,
                nma_sample_point_id=point,
                collection_date=collected,
            )
        )
        session.commit()


def _ph_on_each_sample():
    readings = {}
    for sample in _samples():
        ph = [
            p.sample_value for p in _parameters(sample.id) if p.field_parameter == "pHf"
        ]
        readings[sample.nma_sample_point_id] = ph
    return readings


def test_same_day_samples_under_other_letters_leave_the_lab_record_alone(
    water_well_thing, _cleanup_field_chemistry
):
    """The lab's A holds results; the sheet's B and C are two other samples."""
    _lab_sample(water_well_thing.id)
    result = import_field_tables(
        _tables(
            sample_rows=[
                _named_row(f"{WELL}B", "2025-06-10T10:05:00"),
                _named_row(f"{WELL}C", "2025-06-10T10:18:00"),
            ],
            param_rows=[
                _named_reading(f"{WELL}B", "2025-06-10T10:05:00", 7.0),
                _named_reading(f"{WELL}C", "2025-06-10T10:18:00", 8.0),
            ],
        )
    )

    assert result.exit_code == 0, result.stderr
    assert _ph_on_each_sample() == {
        f"{WELL}A": [],
        f"{WELL}B": [7.0],
        f"{WELL}C": [8.0],
    }


def test_new_records_take_the_sheets_letters_in_any_order(
    water_well_thing, _cleanup_field_chemistry
):
    """Rows listed C then B are stored as C and B, not renumbered."""
    _stored_sample(water_well_thing.id, f"{WELL}A", datetime(2025, 1, 1, 9, 0))
    result = import_field_tables(
        _tables(
            sample_rows=[
                _named_row(f"{WELL}C", "2025-06-10T10:05:00"),
                _named_row(f"{WELL}B", "2025-06-10T10:18:00"),
            ],
            param_rows=[
                _named_reading(f"{WELL}C", "2025-06-10T10:05:00", 7.0),
                _named_reading(f"{WELL}B", "2025-06-10T10:18:00", 8.0),
            ],
        )
    )

    assert result.exit_code == 0, result.stderr
    assert result.payload["warnings"] == []
    assert _ph_on_each_sample() == {
        f"{WELL}A": [],
        f"{WELL}C": [7.0],
        f"{WELL}B": [8.0],
    }


def test_a_sample_point_without_a_letter_aborts(
    water_well_thing, _cleanup_field_chemistry
):
    result = import_field_tables(
        _tables(sample_rows=[_sample_info_row(**{"SamplePointID": WELL})])
    )

    assert result.exit_code == 1
    assert any("has no sample letter" in e for e in result.payload["validation_errors"])
    assert _samples() == []


def test_a_new_visit_named_after_an_undated_sample_aborts(
    water_well_thing, _cleanup_field_chemistry
):
    """An undated record can't be shown to be this visit, so the name is taken."""
    _stored_sample(water_well_thing.id, f"{WELL}A", None)

    result = import_field_tables(_tables())

    assert result.exit_code == 1
    assert any(
        f"{WELL}A already belongs to another visit" in e
        for e in result.payload["validation_errors"]
    )
    (undated,) = _samples()
    assert _parameters(undated.id) == []


# ============= EOF =============================================
