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


def setup_test_environment(env_overrides: dict = {}) -> None:
    """
    Setup the test environment by configuring environment variables and loading the .env file.

    There are multiple testing regimens, such as pytest and BDD step tests, both
    of which require the test environment to be properly configured before running tests.
    They often rely on the same environment variables and database setup to function correctly,
    so they are both configured using this setup function

    Variables in env_overrides are applied last and take precedence over
    the .env file and any values already set in the environment.

    ---
    pytest
    ---
    pytest runs tests/__init__.py on startup so this function is called immediately below
    where it is invoked.

    ---
    BDD step tests
    ---
    BDD step tests require some further configuration specific to the BDD framework,
    which is handled by the BDD test setup code in tests/features/environment.py where
    this function is invoked.
    """
    os.environ["POSTGRES_DB"] = "ocotilloapi_test"
    os.environ["POSTGRES_PORT"] = "5432"

    # any value except for "cloudsql" will make it connect to a local Postgres instance
    os.environ["DB_DRIVER"] = "postgres"

    load_dotenv(override=False)

    for env_name in ("POSTGRES_HOST", "PYGEOAPI_POSTGRES_HOST"):
        host = (os.environ.get(env_name) or "").strip()
        if host != "db":
            continue
        try:
            socket.gethostbyname(host)
        except OSError:
            os.environ[env_name] = "localhost"

    for env_name, env_value in env_overrides.items():
        os.environ[env_name] = env_value


# invoke the test environment setup before importing the database and app modules so that
# the environment variables are correctly set and the database engine is configured properly.
setup_test_environment()

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
