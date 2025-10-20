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
from behave import given, when, then
from fastapi.testclient import TestClient
from fastapi_pagination import add_pagination
from starlette.middleware.cors import CORSMiddleware

from core.app import app
from core.dependencies import (
    amp_admin_function,
    admin_function,
    amp_editor_function,
    amp_viewer_function,
    viewer_function,
)
from core.initializers import init_lexicon, init_parameter, register_routes
from db import Base
from db.engine import engine


@given("the testing API is running")
def step_given_api_is_running(context):
    """
    Ensures the API app is initialized and client is ready.
    Behave will keep 'context' across steps, allowing us to reuse response data.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

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

    def override_authentication(default=True):
        """
        Override the authentication dependency for testing purposes.
        This allows all users to be considered authenticated.
        """

        def closure():
            # print("Overriding authentication")
            return default

        return closure

    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()
    app.dependency_overrides[viewer_function] = override_authentication()

    client = TestClient(app)
    context.client = client
    assert context.client is not None, "TestClient failed to initialize"


@when("I call the testing API group endpoint")
def step_impl(context):
    context.response = context.client.get("/group")


@then("I should receive a successful response")
def step_impl(context):
    assert (
        context.response.status_code == 200
    ), f"Unexpected response: {context.response.text}"


# ============= EOF =============================================
