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

from fastapi.testclient import TestClient

from core.app import init_lexicon
from main import app


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


# ============= EOF =============================================
