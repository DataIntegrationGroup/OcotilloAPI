import uuid

import pandas as pd
from db import Stratigraphy, Thing
from db.engine import session_ctx
from transfers.stratigraphy_legacy import StratigraphyLegacyTransferer


def _create_test_thing(name: str = "ST-0001") -> Thing:
    with session_ctx() as session:
        thing = Thing(name=name, thing_type="water well", release_status="draft")
        session.add(thing)
        session.commit()
        session.refresh(thing)
        return thing


def test_nma_stratigraphy_model_relationship():
    thing = _create_test_thing("ST-REL-001")
    record_id = uuid.uuid4()
    with session_ctx() as session:
        record = Stratigraphy(
            global_id=record_id,
            well_id=uuid.uuid4(),
            point_id=thing.name,
            thing_id=thing.id,
            strat_top=0.0,
            strat_bottom=10.5,
            unit_identifier="110ALVM",
            object_id=123,
        )
        session.add(record)
        session.commit()

        fetched = session.get(Stratigraphy, record_id)
        assert fetched is not None
        assert fetched.thing_id == thing.id
        assert fetched.thing.name == thing.name
        assert fetched.strat_bottom == 10.5


def test_stratigraphy_transfer_inserts_rows(monkeypatch):
    thing = _create_test_thing("ST-TR-001")

    data = pd.DataFrame(
        [
            {
                "GlobalID": str(uuid.uuid4()),
                "WellID": str(uuid.uuid4()),
                "PointID": thing.name,
                "StratTop": 0,
                "StratBottom": 15.25,
                "UnitIdentifier": "110ALVM",
                "Lithology": "Alluvium",
                "LithologicModifier": "sandy",
                "ContributingUnit": "S",
                "StratSource": "Test source",
                "StratNotes": "Test note",
                "OBJECTID": 999,
            },
            {
                "GlobalID": "not-a-uuid",
                "WellID": None,
                "PointID": thing.name,
                "StratTop": 5,
                "StratBottom": 10,
                "UnitIdentifier": None,
                "Lithology": None,
                "LithologicModifier": None,
                "ContributingUnit": None,
                "StratSource": None,
                "StratNotes": None,
                "OBJECTID": 1000,
            },
        ]
    )

    monkeypatch.setattr(
        "transfers.stratigraphy_legacy.read_csv", lambda _: data.copy(deep=True)
    )
    monkeypatch.setattr("transfers.stratigraphy_legacy.replace_nans", lambda df: df)

    transferer = StratigraphyLegacyTransferer(batch_size=10)
    transferer.transfer()

    with session_ctx() as session:
        rows = session.query(Stratigraphy).filter_by(point_id=thing.name).all()
        assert len(rows) == 1
        record = rows[0]
        assert record.point_id == thing.name
        assert record.thing_id == thing.id
        assert record.strat_bottom == 15.25
        assert record.object_id == 999
