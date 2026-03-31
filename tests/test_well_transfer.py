import threading
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from schemas.thing import CreateWell
from transfers import well_transfer as wt


class _FakeSession:
    def __init__(self):
        self.added = []
        self.expunge_calls = []

    def add(self, obj):
        self.added.append(obj)

    def expunge(self, obj):
        self.expunge_calls.append(obj)


class _FakeQuery:
    def __init__(self, session):
        self.session = session

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.session.query_results.pop(0)


class _FakeSavepoint:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeAquiferSession:
    def __init__(self, query_results, flush_exc=None):
        self.added = []
        self.begin_nested_calls = 0
        self.rollback_calls = 0
        self.query_results = list(query_results)
        self.flush_exc = flush_exc

    def add(self, obj):
        self.added.append(obj)

    def begin_nested(self):
        self.begin_nested_calls += 1
        return _FakeSavepoint()

    def flush(self):
        if self.flush_exc is not None:
            exc = self.flush_exc
            self.flush_exc = None
            raise exc

    def query(self, _model):
        return _FakeQuery(self)

    def rollback(self):
        self.rollback_calls += 1


def test_persist_well_excludes_monitoring_status_from_thing_kwargs(
    monkeypatch,
):
    captured_kwargs = {}

    class FakeThing:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(wt, "Thing", FakeThing)

    transferer = wt.WellTransferer()
    session = _FakeSession()
    row = SimpleNamespace(PointID="AR0001", WellID=12, LocationId=34)
    payload = {
        "data": CreateWell(
            name="AR0001",
            monitoring_status="Not currently monitored",
        ),
        "well_purposes": [],
        "well_casing_materials": [],
    }
    batch_errors = []

    well = transferer._persist_well(session, row, payload, batch_errors)

    assert well is session.added[0]
    assert "monitoring_status" not in captured_kwargs
    assert captured_kwargs["thing_type"] == "water well"
    assert captured_kwargs["nma_pk_welldata"] == 12
    assert captured_kwargs["nma_pk_location"] == 34
    assert batch_errors == []
    assert session.expunge_calls == []


def test_add_aquifers_parallel_recovers_from_integrity_error(monkeypatch):
    class FakeAquiferSystem:
        name = "name"

        def __init__(self, name, primary_aquifer_type, geographic_scale):
            self.name = name
            self.primary_aquifer_type = primary_aquifer_type
            self.geographic_scale = geographic_scale

    class FakeThingAquiferAssociation:
        def __init__(self, thing, aquifer_system):
            self.thing = thing
            self.aquifer_system = aquifer_system

    class FakeAquiferType:
        def __init__(self, thing_aquifer_association, aquifer_type):
            self.thing_aquifer_association = thing_aquifer_association
            self.aquifer_type = aquifer_type

    def fake_map_value(value):
        if value.startswith("LU_AquiferClass:"):
            return "Test Aquifer"
        if value.startswith("LU_AquiferType:"):
            return "Confined"
        raise KeyError(value)

    existing_aquifer = SimpleNamespace(name="Test Aquifer")
    session = _FakeAquiferSession(
        query_results=[None, existing_aquifer],
        flush_exc=IntegrityError("insert", {}, Exception("duplicate key")),
    )
    transferer = wt.WellTransferer()
    row = SimpleNamespace(PointID="AR0001", AqClass="AQ", AquiferType="A")
    well = SimpleNamespace(name="AR0001")
    local_aquifers = []

    monkeypatch.setattr(wt, "AquiferSystem", FakeAquiferSystem)
    monkeypatch.setattr(wt, "ThingAquiferAssociation", FakeThingAquiferAssociation)
    monkeypatch.setattr(wt, "AquiferType", FakeAquiferType)
    monkeypatch.setattr(wt, "extract_aquifer_type_codes", lambda _value: ["A"])
    monkeypatch.setattr(wt.lexicon_mapper, "map_value", fake_map_value)

    transferer._add_aquifers_parallel(
        session, row, well, local_aquifers, threading.Lock()
    )

    associations = [
        obj for obj in session.added if isinstance(obj, FakeThingAquiferAssociation)
    ]

    assert session.begin_nested_calls == 1
    assert session.rollback_calls == 0
    assert associations[0].aquifer_system is existing_aquifer
    assert local_aquifers == [existing_aquifer]


def test_add_aquifers_parallel_reraises_unexpected_flush_errors(monkeypatch):
    class FakeAquiferSystem:
        name = "name"

        def __init__(self, name, primary_aquifer_type, geographic_scale):
            self.name = name
            self.primary_aquifer_type = primary_aquifer_type
            self.geographic_scale = geographic_scale

    def fake_map_value(value):
        if value.startswith("LU_AquiferClass:"):
            return "Test Aquifer"
        if value.startswith("LU_AquiferType:"):
            return "Confined"
        raise KeyError(value)

    session = _FakeAquiferSession(
        query_results=[None],
        flush_exc=RuntimeError("database unavailable"),
    )
    transferer = wt.WellTransferer()
    row = SimpleNamespace(PointID="AR0001", AqClass="AQ", AquiferType="A")
    well = SimpleNamespace(name="AR0001")

    monkeypatch.setattr(wt, "AquiferSystem", FakeAquiferSystem)
    monkeypatch.setattr(wt, "extract_aquifer_type_codes", lambda _value: ["A"])
    monkeypatch.setattr(wt.lexicon_mapper, "map_value", fake_map_value)

    with pytest.raises(RuntimeError, match="database unavailable"):
        transferer._add_aquifers_parallel(session, row, well, [], threading.Lock())

    assert session.begin_nested_calls == 1
    assert session.rollback_calls == 0
