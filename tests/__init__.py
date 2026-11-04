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


def setup_test_environment() -> None:
    """
    Setup the test environment by configuring environment variables and loading the .env file.
    POSTGRES_DB, PYGEOAPI_POSTGRES_DB, POSTGRES_PORT and DB_DRIVER are forced
    and win over .env; host, user and password come from the shell or .env.

    There are multiple testing regimens, such as pytest and BDD step tests, both
    of which require the test environment to be properly configured before running tests.
    They often rely on the same environment variables and database setup to function correctly,
    so they are both configured using this setup function

     ---
    pytest
    ---
    pytest imports tests/conftest.py and the test modules as submodules of the
    `tests` package (default `prepend` import mode), so Python runs this file
    `first -- before any `db` or `main` import in them (which require environment
    variables to be correctly set). That is why this function is called at module
    level below, ahead of this file's own app imports. It does not run for suites
    outside tests/ (e.g. automated_ingestion/tests).

    ---
    BDD step tests
    ---
    behave does not treat tests/ as a package, so tests/features/environment.py
    imports `tests` explicitly, above its `db` imports, to trigger the same call.
    No BDD-specific setup is needed beyond this.
    """
    os.environ["POSTGRES_DB"] = "ocotilloapi_test"
    os.environ["PYGEOAPI_POSTGRES_DB"] = "ocotilloapi_test"
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
