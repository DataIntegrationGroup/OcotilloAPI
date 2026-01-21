# ===============================================================================
# Copyright 2025
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
HTTP integration tests for Minor Trace Chemistry admin view.

These tests make real HTTP requests to verify endpoint behavior.
When these tests pass, the UI should work.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from admin.config import create_admin
from db.nma_legacy import NMAMinorTraceChemistry, ChemistrySampleInfo
from db.thing import Thing
from db.engine import session_ctx


@pytest.fixture(scope="module")
def admin_app():
    """Create a FastAPI app with admin interface mounted."""
    app = FastAPI()

    # Add session middleware required for admin
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key-for-admin")

    # Mount admin interface
    create_admin(app)

    return app


@pytest.fixture(scope="module")
def admin_client(admin_app):
    """Create a test client for the admin app."""
    return TestClient(admin_app)


@pytest.fixture(scope="module")
def minor_trace_chemistry_record():
    """Create a minor trace chemistry record for testing."""
    with session_ctx() as session:
        # First create a Thing (required for ChemistrySampleInfo)
        thing = Thing(
            name="Integration Test Well",
            thing_type="water well",
            release_status="draft",
        )
        session.add(thing)
        session.commit()
        session.refresh(thing)

        # Create parent ChemistrySampleInfo
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid.uuid4(),
            sample_point_id="INTTEST01",
            thing_id=thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        # Create MinorTraceChemistry record
        chemistry = NMAMinorTraceChemistry(
            global_id=uuid.uuid4(),
            chemistry_sample_info_id=sample_info.sample_pt_id,
            analyte="Arsenic",
            symbol="As",
            sample_value=0.005,
            units="mg/L",
            analysis_method="EPA 200.8",
            analyses_agency="NMED",
        )
        session.add(chemistry)
        session.commit()
        session.refresh(chemistry)

        yield chemistry

        # Cleanup
        session.delete(chemistry)
        session.delete(sample_info)
        session.delete(thing)
        session.commit()


class TestMinorTraceChemistryListView:
    """Tests for the list view endpoint."""

    def test_list_view_returns_200(self, admin_client):
        """List view should return 200 OK."""
        response = admin_client.get("/admin/n-m-a-minor-trace-chemistry/list")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            f"Response: {response.text[:500]}"
        )

    def test_list_view_contains_view_name(self, admin_client):
        """List view should contain the view name."""
        response = admin_client.get("/admin/n-m-a-minor-trace-chemistry/list")
        assert response.status_code == 200
        assert "Minor Trace Chemistry" in response.text

    def test_no_create_button_in_list_view(self, admin_client):
        """List view should not have a Create button for read-only view."""
        response = admin_client.get("/admin/n-m-a-minor-trace-chemistry/list")
        assert response.status_code == 200
        html = response.text.lower()
        assert 'href="/admin/n-m-a-minor-trace-chemistry/create"' not in html


class TestMinorTraceChemistryDetailView:
    """Tests for the detail view endpoint."""

    def test_detail_view_returns_200(self, admin_client, minor_trace_chemistry_record):
        """Detail view should return 200 OK for existing record."""
        pk = str(minor_trace_chemistry_record.global_id)
        response = admin_client.get(f"/admin/n-m-a-minor-trace-chemistry/detail/{pk}")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            f"Response: {response.text[:500]}"
        )

    def test_detail_view_shows_analyte(
        self, admin_client, minor_trace_chemistry_record
    ):
        """Detail view should display the analyte."""
        pk = str(minor_trace_chemistry_record.global_id)
        response = admin_client.get(f"/admin/n-m-a-minor-trace-chemistry/detail/{pk}")
        assert response.status_code == 200
        assert "Arsenic" in response.text

    def test_detail_view_shows_parent_relationship(
        self, admin_client, minor_trace_chemistry_record
    ):
        """Detail view should display the parent ChemistrySampleInfo."""
        pk = str(minor_trace_chemistry_record.global_id)
        response = admin_client.get(f"/admin/n-m-a-minor-trace-chemistry/detail/{pk}")
        assert response.status_code == 200
        # The parent relationship should be displayed somehow
        # Check for the field label
        assert "Chemistry Sample Info" in response.text

    def test_detail_view_404_for_nonexistent_record(self, admin_client):
        """Detail view should return 404 for non-existent record."""
        fake_pk = str(uuid.uuid4())
        response = admin_client.get(
            f"/admin/n-m-a-minor-trace-chemistry/detail/{fake_pk}"
        )
        assert response.status_code == 404


class TestMinorTraceChemistryReadOnlyRestrictions:
    """Tests for read-only restrictions."""

    def test_create_endpoint_forbidden(self, admin_client):
        """Create endpoint should be forbidden for read-only view."""
        response = admin_client.get("/admin/n-m-a-minor-trace-chemistry/create")
        # Should be 403 or redirect, not 200
        assert response.status_code in (
            403,
            302,
            307,
        ), f"Expected 403 or redirect, got {response.status_code}"

    def test_edit_endpoint_forbidden(self, admin_client, minor_trace_chemistry_record):
        """Edit endpoint should be forbidden for read-only view."""
        pk = str(minor_trace_chemistry_record.global_id)
        response = admin_client.get(f"/admin/n-m-a-minor-trace-chemistry/edit/{pk}")
        # Should be 403 or redirect, not 200
        assert response.status_code in (
            403,
            302,
            307,
        ), f"Expected 403 or redirect, got {response.status_code}"

    def test_delete_endpoint_forbidden(
        self, admin_client, minor_trace_chemistry_record
    ):
        """Delete endpoint should be forbidden for read-only view."""
        pk = str(minor_trace_chemistry_record.global_id)
        response = admin_client.post(
            f"/admin/n-m-a-minor-trace-chemistry/delete",
            data={"pks": [pk]},
        )
        # Should be 403, redirect, or 404/405 (route may not exist for read-only)
        assert response.status_code in (
            403,
            302,
            307,
            404,
            405,
        ), f"Expected 403/redirect/404/405, got {response.status_code}"


# ============= EOF =============================================
