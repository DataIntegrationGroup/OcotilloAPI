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
Tests for admin views module.

These tests ensure admin views can be imported without errors,
catching missing imports and syntax issues early in CI.
"""

import importlib
import pkgutil

import pytest


class TestAdminViewsImport:
    """Tests that verify all admin views can be imported successfully."""

    def test_admin_package_imports(self):
        """
        Admin package should import without errors.

        This catches missing imports like Request, HasOne, etc.
        """
        import admin  # noqa: F401

    def test_admin_views_package_imports(self):
        """Admin views subpackage should import without errors."""
        import admin.views  # noqa: F401

    def test_all_view_modules_import(self):
        """
        All individual admin view modules should import successfully.

        Iterates through all modules in admin.views and verifies each can be imported.
        """
        import admin.views

        failed_imports = []

        for importer, modname, ispkg in pkgutil.iter_modules(admin.views.__path__):
            if modname.startswith("_"):
                continue
            full_name = f"admin.views.{modname}"
            try:
                importlib.import_module(full_name)
            except Exception as e:
                failed_imports.append((full_name, str(e)))

        assert not failed_imports, (
            f"Failed to import admin view modules:\n"
            + "\n".join(f"  {name}: {err}" for name, err in failed_imports)
        )

    @pytest.mark.parametrize(
        "view_module",
        [
            "base",
            "thing",
            "location",
            "observation",
            "sample",
            "contact",
            "chemistry_sampleinfo",
            "major_chemistry",
            "minor_trace_chemistry",
        ],
    )
    def test_core_view_modules_import(self, view_module: str):
        """Core admin view modules should import without errors."""
        importlib.import_module(f"admin.views.{view_module}")


class TestAdminViewsConfiguration:
    """Tests for admin view configuration validity."""

    def test_all_exported_views_have_required_attributes(self):
        """All exported admin views should have required attributes."""
        import admin.views

        for name in admin.views.__all__:
            view_class = getattr(admin.views, name)

            # All views should have a name attribute
            assert hasattr(
                view_class, "name"
            ), f"{view_class.__name__} missing 'name' attribute"

            # All views inheriting from ModelView should have pk_attr
            if hasattr(view_class, "model"):
                assert hasattr(
                    view_class, "pk_attr"
                ), f"{view_class.__name__} missing 'pk_attr' attribute"


# ============= EOF =============================================
