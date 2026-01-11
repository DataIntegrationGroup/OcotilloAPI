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
# Load .env file BEFORE importing anything else
# Use override=True to override conflicting shell environment variables
import os

from dotenv import load_dotenv

load_dotenv(override=True)

# for safety dont test on the production database port
os.environ["POSTGRES_PORT"] = "54321"

# this should not be needed since all Pydantic serializes all datetimes as UTC
# furthermore, tzset is not supported on Windows, so this breaks cross-platform compatibility
# # Set timezone to UTC for consistent datetime handling in tests
# os.environ["TZ"] = "UTC"

# # Also set time.tzset() to apply the timezone change
# import time

# time.tzset()

from fastapi.testclient import TestClient
from fastapi_pagination import add_pagination
from starlette.middleware.cors import CORSMiddleware

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy_utils import TSVectorType
from sqlalchemy_searchable import sync_trigger

from core.initializers import register_routes, init_lexicon, init_parameter
from db import Base, Parameter
from db.engine import session_ctx
from core.app import app


def _alembic_config() -> Config:
    root = os.path.dirname(os.path.dirname(__file__))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "alembic"))
    return cfg


def _reset_schema() -> None:
    with session_ctx() as session:
        session.execute(text("DROP SCHEMA public CASCADE"))
        session.execute(text("CREATE SCHEMA public"))
        session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        session.commit()


def _sync_search_vectors() -> None:
    with session_ctx() as session:
        conn = session.connection()
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, TSVectorType):
                    sync_trigger(
                        conn,
                        table.name,
                        column.name,
                        list(column.type.columns),
                    )
        session.commit()


_reset_schema()
command.upgrade(_alembic_config(), "head")
_sync_search_vectors()
init_lexicon()
init_parameter()
register_routes(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust as needed for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)

client = TestClient(app)

# map (name, type) to id for easy lookup in tests
parameter_map = {}
with session_ctx() as session:
    for param in session.query(Parameter).all():
        if (
            param.parameter_name in ["groundwater level", "pH"]
            and param.parameter_type == "Field Parameter"
        ):
            parameter_map[(param.parameter_name, param.parameter_type)] = param.id

groundwater_level_parameter_id = parameter_map[("groundwater level", "Field Parameter")]
pH_parameter_id = parameter_map[("pH", "Field Parameter")]


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
