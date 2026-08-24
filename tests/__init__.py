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
import os
import socket
from functools import lru_cache

from dotenv import load_dotenv

# Load .env file BEFORE importing anything else
# Use override=False so explicit shell environment variables can override .env
load_dotenv(override=False)


def _normalize_test_db_host() -> None:
    """Fallback docker-compose hostnames to localhost for host-run tests."""
    for env_name in ("POSTGRES_HOST", "PYGEOAPI_POSTGRES_HOST"):
        host = (os.environ.get(env_name) or "").strip()
        if host != "db":
            continue
        try:
            socket.gethostbyname(host)
        except OSError:
            os.environ[env_name] = "localhost"


_normalize_test_db_host()

# for safety don't test on the production database port
os.environ["POSTGRES_PORT"] = "5432"
# Always use test database, never dev
os.environ["POSTGRES_DB"] = "ocotilloapi_test"

from fastapi.testclient import TestClient

from db import Parameter, Base
from db.engine import session_ctx
from main import app

client = TestClient(app)


@lru_cache(maxsize=None)
def get_parameter_id(parameter_name: str, parameter_type: str) -> int:
    with session_ctx() as session:
        param = (
            session.query(Parameter)
            .filter(
                Parameter.parameter_name == parameter_name,
                Parameter.parameter_type == parameter_type,
            )
            .one()
        )
        return param.id


def override_authentication(default=True):
    """
    Override the authentication dependency for testing purposes.
    This allows all users to be considered authenticated.
    """

    def closure():
        # print("Overriding authentication")
        return default

    return closure


def cleanup_post_test(model: Base, new_record_id: int) -> None:
    """
    Function to cleanup POST tests
    """
    with session_ctx() as session:
        session.delete(session.get(model, new_record_id))
        session.commit()


def cleanup_patch_test(model: Base, payload: dict, original_data: Base) -> None:
    """
    Function to cleanup PATCH tests
    """
    with session_ctx() as session:
        updated_record = session.get(model, original_data.id)
        for field in payload.keys():
            original_value = getattr(original_data, field)
            setattr(updated_record, field, original_value)
        session.commit()


# ============= EOF =============================================
