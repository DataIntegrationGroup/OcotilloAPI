import pytest
import uuid

from db import *
from db.engine import session_ctx
from services.thing_helper import add_thing


@pytest.fixture(scope="session")
def location():
    with session_ctx() as session:
        loc = Location(point="SRID=4326;POINT(0 0)")
        session.add(loc)
        session.commit()
        session.refresh(loc)
        yield loc

        session.close()


@pytest.fixture(scope="session")
def thing(location):
    with session_ctx() as session:
        wt = add_thing(
            session,
            {
                "location_id": location.id,
                "name": "Test Well",
            },
            "water well",
        )

        yield wt

        session.close()


@pytest.fixture(scope="session")
def sample(thing):
    with session_ctx() as session:
        sample = Sample(
            sample_date="2025-01-01T00:00:00",
            sample_method="manual",
            thing_id=thing.id,
            sample_type="groundwater",
            sampler_name="Test Sampler",
            release_status="draft",
            field_sample_id=f"FS-{uuid.uuid4()}",
        )
        session.add(sample)
        session.commit()
        yield sample

        session.close()


@pytest.fixture(scope="session")
def sensor():
    with session_ctx() as session:
        sensor = Sensor(name=f"Test Sensor {uuid.uuid4()}")
        session.add(sensor)
        session.commit()
        yield sensor
        session.close()
