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

# init_hypertables()
init_lexicon()

client = TestClient(app)

"""
REFACTOR TODO: put all fixtures here or in a separate fixtures file. Some fixtures are dependent on others,
such as `sample_fixture` which requires `thing`. By putting them all in one place, we can ensure that
they are properly managed and avoid potential issues with fixture scope and lifecycle.
"""


@pytest.fixture(scope="function")
def thing():
    with session_ctx() as session:
        thing = Thing()
        thing.name = "Test Thing"
        thing.thing_type = "water well"
        session.add(thing)
        session.commit()
        session.refresh(thing)
        yield thing
        session.delete(thing)
        session.close()


# ============= EOF =============================================
