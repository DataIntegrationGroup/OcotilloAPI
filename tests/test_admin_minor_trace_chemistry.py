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
Unit tests for Minor Trace Chemistry admin view configuration.

These tests verify the admin view is properly configured without requiring
a running server or database.
"""

import pytest
from fastapi import FastAPI

from admin.config import create_admin
from admin.views.minor_trace_chemistry import MinorTraceChemistryAdmin
from db.nma_legacy import NMA_MinorTraceChemistry


class TestMinorTraceChemistryAdminRegistration:
    """Tests for MinorTraceChemistry admin view registration."""

    def test_minor_trace_chemistry_view_is_registered(self):
        """Minor Trace Chemistry should appear in admin views."""
        app = FastAPI()
        admin = create_admin(app)
        view_names = [v.name for v in admin._views]

        assert "NMA Minor Trace Chemistry" in view_names, (
            f"Expected 'NMA Minor Trace Chemistry' to be registered in admin views. "
            f"Found: {view_names}"
        )

    def test_view_has_correct_label(self):
        """View should have proper label for sidebar display."""
        view = MinorTraceChemistryAdmin(NMA_MinorTraceChemistry)
        assert view.label == "NMA Minor Trace Chemistry"

    def test_class_has_flask_icon_configured(self):
        """View class should have flask icon configured for chemistry data."""
        # Note: icon attribute may be processed by starlette-admin on instantiation
        # so we check the class attribute directly
        assert MinorTraceChemistryAdmin.icon == "fa fa-flask"


class TestMinorTraceChemistryAdminReadOnly:
    """Tests for read-only restrictions on legacy data."""

    @pytest.fixture
    def view(self):
        """Create a MinorTraceChemistryAdmin instance for testing."""
        return MinorTraceChemistryAdmin(NMA_MinorTraceChemistry)

    def test_can_create_returns_false(self, view):
        """Create should be disabled for legacy data."""
        assert view.can_create(None) is False

    def test_can_edit_returns_false(self, view):
        """Edit should be disabled for legacy data."""
        assert view.can_edit(None) is False

    def test_can_delete_returns_false(self, view):
        """Delete should be disabled for legacy data."""
        assert view.can_delete(None) is False

    def test_read_only_methods_are_callable(self, view):
        """Permission methods should be callable (not boolean attributes)."""
        # This test catches the bug where can_create/can_edit/can_delete
        # were set as boolean attributes instead of methods
        assert callable(view.can_create)
        assert callable(view.can_edit)
        assert callable(view.can_delete)


class TestMinorTraceChemistryAdminListView:
    """Tests for list view configuration."""

    @pytest.fixture
    def view(self):
        """Create a MinorTraceChemistryAdmin instance for testing."""
        return MinorTraceChemistryAdmin(NMA_MinorTraceChemistry)

    def test_list_fields_include_required_columns(self, view):
        """List view should show key chemistry data columns."""
        from starlette_admin.fields import HasOne

        # Get field names (handling both string fields and HasOne fields)
        field_names = []
        for f in view.list_fields:
            if isinstance(f, str):
                field_names.append(f)
            elif isinstance(f, HasOne):
                field_names.append(f.name)
            else:
                field_names.append(getattr(f, "name", str(f)))

        required_columns = [
            "global_id",
            "chemistry_sample_info",  # HasOne relationship to parent
            "sample_pt_id",
            "sample_point_id",
            "analyte",
            "sample_value",
            "units",
        ]
        for col in required_columns:
            assert col in field_names, f"Expected '{col}' in list_fields"

    def test_default_sort_by_analysis_date(self, view):
        """Default sort should be by analysis_date descending."""
        assert view.fields_default_sort == [("analysis_date", True)]

    def test_page_size_is_50(self, view):
        """Default page size should be 50."""
        assert view.page_size == 50

    def test_page_size_options_available(self, view):
        """Multiple page size options should be available."""
        assert 25 in view.page_size_options
        assert 50 in view.page_size_options
        assert 100 in view.page_size_options


class TestMinorTraceChemistryAdminFormView:
    """Tests for form/detail view configuration."""

    @pytest.fixture
    def view(self):
        """Create a MinorTraceChemistryAdmin instance for testing."""
        return MinorTraceChemistryAdmin(NMA_MinorTraceChemistry)

    def test_form_includes_all_chemistry_fields(self):
        """Form should include all relevant chemistry data fields in configuration."""
        from starlette_admin.fields import HasOne

        # Check the class-level configuration
        # Note: chemistry_sample_info is a HasOne field, not a string
        expected_string_fields = [
            "global_id",
            "sample_pt_id",
            "sample_point_id",
            "analyte",
            "symbol",
            "sample_value",
            "units",
            "uncertainty",
            "analysis_method",
            "analysis_date",
            "notes",
            "volume",
            "volume_unit",
            "object_id",
            "analyses_agency",
            "wclab_id",
        ]
        configured_fields = MinorTraceChemistryAdmin.fields

        # Check string fields
        for field in expected_string_fields:
            assert (
                field in configured_fields
            ), f"Expected '{field}' in configured fields"

        # Check that chemistry_sample_info HasOne relationship is configured
        has_one_fields = [f for f in configured_fields if isinstance(f, HasOne)]
        assert (
            len(has_one_fields) == 1
        ), "Expected one HasOne field for parent relationship"
        assert has_one_fields[0].name == "chemistry_sample_info"

    def test_field_labels_are_human_readable(self, view):
        """Field labels should be human-readable."""
        assert view.field_labels.get("global_id") == "GlobalID"
        assert view.field_labels.get("sample_value") == "SampleValue"
        assert view.field_labels.get("analysis_date") == "AnalysisDate"

    def test_searchable_fields_include_key_fields(self, view):
        """Searchable fields should include commonly searched columns."""
        assert "analyte" in view.searchable_fields
        assert "symbol" in view.searchable_fields
        assert "analyses_agency" in view.searchable_fields


# ============= EOF =============================================
