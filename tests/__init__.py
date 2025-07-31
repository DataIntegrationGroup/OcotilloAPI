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
from alembic.config import Config
from alembic import command
import uuid

import pytest
from fastapi.testclient import TestClient

from core.app import init_lexicon
from main import app
from db import *
from db.engine import session_ctx


def run_alembic_upgrade():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


def run_alembic_downgrade():
    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, "base")


run_alembic_downgrade()
run_alembic_upgrade()

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
        session.refresh(thing)
        yield thing
        session.delete(thing)
        session.close()


@pytest.fixture
def sample_fixture(thing):
    with session_ctx() as session:
        sample = Sample(
            thing_id=thing.id,
            collection_timestamp="2025-01-01T00:00:00+00:00",
            collection_method="manual",
        )
        session.add(sample)
        session.commit()
        session.refresh(sample)
        yield thing, sample
        session.delete(sample)
        session.commit()


# ============= EOF =============================================
