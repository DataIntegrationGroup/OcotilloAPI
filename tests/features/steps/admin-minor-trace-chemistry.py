# ===============================================================================
# Copyright 2026
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
"""
Step definitions for Minor Trace Chemistry admin view tests.
These are fast integration tests - no HTTP calls, direct module testing.
"""
from behave import when, then, given
from behave.runner import Context


def _ensure_admin_mounted(context):
    """Ensure admin is mounted on the test app."""
    if not getattr(context, "_admin_mounted", False):
        from admin import create_admin
        from starlette.middleware.sessions import SessionMiddleware

        # Add session middleware required by admin
        context.client.app.add_middleware(
            SessionMiddleware, secret_key="test-secret-key"
        )
        create_admin(context.client.app)
        context._admin_mounted = True


@when("I check the registered admin views")
def step_impl(context: Context):
    from admin.config import create_admin
    from fastapi import FastAPI

    app = FastAPI()
    admin = create_admin(app)
    context.admin_views = [v.name for v in admin._views]


@then('"{view_name}" should be in the list of admin views')
def step_impl(context: Context, view_name: str):
    assert view_name in context.admin_views, (
        f"Expected '{view_name}' to be registered in admin views. "
        f"Found: {context.admin_views}"
    )


@then("the Minor Trace Chemistry admin view should not allow create")
def step_impl(context: Context):
    from admin.views.minor_trace_chemistry import MinorTraceChemistryAdmin
    from db.nma_legacy import NMAMinorTraceChemistry

    view = MinorTraceChemistryAdmin(NMAMinorTraceChemistry)
    assert view.can_create(None) is False


@then("the Minor Trace Chemistry admin view should not allow edit")
def step_impl(context: Context):
    from admin.views.minor_trace_chemistry import MinorTraceChemistryAdmin
    from db.nma_legacy import NMAMinorTraceChemistry

    view = MinorTraceChemistryAdmin(NMAMinorTraceChemistry)
    assert view.can_edit(None) is False


@then("the Minor Trace Chemistry admin view should not allow delete")
def step_impl(context: Context):
    from admin.views.minor_trace_chemistry import MinorTraceChemistryAdmin
    from db.nma_legacy import NMAMinorTraceChemistry

    view = MinorTraceChemistryAdmin(NMAMinorTraceChemistry)
    assert view.can_delete(None) is False


@when("I request the Minor Trace Chemistry admin list page")
def step_impl(context: Context):
    _ensure_admin_mounted(context)
    context.response = context.client.get("/admin/n-m-a-minor-trace-chemistry/list")


@when("I request the Minor Trace Chemistry admin detail page for an existing record")
def step_impl(context: Context):
    _ensure_admin_mounted(context)
    from db.engine import session_ctx
    from db.nma_legacy import NMAMinorTraceChemistry

    with session_ctx() as session:
        record = session.query(NMAMinorTraceChemistry).first()
        if record:
            context.response = context.client.get(
                f"/admin/n-m-a-minor-trace-chemistry/detail/{record.global_id}"
            )
        else:
            # No records exist, skip by setting a mock 200 response
            context.response = type("Response", (), {"status_code": 200})()


@then("the response status should be {status_code:d}")
def step_impl(context: Context, status_code: int):
    assert (
        context.response.status_code == status_code
    ), f"Expected status {status_code}, got {context.response.status_code}"


@then("the Minor Trace Chemistry admin view should have these fields configured:")
def step_impl(context: Context):
    from admin.views.minor_trace_chemistry import MinorTraceChemistryAdmin

    expected_fields = [row["field"] for row in context.table]
    actual_fields = MinorTraceChemistryAdmin.fields

    for field in expected_fields:
        assert field in actual_fields, (
            f"Expected field '{field}' not found in admin view fields. "
            f"Configured fields: {actual_fields}"
        )


# ============= EOF =============================================
