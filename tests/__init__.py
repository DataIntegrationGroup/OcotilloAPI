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
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from core.app import init_lexicon, init_hypertables
from db.location import Location
from db.base import Base
from db.sample import Sample
from db.sensor import Sensor
from main import app
from db.engine import engine, session_ctx
from services.thing_helper import add_thing

configure_mappers()

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

init_lexicon()

client = TestClient(app)


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
        # loc = Location(point='SRID=4326;POINT(0 0)')
        # session.add(loc)
        # session.commit()
        # session.refresh(loc)

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
            collection_timestamp="2025-01-01T00:00:00Z",
            collection_method="manual",
            thing_id=thing.id,
            sample_type="groundwater",
            sampler="Test Sampler",
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


# ============= EOF =============================================
