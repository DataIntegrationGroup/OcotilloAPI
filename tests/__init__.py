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
from dotenv import load_dotenv

load_dotenv(override=True)

# this should not be needed since all Pydantic serializes all datetimes as UTC
# furthermore, tzset is not supported on Windows, so this breaks cross-platform compatibility
# # Set timezone to UTC for consistent datetime handling in tests
# os.environ["TZ"] = "UTC"

# # Also set time.tzset() to apply the timezone change
# import time

# time.tzset()

from fastapi.testclient import TestClient

from core.initializers import init_lexicon, init_parameter, erase_and_rebuild_db
from db import Base, Parameter
from db.engine import session_ctx
from main import app

with session_ctx() as session:
    erase_and_rebuild_db(session)

init_lexicon()
init_parameter()

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
