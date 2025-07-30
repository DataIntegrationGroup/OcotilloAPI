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
from main import app
from db import *
from db.engine import engine, session_ctx
from services.thing_helper import add_thing

configure_mappers()

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

# init_hypertables()
init_lexicon()

client = TestClient(app)

@pytest.fixture(scope="module")
def sample():
    with session_ctx() as session:
        loc = Location(point="SRID=4326;POINT(0 0)")
        session.add(loc)
        session.commit()

        thing = add_thing(
            session,
            {
                "location_id": loc.id,
                "name": f"Test Well {loc.id}",
            },
            "water well",
        )

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


@pytest.fixture(scope="module")
def thing():
    with session_ctx() as session:
        loc = Location(point="SRID=4326;POINT(0 0)")
        session.add(loc)
        session.commit()

        wt = add_thing(
            session,
            {
                "location_id": loc.id,
                "name": "Test Well",
            },
            "water well",
        )

        yield wt

        session.close()


@pytest.fixture(scope="module")
def sensor():
    with session_ctx() as session:
        sensor = Sensor(name=f"Test Sensor {uuid.uuid4()}")
        session.add(sensor)
        session.commit()
        yield sensor

        session.close()


# ============= EOF =============================================
