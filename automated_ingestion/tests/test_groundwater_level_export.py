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
The groundwater level export (OCO-79), end to end on a local directory.

The steps run for real -- pyarrow writes real GeoParquet, the checks read it
back -- against ``LocalStorage`` instead of GCS. The fakes are at the process
boundaries only: the database read, the STAC API, and Cloud Run itself, which
the Dagster test replaces with an in-process call to the same worker.
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from automated_ingestion.exports.groundwater_levels import rules, steps, worker
from automated_ingestion.exports.groundwater_levels.storage import (
    LocalStorage,
    read_json,
)

T0 = datetime(2020, 1, 1, 17, 30, tzinfo=timezone.utc)
SNAP = "20261116T091500Z-abcd1234"


def _row(well, thing_id, obs_id, days, depth, lon=-106.9, lat=34.05):
    return {
        "well_id": well,
        "thing_id": thing_id,
        "observation_id": obs_id,
        "datetime": T0 + timedelta(days=days),
        "depth_to_water_bgs": depth - 1.5,
        "depth_to_water_below_mp": depth,
        "measuring_point_height": 1.5,
        "unit": "ft",
        "measurement_method": "Steel-tape measurement",
        "data_quality": None,
        "groundwater_level_reason": None,
        "longitude": lon,
        "latitude": lat,
    }


def _rows():
    return [
        _row("SO-0001", 1, 11, 0, 100.0),
        _row("SO-0001", 1, 12, 30, 101.25),
        # Out of order on purpose: the snapshot step owns the sort.
        _row("SO-0001", 1, 10, -30, 99.5),
        _row("SO-0002", 2, 20, 0, 55.0, lon=-106.8),
        _row("AB 3/x", 3, 30, 5, 210.0, lon=-106.7),
    ]


def _counts(rows):
    out: dict[str, int] = {}
    for r in rows:
        out[r["well_id"]] = out.get(r["well_id"], 0) + 1
    return out


class FakeStac:
    base_url = "https://stac.example.test"

    def __init__(self):
        self.collections = []
        self.items: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []

    def ensure_collection(self, collection):
        self.collections.append(collection["id"])

    def upsert_item(self, collection_id, item):
        self.calls.append(("upsert", item["id"]))
        self.items[item["id"]] = item

    def delete_item(self, collection_id, item_id):
        self.calls.append(("delete", item_id))
        self.items.pop(item_id, None)


def _pipeline(storage, snapshot_id, rows, stac=None, tasks=2):
    steps.snapshot(storage, snapshot_id, rows, _counts(rows), T0)
    for i in range(tasks):
        steps.convert(storage, snapshot_id, i, tasks)
    steps.check(storage, snapshot_id)
    steps.publish(storage, snapshot_id)
    return steps.register(
        storage, snapshot_id, "https://files.example.test/gwl", stac=stac
    )


# ---------------------------------------------------------------------- rules
def test_safe_well_id_replaces_path_hostile_characters():
    assert rules.safe_well_id("AB 3/x") == "AB_3_x"
    assert rules.item_id("SO-0001") == "gwl-SO-0001"
    assert rules.published_paths("SO-0001")["parquet"] == (
        "groundwater-levels/SO-0001/gwl-SO-0001.parquet"
    )


def test_colliding_well_ids_are_rejected():
    with pytest.raises(rules.ExportRuleError):
        rules.assert_unique(["AB 1", "AB/1"])


def test_hash_ignores_nothing_and_depends_on_order():
    rows = sorted(_rows()[:3], key=rules.sort_key)
    same = rules.well_content_hash([dict(r) for r in rows])
    assert rules.well_content_hash(rows) == same
    assert rules.well_content_hash(list(reversed(rows))) != same
    edited = [dict(r) for r in rows]
    edited[0]["data_quality"] = "Water level accurate to within one foot"
    assert rules.well_content_hash(edited) != same


def test_plan_finds_changed_unchanged_and_withdrawn():
    plan = rules.plan_changes(
        {"A": "1", "B": "2", "C": "3"}, {"A": "1", "B": "x", "D": "4"}
    )
    assert plan.changed == ["B", "C"]
    assert plan.unchanged == ["A"]
    assert plan.withdrawn == ["D"]


def test_shards_cover_every_well_exactly_once():
    wells = [f"W{i:03d}" for i in range(23)]
    shards = [rules.shard(wells, i, 4) for i in range(4)]
    assert sorted(w for s in shards for w in s) == wells
    assert max(map(len, shards)) - min(map(len, shards)) <= 1


def test_out_of_range_depth_is_a_warning_not_an_error():
    result = rules.check_well(
        "W",
        expected_rows=2,
        parquet_rows=2,
        csv_rows=2,
        schema_names=[*rules.COLUMN_NAMES, "geometry"],
        null_ids=0,
        sorted_by_time=True,
        depths=[12.0, 99999.0],
    )
    assert result.errors == []
    assert len(result.warnings) == 1


# ---------------------------------------------------------------- the steps
def test_full_run_publishes_files_items_and_state(tmp_path):
    storage = LocalStorage(tmp_path)
    stac = FakeStac()
    report = _pipeline(storage, SNAP, _rows(), stac=stac)

    assert report["registered"] == 3
    assert stac.collections == ["groundwater-levels"]
    assert set(stac.items) == {"gwl-SO-0001", "gwl-SO-0002", "gwl-AB_3_x"}

    # GeoParquet: typed, sorted, with geo metadata.
    paths = rules.published_paths("SO-0001")
    table = pq.read_table(tmp_path / paths["parquet"])
    assert table.num_rows == 3
    assert table.schema.names == [*rules.COLUMN_NAMES, "geometry"]
    assert table.schema.field("datetime").type == pa.timestamp("us", tz="UTC")
    assert table["observation_id"].to_pylist() == [10, 11, 12]
    geo = json.loads(table.schema.metadata[b"geo"])
    assert geo["primary_column"] == "geometry"
    assert geo["columns"]["geometry"]["encoding"] == "WKB"
    assert (
        pq.read_metadata(tmp_path / paths["parquet"]).row_group(0).column(0).compression
        == "ZSTD"
    )

    # CSV: BOM, header, ISO UTC times.
    text = (tmp_path / paths["csv"]).read_bytes().decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    assert [r["observation_id"] for r in rows] == ["10", "11", "12"]
    assert rows[1]["datetime"] == "2020-01-01T17:30:00Z"

    # STAC item points at the fixed path, with a matching checksum.
    item = stac.items["gwl-SO-0001"]
    assert item["collection"] == "groundwater-levels"
    assert item["assets"]["data"]["href"] == (
        "https://files.example.test/gwl/" + paths["parquet"]
    )
    assert item["assets"]["csv"]["file:size"] == len(text.encode("utf-8"))
    assert item["properties"]["nmbgmr:observation_count"] == 3
    assert item["properties"]["start_datetime"] == "2019-12-02T17:30:00Z"
    assert json.loads((tmp_path / paths["item"]).read_text())["id"] == "gwl-SO-0001"

    state = read_json(storage, rules.STATE_PATH)
    assert state["snapshot_id"] == SNAP
    assert set(state["wells"]) == {"SO-0001", "SO-0002", "AB 3/x"}


def test_rerun_without_changes_writes_no_files_and_calls_no_stac(tmp_path):
    storage = LocalStorage(tmp_path)
    stac = FakeStac()
    _pipeline(storage, SNAP, _rows(), stac=stac)
    published = tmp_path / rules.published_paths("SO-0001")["parquet"]
    mtime = published.stat().st_mtime_ns
    stac.calls.clear()

    report = _pipeline(storage, "20261117T091500Z-ffff0000", _rows(), stac=stac)

    assert report["registered"] == 0
    assert stac.calls == []
    assert published.stat().st_mtime_ns == mtime
    assert storage.list("_runs/20261117T091500Z-ffff0000/wells") == []


def test_one_changed_value_republishes_only_that_well(tmp_path):
    storage = LocalStorage(tmp_path)
    stac = FakeStac()
    _pipeline(storage, SNAP, _rows(), stac=stac)
    stac.calls.clear()

    rows = _rows()
    rows[3]["depth_to_water_bgs"] = 56.0  # SO-0002
    _pipeline(storage, "20261117T091500Z-ffff0000", rows, stac=stac)

    assert stac.calls == [("upsert", "gwl-SO-0002")]


def test_well_no_longer_public_is_withdrawn(tmp_path):
    storage = LocalStorage(tmp_path)
    stac = FakeStac()
    _pipeline(storage, SNAP, _rows(), stac=stac)

    rows = [r for r in _rows() if r["well_id"] != "SO-0002"]
    _pipeline(storage, "20261117T091500Z-ffff0000", rows, stac=stac)

    paths = rules.published_paths("SO-0002")
    assert not (tmp_path / paths["parquet"]).exists()
    assert not (tmp_path / paths["csv"]).exists()
    assert not (tmp_path / paths["item"]).exists()
    assert "gwl-SO-0002" not in stac.items
    assert "SO-0002" not in read_json(storage, rules.STATE_PATH)["wells"]


def test_configuring_the_stac_api_later_backfills_every_item(tmp_path):
    storage = LocalStorage(tmp_path)
    _pipeline(storage, SNAP, _rows(), stac=None)  # before OCO-78 exists
    stac = FakeStac()

    report = _pipeline(storage, "20261117T091500Z-ffff0000", _rows(), stac=stac)

    assert report["registered"] == 3
    assert len(stac.items) == 3


def test_snapshot_rejects_rows_that_disagree_with_db_counts(tmp_path):
    rows = _rows()
    with pytest.raises(steps.StepError):
        steps.snapshot(LocalStorage(tmp_path), SNAP, rows, {"SO-0001": 3}, T0)


def test_tampered_file_fails_checks_and_blocks_publish(tmp_path):
    storage = LocalStorage(tmp_path)
    rows = _rows()
    steps.snapshot(storage, SNAP, rows, _counts(rows), T0)
    steps.convert(storage, SNAP)
    staged = rules.staged_paths(SNAP, "SO-0001")["csv"]
    storage.write_bytes(staged, storage.read_bytes(staged) + b"extra,row\r\n")

    with pytest.raises(steps.StepError):
        steps.check(storage, SNAP)
    assert read_json(storage, f"_runs/{SNAP}/reports/check.json")["errors"]
    with pytest.raises(steps.StepError):
        steps.publish(storage, SNAP)
    assert not storage.exists(rules.published_paths("SO-0001")["csv"])


def test_publish_refuses_a_snapshot_never_checked(tmp_path):
    storage = LocalStorage(tmp_path)
    rows = _rows()
    steps.snapshot(storage, SNAP, rows, _counts(rows), T0)
    steps.convert(storage, SNAP)
    with pytest.raises(steps.StepError):
        steps.publish(storage, SNAP)


def test_worker_cli_runs_a_step_and_exits_nonzero_on_step_error(tmp_path, capsys):
    storage = LocalStorage(tmp_path)
    rows = _rows()
    steps.snapshot(storage, SNAP, rows, _counts(rows), T0)

    assert worker.main(["convert", "--snapshot-id", SNAP, "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["gwl_export"]["wells"] == 3
    assert worker.main(["publish", "--snapshot-id", SNAP, "--root", str(tmp_path)]) == 1


# ----------------------------------------------------------------- Cloud Run
class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.text = json.dumps(body)

    def json(self):
        return self._body


class FakeSession:
    EXEC = "projects/p/locations/r/jobs/gwl-export/executions/gwl-export-abc"

    def __init__(self, final, polls=1):
        self.final = final
        self.polls = polls
        self.posts: list[tuple[str, dict]] = []

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        return FakeResponse(
            {
                "name": "projects/p/locations/r/operations/op1",
                "metadata": {"name": self.EXEC},
                "done": False,
            }
        )

    def get(self, url, timeout=None):
        self.polls -= 1
        if self.polls > 0:
            return FakeResponse(
                {"name": "projects/p/locations/r/operations/op1", "done": False}
            )
        return FakeResponse({"name": "op1", "done": True, **self.final})


def test_run_job_sends_overrides_and_returns_execution():
    from automated_ingestion.shared.cloud_run import run_job

    session = FakeSession(
        {
            "response": {
                "name": FakeSession.EXEC,
                "succeededCount": 3,
                "taskCount": 3,
                "logUri": "https://logs",
            }
        },
        polls=2,
    )
    execution = run_job(
        session,
        "projects/p/locations/r/jobs/gwl-export",
        ["convert", "--snapshot-id", "S"],
        task_count=3,
        sleep=lambda _: None,
    )

    url, body = session.posts[0]
    assert url.endswith("/v2/projects/p/locations/r/jobs/gwl-export:run")
    assert body["overrides"]["containerOverrides"][0]["args"] == [
        "convert",
        "--snapshot-id",
        "S",
    ]
    assert body["overrides"]["taskCount"] == 3
    assert execution.short_name == "gwl-export-abc"
    assert execution.log_uri == "https://logs"


def test_run_job_raises_on_failed_tasks():
    from automated_ingestion.shared.cloud_run import CloudRunExecutionFailed, run_job

    session = FakeSession(
        {"response": {"succeededCount": 1, "failedCount": 1, "taskCount": 2}}
    )
    with pytest.raises(CloudRunExecutionFailed):
        run_job(
            session,
            "projects/p/locations/r/jobs/j",
            ["check"],
            task_count=2,
            sleep=lambda _: None,
        )


def test_run_job_raises_on_operation_error():
    from automated_ingestion.shared.cloud_run import CloudRunExecutionFailed, run_job

    session = FakeSession(
        {"error": {"code": 2, "message": "Task gwl-export-abc-task0 failed"}}
    )
    with pytest.raises(CloudRunExecutionFailed, match="failed"):
        run_job(
            session, "projects/p/locations/r/jobs/j", ["check"], sleep=lambda _: None
        )


def test_interrupted_wait_cancels_the_execution():
    from automated_ingestion.shared.cloud_run import run_job

    session = FakeSession({}, polls=99)

    def interrupt(_):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_job(session, "projects/p/locations/r/jobs/j", ["snapshot"], sleep=interrupt)
    assert session.posts[-1][0].endswith(f"{FakeSession.EXEC}:cancel")


# ------------------------------------------------------------------- Dagster
def test_assets_run_every_step_in_order(tmp_path, monkeypatch):
    """All five assets, with Cloud Run replaced by the same worker in-process."""
    from dagster import materialize

    from automated_ingestion.defs.assets.groundwater_level_export import (
        GROUNDWATER_LEVEL_EXPORT_ASSETS,
    )
    from automated_ingestion.defs.resources import CloudRunJob, ExportStorage
    from automated_ingestion.shared.cloud_run import CloudRunExecution

    monkeypatch.setenv(worker.PUBLIC_BASE_URL_ENV_VAR, "https://files.example.test")
    monkeypatch.delenv("STAC_API_URL", raising=False)
    launched: list[tuple[str, int]] = []
    rows = _rows()

    class InProcessCloudRun(CloudRunJob):
        def run(self, context, args, task_count=1, timeout_seconds=3600):
            step, snapshot_id, root = args[0], args[2], args[4]
            launched.append((step, task_count))
            if step == "snapshot":  # the only step that needs the database
                steps.snapshot(LocalStorage(root), snapshot_id, rows, _counts(rows), T0)
            else:
                for i in range(task_count):
                    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", str(i))
                    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", str(task_count))
                    worker.run(step, snapshot_id, root)
            return CloudRunExecution(name=f"x/executions/{step}", succeeded=task_count)

    resources = {
        "cloud_run": InProcessCloudRun(project="p", region="r", job="gwl-export"),
        "export_storage": ExportStorage(root=str(tmp_path)),
    }
    result = materialize(
        GROUNDWATER_LEVEL_EXPORT_ASSETS,
        resources=resources,
        run_config={"ops": {"gwl_well_files": {"config": {"wells_per_task": 2}}}},
    )

    assert result.success
    assert launched == [
        ("snapshot", 1),
        ("convert", 2),
        ("check", 1),
        ("publish", 1),
        ("register", 1),
    ]
    stac = result.asset_materializations_for_node("gwl_stac_items")[0].metadata
    assert stac["items_registered"].value == 3
    assert (tmp_path / rules.published_paths("SO-0002")["item"]).exists()

    # Second run, nothing changed: convert launches no Cloud Run execution.
    launched.clear()
    assert materialize(GROUNDWATER_LEVEL_EXPORT_ASSETS, resources=resources).success
    assert [s for s, _ in launched] == ["snapshot", "check", "publish", "register"]


def test_export_job_and_schedule_are_registered():
    from automated_ingestion.defs.definitions import defs

    job = defs.resolve_job_def("groundwater_level_export")
    assert job is not None
    schedule = defs.resolve_schedule_def("groundwater_level_export_nightly")
    assert schedule.default_status.value == "STOPPED"


# ============= EOF =============================================
