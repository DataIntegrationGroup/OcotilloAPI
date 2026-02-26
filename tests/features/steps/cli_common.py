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
from behave import given, then
from starlette.testclient import TestClient

from core.dependencies import (
    viewer_function,
    amp_viewer_function,
    amp_editor_function,
    admin_function,
    amp_admin_function,
)


@given("a functioning cli")
def step_given_cli_is_running(context):
    """
    Initializes app/auth context needed by CLI-backed feature tests
    that still perform DB-backed assertions.
    """
    from main import app

    def override_authentication(default=True):
        def closure():
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

    # Kept for compatibility with existing steps that may use context.client.
    context.client = TestClient(app)


@then("the command exits with code 0")
def step_impl_command_exit_zero(context):
    assert context.cli_result.exit_code == 0, context.cli_result.stderr


@then("the command exits with a non-zero exit code")
def step_impl_command_exit_nonzero(context):
    assert context.cli_result.exit_code != 0


# ============= EOF =============================================
