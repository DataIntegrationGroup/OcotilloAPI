from __future__ import annotations

import logging
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from cli.cli import cli
import services.scoped_transfer as scoped_transfer_module
from services.scoped_transfer import (
    FamilySpec,
    ScopedFamilyResult,
    ScopedTransferOptions,
    ScopedTransferResult,
    ScopedTransferRuntime,
    ScopedTransferLogFilter,
    ScopedWaterLevelTransferer,
    ScopedWellTransferer,
    _plan_chemistry_child_table,
    _plan_chemistry_sampleinfo,
    _plan_groups,
    normalize_pointids,
    run_scoped_transfer,
)


class _FakeSavepoint:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeScalarQuery:
    def __init__(self, session):
        self.session = session

    def filter(self, *_args, **_kwargs):
        return self

    def scalar(self):
        return self.session.scalar_results.pop(0)


class _FakeParticipantSession:
    def __init__(self, scalar_results):
        self.begin_nested_calls = 0
        self.scalar_results = list(scalar_results)
        self.execute_calls = []

    def begin_nested(self):
        self.begin_nested_calls += 1
        return _FakeSavepoint()

    def execute(self, statement, params):
        self.execute_calls.append((statement, params))
        raise IntegrityError("insert", {}, Exception("duplicate key"))

    def query(self, *_args, **_kwargs):
        return _FakeScalarQuery(self)


def test_scoped_transfer_cli_json_output(monkeypatch):
    def fake_run(_options):
        return ScopedTransferResult(
            pointids=["SM-0001"],
            selected_families=["wells"],
            added_prerequisites=[],
            dry_run=True,
            family_results=[
                ScopedFamilyResult(
                    family="wells",
                    status="planned",
                    applicable_source_rows=1,
                )
            ],
            validation_errors=[],
            exit_code=0,
        )

    monkeypatch.setattr("services.scoped_transfer.run_scoped_transfer", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scoped-transfer",
            "--pointid",
            "SM-0001",
            "--dry-run",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"pointids": [' in result.output
    assert '"selected_families": [' in result.output


def test_scoped_transfer_cli_human_output(monkeypatch):
    def fake_run(_options):
        return ScopedTransferResult(
            pointids=["SM-0001"],
            selected_families=["wells", "contacts"],
            added_prerequisites=["contacts"],
            dry_run=False,
            family_results=[
                ScopedFamilyResult(
                    family="wells",
                    status="completed",
                    applicable_source_rows=1,
                    created=1,
                ),
                ScopedFamilyResult(
                    family="contacts",
                    status="completed",
                    applicable_source_rows=1,
                    created=1,
                    added_as_prerequisite=True,
                ),
            ],
            validation_errors=[],
            exit_code=0,
        )

    monkeypatch.setattr("services.scoped_transfer.run_scoped_transfer", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["scoped-transfer", "--pointid", "SM-0001"])

    assert result.exit_code == 0, result.output
    assert "Starting scoped transfer for PointIDs: SM-0001" in result.output
    assert "Validating requested scope and preparing execution..." in result.output
    assert "[SCOPED TRANSFER]" in result.output
    assert "Requested PointIDs: SM-0001" in result.output
    assert "Auto-added prerequisites: contacts" in result.output
    assert "wells" in result.output
    assert "contacts" in result.output


def test_normalize_pointids_dedupes_and_uppercases():
    assert normalize_pointids([" sm-0001 ", "SM-0001", "sp-1"]) == [
        "SM-0001",
        "SP-1",
    ]


def test_scoped_transfer_runtime_expands_dependencies():
    runtime = ScopedTransferRuntime(
        ScopedTransferOptions(pointids=["SM-0001"], only=["field-parameters"])
    )

    assert runtime.selected_family_names == [
        "wells",
        "chemistry-sampleinfo",
        "field-parameters",
    ]
    assert runtime.added_prerequisites == ["chemistry-sampleinfo", "wells"]


def test_run_scoped_transfer_fails_preflight_when_pointid_missing(monkeypatch):
    def fake_registry():
        return {
            "wells": FamilySpec(
                name="wells",
                planner=lambda _runtime: ScopedFamilyResult(
                    family="wells",
                    status="no-op",
                    applicable_source_rows=0,
                ),
                executor=lambda _runtime: ScopedFamilyResult(
                    family="wells",
                    status="no-op",
                    applicable_source_rows=0,
                ),
            )
        }

    monkeypatch.setattr("services.scoped_transfer.build_family_registry", fake_registry)

    result = run_scoped_transfer(
        ScopedTransferOptions(pointids=["DOES-NOT-EXIST"], only=["wells"], dry_run=True)
    )

    assert result.exit_code == 1
    assert result.validation_errors
    assert "DOES-NOT-EXIST" in result.validation_errors[0]


def test_run_scoped_transfer_dry_run_returns_planned_results(monkeypatch):
    def fake_registry():
        return {
            "wells": FamilySpec(
                name="wells",
                planner=lambda _runtime: ScopedFamilyResult(
                    family="wells",
                    status="planned",
                    applicable_source_rows=1,
                ),
                executor=lambda _runtime: ScopedFamilyResult(
                    family="wells",
                    status="completed",
                    applicable_source_rows=1,
                ),
            )
        }

    monkeypatch.setattr("services.scoped_transfer.build_family_registry", fake_registry)
    monkeypatch.setattr(
        "services.scoped_transfer.read_csv",
        lambda *args, **kwargs: __import__("pandas").DataFrame(
            {"PointID": ["SM-0001"]}
        ),
    )
    monkeypatch.setattr(
        "services.scoped_transfer.replace_nans",
        lambda df: df,
    )

    result = run_scoped_transfer(
        ScopedTransferOptions(pointids=["SM-0001"], only=["wells"], dry_run=True)
    )

    assert result.exit_code == 0
    assert result.dry_run is True
    assert len(result.family_results) == 1
    assert result.family_results[0].status == "planned"


def test_plan_chemistry_sampleinfo_uses_samplepointid_prefix(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(
        "services.scoped_transfer.read_csv",
        lambda name, *args, **kwargs: (
            pd.DataFrame(
                {
                    "SamplePointID": ["SM-0001A", "SM-0001B", "SM-9999A"],
                    "SamplePtID": ["a", "b", "c"],
                }
            )
            if name == "Chemistry_SampleInfo"
            else pd.DataFrame()
        ),
    )

    result = _plan_chemistry_sampleinfo(["SM-0001"])

    assert result.status == "planned"
    assert result.applicable_source_rows == 2


def test_plan_chemistry_child_table_uses_sample_pt_ids_from_sampleinfo(monkeypatch):
    import pandas as pd

    def fake_read_csv(name, *args, **kwargs):
        if name == "Chemistry_SampleInfo":
            return pd.DataFrame(
                {
                    "SamplePointID": ["SM-0001A", "SM-0001B", "ZZ-0001A"],
                    "SamplePtID": ["A", "B", "Z"],
                }
            )
        if name == "MajorChemistry":
            return pd.DataFrame(
                {
                    "SamplePtID": ["A", "A", "B", "Z"],
                }
            )
        return pd.DataFrame()

    monkeypatch.setattr("services.scoped_transfer.read_csv", fake_read_csv)

    result = _plan_chemistry_child_table("MajorChemistry", ["SM-0001"])

    assert result.status == "planned"
    assert result.applicable_source_rows == 3


def test_plan_groups_counts_matching_prefixes_only(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(
        "services.scoped_transfer.read_csv",
        lambda *args, **kwargs: pd.DataFrame(
            {
                "Project": ["Sacramento", "Questa", "Other"],
                "PointIDPrefix": ["SM, SO", "QU", "AB"],
            }
        ),
    )

    result = _plan_groups(["SM-0001"])

    assert result.status == "planned"
    assert result.applicable_source_rows == 1


def test_scoped_waterlevels_reuses_existing_contacts_after_insert_collision(
    monkeypatch,
):
    monkeypatch.setattr(
        scoped_transfer_module,
        "get_contacts_info",
        lambda row, measured_by, mapper: [
            ("Alice Example", "NMBGMR", "Technician"),
        ],
    )

    transferer = ScopedWaterLevelTransferer.__new__(ScopedWaterLevelTransferer)
    transferer._created_contact_id_by_key = {}
    transferer._owner_contact_id_by_pointid = {}
    transferer._measured_by_mapper = {}
    transferer._last_contacts_created_count = 0
    transferer._last_contacts_reused_count = 0

    session = _FakeParticipantSession(scalar_results=[42])
    row = SimpleNamespace(
        PointID="SM-0001",
        GlobalID="gid-1",
        MeasuredBy="NMBGMR_TECH",
    )

    participant_ids = transferer._get_field_event_participant_ids(session, row)

    assert participant_ids == [42]
    assert session.begin_nested_calls == 1
    assert len(session.execute_calls) == 1
    assert transferer._created_contact_id_by_key == {
        ("Alice Example", "NMBGMR"): 42,
    }
    assert transferer._last_contacts_created_count == 0
    assert transferer._last_contacts_reused_count == 1


def test_scoped_wells_duplicate_check_only_applies_to_requested_pointids(monkeypatch):
    import pandas as pd

    well_df = pd.DataFrame(
        {
            "PointID": ["SM-0001", "QU-047", "QU-047", "DA-0047", "DA-0047"],
            "LocationId": [1, 2, 3, 4, 5],
            "SiteType": ["GW"] * 5,
            "Easting": [1] * 5,
            "Northing": [1] * 5,
            "OSEWelltagID": [None] * 5,
        }
    )
    location_df = pd.DataFrame(
        {
            "LocationId": [1, 2, 3, 4, 5],
            "PointID": ["SM-0001", "QU-047", "QU-047", "DA-0047", "DA-0047"],
            "SSMA_TimeStamp": [None] * 5,
        }
    )

    def fake_read_csv(name, *args, **kwargs):
        if name == "WellData":
            return well_df.copy()
        if name == "Location":
            return location_df.copy()
        raise AssertionError(f"Unexpected table {name}")

    monkeypatch.setattr(scoped_transfer_module, "read_csv", fake_read_csv)
    monkeypatch.setattr(scoped_transfer_module, "replace_nans", lambda df: df)
    monkeypatch.setattr(
        scoped_transfer_module,
        "get_transferable_wells",
        lambda df: df,
    )
    monkeypatch.setattr(
        scoped_transfer_module,
        "filter_non_transferred_wells",
        lambda df: df,
    )

    transferer = ScopedWellTransferer.__new__(ScopedWellTransferer)
    transferer.pointids = ["SM-0001"]

    _input_df, cleaned_df = transferer._get_dfs()

    assert cleaned_df["PointID"].tolist() == ["SM-0001"]


def test_scoped_transfer_log_filter_suppresses_known_noise_patterns():
    log_filter = ScopedTransferLogFilter()

    suppressed = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=(
            "Filtered out 288 HydraulicsData records without matching Things "
            "(0 valid, 288 orphan records prevented)"
        ),
        args=(),
        exc_info=None,
    )
    allowed = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Actual scoped warning that should remain visible",
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(suppressed) is False
    assert log_filter.filter(allowed) is True
