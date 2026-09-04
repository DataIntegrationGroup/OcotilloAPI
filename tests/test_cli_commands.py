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

import gzip
import textwrap
import uuid
from pathlib import Path
from subprocess import CalledProcessError
from types import SimpleNamespace

from sqlalchemy import select
from typer.testing import CliRunner

from cli.cli import cli
from cli.service_adapter import WellInventoryResult
from db import (
    Contact,
    FieldActivity,
    FieldEvent,
    FieldEventParticipant,
    Observation,
    Sample,
)
from db.engine import session_ctx


def test_refresh_materialized_views_defaults(monkeypatch):
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
    result = runner.invoke(cli, ["refresh-materialized-views"])

    assert result.exit_code == 0, result.output
    assert executed_sql == [
        "REFRESH MATERIALIZED VIEW ogc_latest_depth_to_water_wells",
        "REFRESH MATERIALIZED VIEW ogc_water_elevation_wells",
        "REFRESH MATERIALIZED VIEW ogc_avg_tds_wells",
        "REFRESH MATERIALIZED VIEW ogc_depth_to_water_trend_wells",
        "REFRESH MATERIALIZED VIEW ogc_water_well_summary",
        "REFRESH MATERIALIZED VIEW ogc_major_chemistry_results",
        "REFRESH MATERIALIZED VIEW ogc_minor_chemistry_wells",
        "REFRESH MATERIALIZED VIEW ogc_water_chemistry",
        "REFRESH MATERIALIZED VIEW ogc_internal_water_chemistry",
        "REFRESH MATERIALIZED VIEW ogc_internal_water_well_field_operations_stats",
        "REFRESH MATERIALIZED VIEW transducer_daily_data",
    ]
    assert commit_called["value"] is True
    assert "Refreshed 11 materialized view(s)." in result.output


def test_refresh_materialized_views_custom_and_concurrently(
    monkeypatch,
):
    executed_sql: list[str] = []
    execution_options: list[dict[str, object]] = []

    class FakeConnection:
        def execution_options(self, **kwargs):
            execution_options.append(kwargs)
            return self

        def execute(self, stmt):
            executed_sql.append(str(stmt))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr("db.engine.engine", FakeEngine())

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "refresh-materialized-views",
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


def test_refresh_materialized_views_rejects_invalid_identifier():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "refresh-materialized-views",
            "--view",
            "ogc_avg_tds_wells;drop table thing",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid SQL identifier" in result.output


class _FakeAreaGroup:
    """Stands in for a Group row without needing the database."""

    def __init__(self, group_id=1, release_status="public", project_area=None):
        self.id = group_id
        self.release_status = release_status
        self.project_area = project_area


class _FakeAreaSession:
    """Answers the one name lookup per feature that the planner makes."""

    def __init__(self, lookups):
        self._lookups = list(lookups)
        self.commit_called = False
        self.rollback_called = False
        self.added = []

    def scalars(self, stmt):
        groups = self._lookups.pop(0) if self._lookups else []
        return SimpleNamespace(all=lambda: groups)

    def get(self, model, item_id):
        return self.by_id[item_id]

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commit_called = True

    def rollback(self):
        self.rollback_called = True


def _area_feature(object_id, location, x=-106.9, y=33.9):
    return {
        "properties": {"OBJECTID": object_id, "location": location},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [x, y],
                    [x + 0.2, y],
                    [x + 0.2, y + 0.2],
                    [x, y + 0.2],
                    [x, y],
                ]
            ],
        },
    }


def _patch_area_import(monkeypatch, features, lookups, session=None):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    seen = {}

    def fake_fetch(client, layer_url):
        seen["layer_url"] = layer_url
        return features

    monkeypatch.setattr("cli.project_area_import.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "cli.project_area_import._fetch_project_area_features", fake_fetch
    )

    fake_session = session or _FakeAreaSession(lookups)
    fake_session.by_id = {group.id: group for groups in lookups for group in groups}

    class FakeSessionCtx:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("cli.project_area_import.session_ctx", lambda: FakeSessionCtx())
    return fake_session, seen


def test_import_project_area_boundaries_updates_mapped_group_by_objectid(monkeypatch):
    # OBJECTID 29 maps to 'S.Taos Valley', whose location is 'Southern Taos
    # Valley' -- the case that name matching cannot get right.
    group = _FakeAreaGroup(group_id=2)
    session, _ = _patch_area_import(
        monkeypatch,
        [_area_feature(29, "Southern Taos Valley")],
        [[group]],
    )

    result = CliRunner().invoke(cli, ["import-project-area-boundaries"])

    assert result.exit_code == 0, result.output
    assert "Updated 1 group(s)." in result.output
    assert group.project_area is not None
    assert session.commit_called is True


def test_import_project_area_boundaries_publishes_a_draft_group_it_writes_to(
    monkeypatch,
):
    group = _FakeAreaGroup(group_id=57, release_status="draft")
    _patch_area_import(monkeypatch, [_area_feature(12, "Carrizozo")], [[group]])

    result = CliRunner().invoke(cli, ["import-project-area-boundaries"])

    assert result.exit_code == 0, result.output
    assert "Published 1 group(s)." in result.output
    assert group.release_status == "public"


def test_import_project_area_boundaries_skips_unmapped_objectid(monkeypatch):
    session, _ = _patch_area_import(
        monkeypatch, [_area_feature(9999, "Somewhere New")], []
    )

    result = CliRunner().invoke(cli, ["import-project-area-boundaries"])

    assert result.exit_code == 0, result.output
    assert "Skipped 1 feature(s)." in result.output
    assert "not in PROJECT_AREA_MAPPINGS" in result.output
    assert session.added == []


def test_import_project_area_boundaries_keeps_duplicate_locations_apart(monkeypatch):
    # 40 and 41 share the location 'Gila-Animas'; each has its own group name,
    # and neither exists yet, so both are created rather than colliding.
    session, _ = _patch_area_import(
        monkeypatch,
        [_area_feature(40, "Gila-Animas"), _area_feature(41, "Gila-Animas")],
        [[], []],
    )

    result = CliRunner().invoke(cli, ["import-project-area-boundaries"])

    assert result.exit_code == 0, result.output
    assert "Created 2 group(s)." in result.output
    assert sorted(group.name for group in session.added) == [
        "Gila-Animas 1 (AEM)",
        "Gila-Animas 2 (AEM)",
    ]


def test_import_project_area_boundaries_dry_run_writes_nothing(monkeypatch):
    group = _FakeAreaGroup(group_id=2)
    session, _ = _patch_area_import(
        monkeypatch, [_area_feature(29, "Southern Taos Valley")], [[group]]
    )

    result = CliRunner().invoke(cli, ["import-project-area-boundaries", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "DRY RUN -- nothing written." in result.output
    assert "Updated 1 group(s)." in result.output
    assert group.project_area is None
    assert session.commit_called is False
    assert session.rollback_called is True


def test_import_project_area_boundaries_defaults_to_layer_18(monkeypatch):
    """Layer 17 was retired and 404s; a silent revert would break every import."""
    _, seen = _patch_area_import(monkeypatch, [], [])

    result = CliRunner().invoke(cli, ["import-project-area-boundaries"])

    assert result.exit_code == 0, result.output
    assert seen["layer_url"].endswith("/MapServer/18")


def test_initialize_lexicon_invokes_initializer(monkeypatch):
    called = {"count": 0}

    def fake_initializer():
        called["count"] += 1

    monkeypatch.setattr("core.initializers.init_lexicon", fake_initializer)

    runner = CliRunner()
    result = runner.invoke(cli, ["initialize-lexicon"])

    assert result.exit_code == 0
    assert called["count"] == 1


def test_associate_assets_command_calls_service(monkeypatch, tmp_path):
    captured = {}

    def fake_associate(source_directory):
        captured["path"] = Path(source_directory)
        return ["uri1"]

    monkeypatch.setattr("cli.service_adapter.associate_assets", fake_associate)

    asset_dir = tmp_path / "asset_import_batch"
    asset_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["associate-assets", str(asset_dir)])

    assert result.exit_code == 0, result.output
    assert captured["path"] == asset_dir


def test_restore_local_db_invokes_psql(monkeypatch, tmp_path):
    sql_file = tmp_path / "restore.sql"
    sql_file.write_text(
        "SET ROLE ocotillo;\n"
        "ALTER TABLE public.sample OWNER TO ocotillo;\n"
        "GRANT ALL ON TABLE public.sample TO ocotillo;\n"
        "select 1;\n"
    )
    captured: dict[str, object] = {}
    call_order: list[str] = []

    def fake_reset():
        call_order.append("reset")

    def fake_run(command, check, env, capture_output, text):
        call_order.append("psql")
        captured["command"] = command
        captured["check"] = check
        captured["env"] = env
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["restored_sql"] = Path(command[-1]).read_text()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("cli.db_restore._reset_target_schema", fake_reset)
    monkeypatch.setattr("cli.db_restore.subprocess.run", fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "nm_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "ocotilloapi_dev")

    runner = CliRunner()
    result = runner.invoke(cli, ["restore-local-db", str(sql_file)])

    assert result.exit_code == 0, result.output
    assert captured["command"][:-1] == [
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        "localhost",
        "-p",
        "5432",
        "-U",
        "nm_user",
        "-d",
        "ocotilloapi_dev",
        "-f",
    ]
    assert captured["command"][-1].endswith("/restore.sql")
    assert captured["check"] is True
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["env"]["PGPASSWORD"] == "secret"
    assert captured["restored_sql"] == "select 1;\n"
    assert call_order == ["reset", "psql"]
    assert "Restored" in result.output
    assert "ocotilloapi_dev" in result.output


def test_restore_local_db_rejects_non_sql_files(tmp_path):
    source_file = tmp_path / "restore.dump"
    source_file.write_text("not sql")

    runner = CliRunner()
    result = runner.invoke(cli, ["restore-local-db", str(source_file)])

    assert result.exit_code == 1
    assert "requires a .sql or .sql.gz source" in result.output


def test_restore_local_db_rejects_remote_host(monkeypatch, tmp_path):
    sql_file = tmp_path / "restore.sql"
    sql_file.write_text("select 1;\n")
    called = {"value": False}

    def fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("subprocess.run should not be called for remote hosts")

    monkeypatch.setattr("cli.db_restore.subprocess.run", fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "db.example.com")

    runner = CliRunner()
    result = runner.invoke(cli, ["restore-local-db", str(sql_file)])

    assert result.exit_code == 1
    assert "only supports local PostgreSQL hosts" in result.output
    assert called["value"] is False


def test_restore_local_db_reports_psql_failures(monkeypatch, tmp_path):
    sql_file = tmp_path / "restore.sql"
    sql_file.write_text("select 1;\n")

    def fake_run(command, check, env, capture_output, text):
        raise CalledProcessError(
            1,
            command,
            stderr='psql: role "missing" does not exist',
        )

    monkeypatch.setattr("cli.db_restore._reset_target_schema", lambda: None)
    monkeypatch.setattr("cli.db_restore.subprocess.run", fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_DB", "ocotilloapi_dev")

    runner = CliRunner()
    result = runner.invoke(cli, ["restore-local-db", str(sql_file)])

    assert result.exit_code == 1
    assert "Restore failed for database 'ocotilloapi_dev'" in result.output
    assert 'role "missing" does not exist' in result.output


def test_restore_local_db_downloads_and_restores_gcs_gzip(monkeypatch, tmp_path):
    source_uri = "gs://ocotillo/sql-exports/latest.sql.gz"
    sql_text = (
        "SET SESSION AUTHORIZATION 'ocotillo';\n"
        "REVOKE ALL ON SCHEMA public FROM ocotillo;\n"
        "select 42;\n"
    )
    gz_payload = gzip.compress(sql_text.encode("utf-8"))
    captured: dict[str, object] = {}

    class FakeBlob:
        def download_to_filename(self, filename):
            Path(filename).write_bytes(gz_payload)

    class FakeBucket:
        def __init__(self):
            self.requested_blob_name = None

        def blob(self, blob_name):
            self.requested_blob_name = blob_name
            captured["blob_name"] = blob_name
            return FakeBlob()

    fake_bucket = FakeBucket()

    def fake_get_storage_bucket(client=None, bucket=None):
        captured["bucket_name"] = bucket
        return fake_bucket

    def fake_run(command, check, env, capture_output, text):
        captured["command"] = command
        captured["restored_sql"] = Path(command[-1]).read_text()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("cli.db_restore._reset_target_schema", lambda: None)
    monkeypatch.setattr(
        "cli.db_restore.get_storage_bucket",
        fake_get_storage_bucket,
    )
    monkeypatch.setattr("cli.db_restore.subprocess.run", fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_DB", "ocotilloapi_dev")

    runner = CliRunner()
    result = runner.invoke(cli, ["restore-local-db", source_uri])

    assert result.exit_code == 0, result.output
    assert captured["bucket_name"] == "ocotillo"
    assert captured["blob_name"] == "sql-exports/latest.sql.gz"
    assert captured["restored_sql"] == "select 42;\n"
    assert captured["command"][-2:] == ["-f", captured["command"][-1]]
    assert source_uri in result.output


def test_restore_local_db_reports_schema_reset_failures(monkeypatch, tmp_path):
    sql_file = tmp_path / "restore.sql"
    sql_file.write_text("select 1;\n")
    called = {"psql": False}

    def fake_reset():
        raise RuntimeError("permission denied to drop schema public")

    def fake_run(*args, **kwargs):
        called["psql"] = True
        raise AssertionError("psql should not be called when schema reset fails")

    monkeypatch.setattr("cli.db_restore._reset_target_schema", fake_reset)
    monkeypatch.setattr("cli.db_restore.subprocess.run", fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_DB", "ocotilloapi_dev")

    runner = CliRunner()
    result = runner.invoke(cli, ["restore-local-db", str(sql_file)])

    assert result.exit_code == 1
    assert "permission denied to drop schema public" in result.output
    assert called["psql"] is False


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

    monkeypatch.setattr(
        "cli.service_adapter.well_inventory_csv",
        fake_well_inventory,
    )

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
        "transfers.transfer_results_builder.TransferResultsBuilder",
        FakeBuilder,
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

    monkeypatch.setattr(
        "cli.service_adapter.well_inventory_csv",
        fake_well_inventory,
    )

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


def test_water_levels_bulk_upload_reports_partial_success(monkeypatch, tmp_path):
    csv_file = tmp_path / "water_levels.csv"
    csv_file.write_text("col\nvalue\n")

    def fake_upload(_file_path, *, pretty_json=False):
        assert pretty_json is False
        return SimpleNamespace(
            exit_code=0,
            stdout="",
            stderr="Row 2: Unknown well_name_point_id 'Bad Well'",
            payload={
                "summary": {
                    "total_rows_processed": 2,
                    "total_rows_imported": 1,
                    "validation_errors_or_warnings": 1,
                },
                "validation_errors": ["Row 2: Unknown well_name_point_id 'Bad Well'"],
                "water_levels": [{}],
            },
        )

    monkeypatch.setattr("cli.service_adapter.water_levels_csv", fake_upload)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["water-levels", "bulk-upload", "--file", str(csv_file)]
    )

    assert result.exit_code == 0, result.output
    assert "[WATER LEVEL IMPORT] COMPLETED WITH ISSUES" in result.output
    assert "rows_with_issues" in result.output


def test_water_levels_cli_persists_observations(tmp_path, water_well_thing):
    """
    End-to-end CLI invocation should create FieldEvent, Sample,
    and Observation rows.
    """

    def _write_csv(path: Path, *, well_name: str, notes: str):
        header = (
            "field_staff,well_name_point_id,field_event_date_time,"
            "measurement_date_time,sampler,sample_method,mp_height,"
            "level_status,depth_to_water_ft,data_quality,"
            "water_level_notes"
        )
        row = (
            f"CLI Tester,{well_name},2025-02-15T08:00:00-07:00,"
            "2025-02-15T10:30:00-07:00,CLI Tester,electric tape,"
            f"1.5,Water level not affected,7.0,"
            "Water level accurate to within two hundreths of a foot,"
            f"{notes}"
        )
        csv_text = textwrap.dedent(
            f"""\
            {header}
            {row}
            """
        )
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
        assert sample.sample_matrix == "groundwater"
        assert sample.sample_name == f"{water_well_thing.name}-WL-202502151730"
        assert observation.value == 7.0
        assert observation.measuring_point_height == 1.5
        assert observation.notes == unique_notes
        assert observation.groundwater_level_reason == "Water level not affected"
        assert (
            observation.nma_data_quality
            == "Water level accurate to within two hundreths of a foot"
        )
        assert field_event.notes == unique_notes
        assert field_activity.notes is None

        created_ids = {
            "observation_id": observation.id,
            "sample_id": sample.id,
            "field_activity_id": field_activity.id,
            "field_event_id": field_event.id,
        }

    if created_ids:
        # Clean up committed rows so other tests see a pristine database.
        with session_ctx() as session:
            # Collect participant contacts before deleting the field event so
            # importer-created staff contacts do not leak into later tests.
            participant_contact_ids = session.scalars(
                select(FieldEventParticipant.contact_id).where(
                    FieldEventParticipant.field_event_id
                    == created_ids["field_event_id"]
                )
            ).all()
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
            for contact_id in participant_contact_ids:
                contact = session.get(Contact, contact_id)
                if contact:
                    session.delete(contact)
                    session.flush()

            session.commit()


# ============= EOF =============================================
