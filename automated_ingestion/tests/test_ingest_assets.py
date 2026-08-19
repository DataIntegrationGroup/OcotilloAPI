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
The Dagster assets, which is where the pieces meet.

Every part of `san_acacia_observations` is covered on its own -- matching,
resolving, watermarks, the adapter, the loader. What was not covered is the
orchestration between them: which wells get skipped, what the metadata says, and
whether one unresolvable well costs the others.

Fakes stand in at the process boundaries -- the vendor client, the database
session, the dlt pipeline -- and nowhere else. The reconciler, resolver and
adapter run for real, so a change in their behaviour shows up here.
"""

from contextlib import contextmanager
from datetime import date

import pytest
from dagster import build_asset_context

from automated_ingestion.ocotillo import loader as loader_module
from automated_ingestion.ocotillo.loader import LoadResult
from automated_ingestion.shared import watermark as watermark_module
from automated_ingestion.sources.san_acacia import ingest
from automated_ingestion.sources.san_acacia.reconcile import ThingCandidate
from automated_ingestion.sources.san_acacia.resolve import DeploymentCandidate

READING = {"dateAndTime": "2026-04-15T22:45:00", "level": 471.518}


class FakeClient:
    """The vendor, reduced to what the assets ask of it."""

    def __init__(self, points, readings=None, approved=()):
        self._points = points
        self._readings = READING if readings is None else readings
        self._approved = approved
        self.water_level_calls = []

    def monitoring_points(self, project_id):
        return self._points

    def water_levels(self, point_id, start, end, reference, approved=None, span=None):
        self.water_level_calls.append((point_id, start, end, approved))
        if approved:
            return iter(self._approved)
        return iter(
            self._readings if isinstance(self._readings, list) else [self._readings]
        )


class FakeDatabase:
    """Stands in for OcotilloDatabase. The session is never really used --
    every function that would touch it is replaced."""

    @contextmanager
    def session(self):
        yield object()


class NoWatermark:
    def __init__(self, session):
        pass

    def get(self, thing_id, parameter_id):
        return None


@pytest.fixture()
def wired(monkeypatch):
    """Wire the asset to fakes, returning the recorded loads."""
    loaded = []

    def fake_load(session, records, deployment_id, parameter_id, release_status, **kw):
        records = list(records)
        loaded.append(
            {
                "deployment_id": deployment_id,
                "parameter_id": parameter_id,
                "release_status": release_status,
                "rows": len(records),
            }
        )
        return LoadResult(rows_seen=len(records), rows_written=len(records), batches=1)

    monkeypatch.setattr(loader_module, "load_observations", fake_load)
    monkeypatch.setattr(loader_module, "ensure_block", lambda *a, **k: 1)
    monkeypatch.setattr(watermark_module, "PostgresWatermarkStore", NoWatermark)
    monkeypatch.setattr(ingest, "_parameter_id", lambda session, name: 1)
    return loaded


def _run(monkeypatch, client, candidates, deployments):
    monkeypatch.setattr(ingest, "_client", lambda: client)
    monkeypatch.setattr(ingest, "_well_candidates", lambda session: candidates)
    monkeypatch.setattr(ingest, "_deployments", lambda session, thing_id: deployments)
    return ingest.san_acacia_observations(build_asset_context(), FakeDatabase())


TRANSDUCER = DeploymentCandidate(437, "Pressure Transducer")


class TestObservationsAsset:
    def test_a_resolvable_well_is_loaded(self, monkeypatch, wired):
        output = _run(
            monkeypatch,
            FakeClient([{"id": 39, "name": "SO-0125"}]),
            [ThingCandidate(2343, "SO-0125")],
            [TRANSDUCER],
        )
        assert output.value == 1
        assert wired[0]["deployment_id"] == 437
        assert wired[0]["release_status"] == "public"
        assert output.metadata["wells_skipped"].value == 0

    def test_an_unmatched_well_is_skipped_not_invented(self, monkeypatch, wired):
        # No Ocotillo well by that name. Ingestion does not create wells.
        output = _run(
            monkeypatch,
            FakeClient([{"id": 39, "name": "SO-9999"}]),
            [ThingCandidate(2343, "SO-0125")],
            [TRANSDUCER],
        )
        assert output.value == 0
        assert wired == []
        assert output.metadata["wells_skipped"].value == 1
        assert "unmatched" in str(output.metadata["skipped"].data)

    def test_an_ambiguous_well_is_skipped(self, monkeypatch, wired):
        # Two wells share the name -- picking one would be a silent guess.
        output = _run(
            monkeypatch,
            FakeClient([{"id": 39, "name": "SO-0125"}]),
            [ThingCandidate(1, "SO-0125"), ThingCandidate(2, "SO-0125")],
            [TRANSDUCER],
        )
        assert wired == []
        assert "ambiguous" in str(output.metadata["skipped"].data)

    def test_a_well_without_a_transducer_is_skipped(self, monkeypatch, wired):
        # SO-0246 is in this state in production.
        output = _run(
            monkeypatch,
            FakeClient([{"id": 39, "name": "SO-0125"}]),
            [ThingCandidate(2343, "SO-0125")],
            [DeploymentCandidate(436, "DiverLink")],
        )
        assert wired == []
        assert "missing" in str(output.metadata["skipped"].data)

    def test_a_removed_transducer_does_not_qualify(self, monkeypatch, wired):
        output = _run(
            monkeypatch,
            FakeClient([{"id": 39, "name": "SO-0125"}]),
            [ThingCandidate(2343, "SO-0125")],
            [
                DeploymentCandidate(
                    437, "Pressure Transducer", removal_date=date(2024, 1, 1)
                )
            ],
        )
        assert wired == []

    def test_one_bad_well_does_not_cost_the_others(self, monkeypatch, wired):
        # The point of skipping rather than raising.
        output = _run(
            monkeypatch,
            FakeClient(
                [
                    {"id": 39, "name": "SO-9999"},
                    {"id": 40, "name": "SO-0125"},
                ]
            ),
            [ThingCandidate(2343, "SO-0125")],
            [TRANSDUCER],
        )
        assert output.value == 1
        assert output.metadata["wells_attempted"].value == 2
        assert output.metadata["wells_skipped"].value == 1

    def test_a_reading_the_adapter_refuses_is_counted(self, monkeypatch, wired):
        # A null level has nothing to store; it should surface, not vanish.
        client = FakeClient(
            [{"id": 39, "name": "SO-0125"}],
            readings=[{"dateAndTime": "2026-04-15T22:45:00", "level": None}],
        )
        output = _run(
            monkeypatch, client, [ThingCandidate(2343, "SO-0125")], [TRANSDUCER]
        )
        assert output.value == 0
        assert output.metadata["adapter_failures"].value == 1

    def test_no_wells_at_all(self, monkeypatch, wired):
        output = _run(monkeypatch, FakeClient([]), [], [TRANSDUCER])
        assert output.value == 0
        assert output.metadata["wells_attempted"].value == 0


class TestParameterLookup:
    def test_a_missing_parameter_is_a_clear_error(self):
        # Ingestion does not create parameters, so the message has to say what
        # to do instead of surfacing an integrity error later.
        class Empty:
            def scalar(self, *_):
                return None

        with pytest.raises(RuntimeError, match="does not create parameters"):
            ingest._parameter_id(Empty(), "groundwater level")

    def test_a_found_parameter_is_returned(self):
        class Found:
            def scalar(self, *_):
                return 7

        assert ingest._parameter_id(Found(), "groundwater level") == 7


class TestRowCount:
    def test_malformed_load_info_reports_zero(self):
        # Metadata must never fail a load that worked.
        assert ingest._row_count(object()) == 0

    def test_none_reports_zero(self):
        assert ingest._row_count(None) == 0


class FakePipeline:
    """Stands in for the dlt pipeline. Records what it was asked to run."""

    def __init__(self):
        self.runs = []

    def run(self, resource, loader_file_format=None):
        # Consume the resource so the generator body actually executes.
        rows = list(resource) if hasattr(resource, "__iter__") else []
        self.runs.append({"format": loader_file_format, "rows": len(rows)})
        return object()


class TestRawAssets:
    def test_locations_reports_what_it_landed(self, monkeypatch):
        from automated_ingestion.sources.san_acacia import dlt_pipeline

        pipeline = FakePipeline()
        client = FakeClient(
            [{"id": 39, "name": "SO-0125"}, {"id": 40, "name": "SO-0131"}]
        )
        monkeypatch.setattr(ingest, "_client", lambda: client)
        monkeypatch.setattr(dlt_pipeline, "build_pipeline", lambda: pipeline)

        output = ingest.raw_san_acacia_locations(build_asset_context())

        assert output.value == 2
        assert output.metadata["monitoring_points"].value == 2
        assert "SO-0125" in output.metadata["names"].value

    def test_locations_are_written_as_parquet(self, monkeypatch):
        # dlt writes gzipped JSONL unless told otherwise, and Mode B replay
        # assumes parquet.
        from automated_ingestion.sources.san_acacia import dlt_pipeline

        pipeline = FakePipeline()
        monkeypatch.setattr(ingest, "_client", lambda: FakeClient([]))
        monkeypatch.setattr(dlt_pipeline, "build_pipeline", lambda: pipeline)

        ingest.raw_san_acacia_locations(build_asset_context())
        assert pipeline.runs[0]["format"] == "parquet"

    def test_readings_report_per_point_failures(self, monkeypatch):
        from automated_ingestion.sources.san_acacia import dlt_pipeline

        pipeline = FakePipeline()
        client = FakeClient([{"id": 39, "name": "SO-0125"}])
        monkeypatch.setattr(ingest, "_client", lambda: client)
        monkeypatch.setattr(dlt_pipeline, "build_pipeline", lambda: pipeline)

        output = ingest.raw_san_acacia_readings(build_asset_context())

        assert output.metadata["points_attempted"].value == 1
        assert output.metadata["points_failed"].value == 0

    def test_readings_are_written_as_parquet(self, monkeypatch):
        from automated_ingestion.sources.san_acacia import dlt_pipeline

        pipeline = FakePipeline()
        monkeypatch.setattr(ingest, "_client", lambda: FakeClient([]))
        monkeypatch.setattr(dlt_pipeline, "build_pipeline", lambda: pipeline)

        ingest.raw_san_acacia_readings(build_asset_context())
        assert pipeline.runs[0]["format"] == "parquet"

    def test_readings_count_a_point_the_vendor_refuses(self, monkeypatch):
        # One diver failing must cost that diver, not the run. The count is how
        # anyone finds out it happened.
        from automated_ingestion.sources.san_acacia import dlt_pipeline
        from automated_ingestion.sources.san_acacia.client import DiverHubError

        class Refusing(FakeClient):
            def water_levels(self, *a, **kw):
                raise DiverHubError("500 at the minimum window")

        pipeline = FakePipeline()
        client = Refusing([{"id": 39, "name": "SO-0125"}])
        monkeypatch.setattr(ingest, "_client", lambda: client)
        monkeypatch.setattr(dlt_pipeline, "build_pipeline", lambda: pipeline)

        output = ingest.raw_san_acacia_readings(build_asset_context())

        assert output.metadata["points_failed"].value == 1
        assert output.metadata["points_attempted"].value == 1
        assert "500" in str(output.metadata["failures"].data)


# ============= EOF =============================================
