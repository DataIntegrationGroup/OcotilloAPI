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
from fastapi_pagination import add_pagination
from starlette.middleware.cors import CORSMiddleware

from core.initializers import (
    register_routes,
    erase_and_rebuild_db,
)
from db import Base, Parameter
from db.engine import session_ctx
from core.app import app

erase_and_rebuild_db()
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


def retrieve_latest_polymorphic_table_record(
    target_record: Base,
    polymorphic_relationship: str,
    polymorphic_type: str,
) -> Base:
    """
    Retrieve the latest record from a polymorphic table. This function assumes that the
    parent class has the correct mixin to support retrieval via an attribute. This
    requires end_date to be None

    Parameters:
    ----------
    target_record : Base
        The parent record from which to retrieve the polymorphic child record.
    polymorphic_relationship : str
        The name of the relationship attribute on the parent record that corresponds to the polymorphic table.
    polymorphic_type : str
        The specific type of the polymorphic record to retrieve (e.g., 'Use Status' or 'Monitoring Status' for StatusHistory).
    latest : bool, optional
        If True, retrieves the latest record based on start_date. Defaults to True.
    """
    if polymorphic_relationship == "permissions":
        type_field = "permission_type"
    elif polymorphic_relationship == "status_history":
        type_field = "status_type"

    polymorphic_records = getattr(target_record, polymorphic_relationship)
    type_polymorphic_records = [
        r
        for r in polymorphic_records
        if getattr(r, type_field) == polymorphic_type and r.end_date is None
    ]
    sorted_type_polymorphic_records = sorted(
        type_polymorphic_records, key=lambda r: r.start_date, reverse=True
    )
    return sorted_type_polymorphic_records[0]


# ============= EOF =============================================
