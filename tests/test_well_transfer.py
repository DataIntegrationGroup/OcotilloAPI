from types import SimpleNamespace

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
