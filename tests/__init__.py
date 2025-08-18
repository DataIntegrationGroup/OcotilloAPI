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
from fastapi.testclient import TestClient

from core.app import init_lexicon
from db import Base
from db.engine import engine, session_ctx
from main import app


Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

init_lexicon()

client = TestClient(app)


def override_authentication(default=True):
    """
    Override the authentication dependency for testing purposes.
    This allows all users to be considered authenticated.
    """

    def closure():
        print("Overriding authentication")
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
