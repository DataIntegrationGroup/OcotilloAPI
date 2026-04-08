from types import SimpleNamespace
from contextlib import contextmanager

import pandas as pd
import pytest

from transfers import transfer as transfer_module
from transfers import thing_transfer as thing_transfer_module
from transfers import well_transfer_util as well_transfer_util_module


class _FakeExecuteResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self):
        self.inserted_location_rows = []
        self.inserted_thing_rows = []
        self.commits = 0

    def execute(self, statement, rows):
        table_name = statement.table.name
        if table_name == "location":
            self.inserted_location_rows.extend(rows)
            returned = [
                (index + 1, row["nma_pk_location"]) for index, row in enumerate(rows)
            ]
            return _FakeExecuteResult(returned)
        if table_name == "thing":
            self.inserted_thing_rows.extend(rows)
            returned = [
                (index + 10, row["nma_pk_location"]) for index, row in enumerate(rows)
            ]
            return _FakeExecuteResult(returned)
        return _FakeExecuteResult()

    def commit(self):
        self.commits += 1


def test_normalize_test_pointids_dedupes_and_upcases():
    pointids = transfer_module._normalize_test_pointids(" sm-0001,SM-0001, sp-1 ")

    assert pointids == ["SM-0001", "SP-1"]


def test_validate_scoped_pointids_or_raise_raises_for_missing(monkeypatch):
    monkeypatch.setattr(
        transfer_module,
        "_collect_available_scoped_pointids",
        lambda _opts: {"SM-0001"},
    )
    opts = transfer_module.load_transfer_options()

    with pytest.raises(RuntimeError, match="MISSING-1"):
        transfer_module._validate_scoped_pointids_or_raise(
            ["SM-0001", "MISSING-1"], opts
        )


def test_execute_session_transfer_with_timing_passes_pointids(monkeypatch):
    seen = {}

    @contextmanager
    def fake_session_ctx():
        yield object()

    monkeypatch.setattr(transfer_module, "session_ctx", fake_session_ctx)

    def fake_transfer(session, limit=None, pointids=None):
        seen["limit"] = limit
        seen["pointids"] = pointids
        return "ok"

    name, result, _elapsed = transfer_module._execute_session_transfer_with_timing(
        "Fake",
        fake_transfer,
        30,
        ["SM-0001"],
    )

    assert name == "Fake"
    assert result == "ok"
    assert seen["limit"] == 3
    assert seen["pointids"] == ["SM-0001"]


def test_transfer_thing_filters_to_requested_pointids(monkeypatch):
    location_df = pd.DataFrame(
        [
            {
                "SiteType": "SP",
                "PointID": "PT-1",
                "Easting": 1,
                "Northing": 1,
                "LocationId": "loc-1",
                "PublicRelease": True,
            },
            {
                "SiteType": "SP",
                "PointID": "PT-2",
                "Easting": 2,
                "Northing": 2,
                "LocationId": "loc-2",
                "PublicRelease": False,
            },
        ]
    )

    fake_location = SimpleNamespace(
        nma_pk_location="loc-1",
        description=None,
        point="POINT",
        elevation=1.0,
        release_status="public",
        nma_date_created=None,
        nma_site_date=None,
        nma_location_notes=None,
        nma_coordinate_notes=None,
        nma_data_reliability=None,
    )

    monkeypatch.setattr(thing_transfer_module, "_get_location_df", lambda: location_df)
    monkeypatch.setattr(
        thing_transfer_module,
        "make_location",
        lambda row, _cache: (fake_location, "manual", {}),
    )
    monkeypatch.setattr(
        thing_transfer_module,
        "make_location_data_provenance",
        lambda row, location_stub, elevation_method: [],
    )

    session = _FakeSession()

    thing_transfer_module.transfer_thing(
        session,
        "SP",
        lambda row: {
            "name": row.PointID,
            "thing_type": "spring",
            "release_status": "public",
        },
        pointids=["PT-1"],
    )

    assert [row["name"] for row in session.inserted_thing_rows] == ["PT-1"]


def test_cleanup_locations_scopes_to_requested_pointids(monkeypatch):
    class FakeBlob:
        def exists(self):
            return False

    class FakeBucket:
        def blob(self, _name):
            return FakeBlob()

    class FakeQuery:
        def __init__(self, locations):
            self.locations = locations
            self.join_calls = 0
            self.filter_calls = 0
            self.distinct_calls = 0

        def join(self, *_args, **_kwargs):
            self.join_calls += 1
            return self

        def filter(self, *_args, **_kwargs):
            self.filter_calls += 1
            return self

        def distinct(self):
            self.distinct_calls += 1
            return self

        def all(self):
            return self.locations

    class FakeSession:
        def __init__(self, query):
            self._query = query
            self.updated = []
            self.commits = 0

        def query(self, _model):
            return self._query

        def bulk_update_mappings(self, _model, updates):
            self.updated.extend(updates)

        def commit(self):
            self.commits += 1

    location = SimpleNamespace(
        id=1,
        latlon=(35.0, -106.0),
        state="New Mexico",
        county="Bernalillo",
        quad_name="Albuquerque West",
    )
    query = FakeQuery([location])
    session = FakeSession(query)

    monkeypatch.setattr(
        well_transfer_util_module, "get_storage_bucket", lambda: FakeBucket()
    )
    monkeypatch.setattr(
        well_transfer_util_module, "upload_blob_json", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        well_transfer_util_module, "download_blob_json", lambda *_args, **_kwargs: {}
    )

    well_transfer_util_module.cleanup_locations(session, pointids=["sm-0001"])

    assert query.join_calls == 2
    assert query.filter_calls == 1
    assert query.distinct_calls == 1
    assert session.updated == [
        {
            "id": 1,
            "state": "New Mexico",
            "county": "Bernalillo",
            "quad_name": "Albuquerque West",
        }
    ]
