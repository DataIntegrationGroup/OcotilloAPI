# ===============================================================================
# Copyright 2025 ross
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
from __future__ import annotations

import textwrap
import uuid
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from typer.testing import CliRunner

from cli.cli import cli
from cli.service_adapter import WellInventoryResult
from db import FieldActivity, FieldEvent, Observation, Sample
from db.engine import session_ctx


def test_refresh_pygeoapi_materialized_views_defaults(monkeypatch):
    executed_sql: list[str] = []
    commit_called = {"value": False}

    class FakeSession:
        def execute(self, stmt):
            executed_sql.append(str(stmt))

        def commit(self):
            commit_called["value"] = True

    class _FakeCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("db.engine.session_ctx", lambda: _FakeCtx())

    runner = CliRunner()
    result = runner.invoke(cli, ["refresh-pygeoapi-materialized-views"])

    assert result.exit_code == 0, result.output
    assert executed_sql == [
        "REFRESH MATERIALIZED VIEW ogc_latest_depth_to_water_wells",
        "REFRESH MATERIALIZED VIEW ogc_avg_tds_wells",
    ]
    assert commit_called["value"] is True
    assert "Refreshed 2 materialized view(s)." in result.output


def test_refresh_pygeoapi_materialized_views_custom_and_concurrently(monkeypatch):
    executed_sql: list[str] = []
    execution_options: list[dict[str, object]] = []

    class FakeConnection:
        def execution_options(self, **kwargs):
            execution_options.append(kwargs)
            return self

        def execute(self, stmt):
            executed_sql.append(str(stmt))

    class _FakeConnCtx:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return _FakeConnCtx()

    monkeypatch.setattr("db.engine.engine", FakeEngine())

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "refresh-pygeoapi-materialized-views",
            "--view",
            "ogc_avg_tds_wells",
            "--concurrently",
        ],
    )

    assert result.exit_code == 0, result.output
    assert execution_options == [{"isolation_level": "AUTOCOMMIT"}]
    assert executed_sql == [
        "REFRESH MATERIALIZED VIEW CONCURRENTLY ogc_avg_tds_wells",
    ]


def test_refresh_pygeoapi_materialized_views_rejects_invalid_identifier():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "refresh-pygeoapi-materialized-views",
            "--view",
            "ogc_avg_tds_wells;drop table thing",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid SQL identifier" in result.output


def test_initialize_lexicon_invokes_initializer(monkeypatch):
    called = {"count": 0}

    def fake_initializer():
        called["count"] += 1

    monkeypatch.setattr("core.initializers.init_lexicon", fake_initializer)

    runner = CliRunner()
    result = runner.invoke(cli, ["initialize-lexicon"])

    assert result.exit_code == 0
    assert called["count"] == 1


def test_associate_assets_command_calls_service(monkeypatch):
    captured = {}

    def fake_associate(source_directory):
        captured["path"] = Path(source_directory)
        return ["uri1"]

    monkeypatch.setattr("cli.service_adapter.associate_assets", fake_associate)

    runner = CliRunner()
    with runner.isolated_filesystem():
        workdir = Path.cwd()
        asset_dir = workdir / "asset_import_batch"
        asset_dir.mkdir()

        result = runner.invoke(cli, ["associate-assets", str(asset_dir)])

    assert result.exit_code == 0, result.output
    assert captured["path"] == asset_dir


def test_well_inventory_csv_command_calls_service(monkeypatch, tmp_path):
    inventory_file = tmp_path / "inventory.csv"
    inventory_file.write_text("header\nvalue\n")
    captured = {}

    def fake_well_inventory(file_path):
        captured["path"] = file_path
        return WellInventoryResult(
            exit_code=0,
            stdout="",
            stderr="",
            payload={
                "summary": {
                    "total_rows_processed": 1,
                    "total_rows_imported": 1,
                    "validation_errors_or_warnings": 0,
                },
                "validation_errors": [],
                "wells": [{}],
            },
        )

    monkeypatch.setattr("cli.service_adapter.well_inventory_csv", fake_well_inventory)

    runner = CliRunner()
    result = runner.invoke(cli, ["well-inventory-csv", str(inventory_file)])

    assert result.exit_code == 0, result.output
    assert Path(captured["path"]) == inventory_file
    assert "[WELL INVENTORY IMPORT] SUCCESS" in result.output


def test_transfer_results_command_writes_summary(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakeBuilder:
        def __init__(self, sample_limit: int = 25):
            captured["sample_limit"] = sample_limit

        def build(self):
            captured["built"] = True
            return SimpleNamespace(
                results={"WellData": object(), "WaterLevels": object()}
            )

        @staticmethod
        def write_summary(path, comparison):
            captured["summary_path"] = Path(path)
            captured["result_count"] = len(comparison.results)

    monkeypatch.setattr(
        "transfers.transfer_results_builder.TransferResultsBuilder", FakeBuilder
    )

    summary_path = tmp_path / "metrics" / "summary.md"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "transfer-results",
            "--summary-path",
            str(summary_path),
            "--sample-limit",
            "11",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["sample_limit"] == 11
    assert captured["built"] is True
    assert captured["summary_path"] == summary_path
    assert captured["result_count"] == 2
    assert f"Wrote comparison summary: {summary_path}" in result.output
    assert "Transfer comparisons: 2" in result.output


def test_well_inventory_csv_command_reports_validation_errors(monkeypatch, tmp_path):
    inventory_file = tmp_path / "inventory.csv"
    inventory_file.write_text("header\nvalue\n")

    def fake_well_inventory(_file_path):
        return WellInventoryResult(
            exit_code=1,
            stdout="",
            stderr="",
            payload={
                "summary": {
                    "total_rows_processed": 2,
                    "total_rows_imported": 0,
                    "validation_errors_or_warnings": 2,
                },
                "validation_errors": [
                    {
                        "row": 1,
                        "field": "contact_1_phone_1",
                        "error": "Invalid phone",
                        "value": "555-INVALID",
                    },
                    {
                        "row": 2,
                        "field": "date_time",
                        "error": "Invalid datetime",
                        "value": "1/12/2026 14:37",
                    },
                ],
                "wells": [],
            },
        )

    monkeypatch.setattr("cli.service_adapter.well_inventory_csv", fake_well_inventory)

    runner = CliRunner()
    result = runner.invoke(cli, ["well-inventory-csv", str(inventory_file)])

    assert result.exit_code == 1
    assert "Validation errors: 2" in result.output
    assert "Row 1 (1 issue)" in result.output
    assert "1. contact_1_phone_1: Invalid phone" in result.output
    assert "input: 555-INVALID" in result.output


def test_water_levels_bulk_upload_default_output(monkeypatch, tmp_path):
    csv_file = tmp_path / "water_levels.csv"
    csv_file.write_text("col\nvalue\n")
    captured = {}

    def fake_upload(file_path, *, pretty_json=False):
        captured["path"] = file_path
        captured["pretty_json"] = pretty_json
        return 0

    monkeypatch.setattr("cli.service_adapter.water_levels_csv", fake_upload)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["water-levels", "bulk-upload", "--file", str(csv_file)]
    )

    assert result.exit_code == 0
    assert Path(captured["path"]) == csv_file
    assert captured["pretty_json"] is False


def test_water_levels_bulk_upload_json_output(monkeypatch, tmp_path):
    csv_file = tmp_path / "water_levels.csv"
    csv_file.write_text("col\nvalue\n")
    captured = {}

    def fake_upload(file_path, *, pretty_json=False):
        captured["path"] = file_path
        captured["pretty_json"] = pretty_json
        return 0

    monkeypatch.setattr("cli.service_adapter.water_levels_csv", fake_upload)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "water-levels",
            "bulk-upload",
            "--file",
            str(csv_file),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert Path(captured["path"]) == csv_file
    assert captured["pretty_json"] is True


def test_water_levels_cli_persists_observations(tmp_path, water_well_thing):
    """
    End-to-end CLI invocation should create FieldEvent, Sample, and Observation rows.
    """

    def _write_csv(path: Path, *, well_name: str, notes: str):
        csv_text = textwrap.dedent(f"""\
            field_staff,well_name_point_id,field_event_date_time,measurement_date_time,sampler,sample_method,mp_height,level_status,depth_to_water_ft,data_quality,water_level_notes
            CLI Tester,{well_name},2025-02-15T08:00:00-07:00,2025-02-15T10:30:00-07:00,Groundwater Team,electric tape,1.5,stable,42.5,approved,{notes}
            """)
        path.write_text(csv_text)

    unique_notes = f"pytest-{uuid.uuid4()}"
    csv_file = tmp_path / "water_levels.csv"
    _write_csv(csv_file, well_name=water_well_thing.name, notes=unique_notes)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["water-levels", "bulk-upload", "--file", str(csv_file)]
    )

    assert result.exit_code == 0, result.output

    created_ids: dict[str, int] = {}
    with session_ctx() as session:
        stmt = (
            select(Observation)
            .join(Observation.sample)
            .join(Sample.field_activity)
            .join(FieldActivity.field_event)
            .where(Sample.notes == unique_notes)
        )
        observations = session.scalars(stmt).all()
        assert len(observations) == 1, "Expected one observation for the uploaded CSV"

        observation = observations[0]
        sample = observation.sample
        field_activity = sample.field_activity
        field_event = field_activity.field_event

        assert field_event.thing_id == water_well_thing.id
        assert sample.sample_method == "Electric tape measurement (E-probe)"
        assert sample.sample_matrix == "water"
        assert observation.value == 42.5
        assert observation.measuring_point_height == 1.5
        assert observation.notes == "Level status: stable | Data quality: approved"
        assert (
            field_event.notes == f"Field staff: CLI Tester | {unique_notes}"
        ), "Field event notes should capture field staff and notes"

        created_ids = {
            "observation_id": observation.id,
            "sample_id": sample.id,
            "field_activity_id": field_activity.id,
            "field_event_id": field_event.id,
        }

    if created_ids:
        # Clean up committed rows so other tests see a pristine database.
        with session_ctx() as session:
            observation = session.get(Observation, created_ids["observation_id"])
            sample = session.get(Sample, created_ids["sample_id"])
            field_activity = session.get(
                FieldActivity, created_ids["field_activity_id"]
            )
            field_event = session.get(FieldEvent, created_ids["field_event_id"])

            if observation:
                session.delete(observation)
                session.flush()
            if sample:
                session.delete(sample)
                session.flush()
            if field_activity:
                session.delete(field_activity)
                session.flush()
            if field_event:
                session.delete(field_event)
                session.flush()

            session.commit()


# ============= EOF =============================================
