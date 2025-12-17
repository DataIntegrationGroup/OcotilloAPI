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
Unit tests for release_status filtering logic.

Tests the data visibility controls without requiring a database.
Uses mocks to verify:
- Public users (unauthenticated) see only public data
- Staff users (authenticated) see all data
- Private/draft data is hidden from public users
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException


class TestOptionalViewerDependency:
    """Test the optional_viewer_function dependency"""

    def test_returns_none_when_authentication_fails(self):
        """Public user - authentication fails, returns None"""
        from core.dependencies import optional_viewer_function

        with patch("core.dependencies.viewer_function") as mock_viewer:
            mock_viewer.side_effect = Exception("Not authenticated")

            result = optional_viewer_function()

            assert result is None

    def test_returns_user_when_authentication_succeeds(self):
        """Staff user - authentication succeeds, returns user dict"""
        from core.dependencies import optional_viewer_function

        with patch("core.dependencies.viewer_function") as mock_viewer:
            expected_user = {"sub": "test-123", "name": "Test User"}
            mock_viewer.return_value = expected_user

            result = optional_viewer_function()

            assert result == expected_user


class TestGetLocationByIdFiltering:
    """Test GET /location/{id} endpoint filtering logic"""

    @patch("api.location.simple_get_by_id")
    def test_public_user_can_access_public_location(self, mock_get_by_id):
        """Public user can access location with release_status='public'"""
        from api.location import get_location_by_id
        import asyncio

        # Mock a public location
        mock_location = Mock()
        mock_location.release_status = "public"
        mock_get_by_id.return_value = mock_location

        mock_session = Mock()

        # Should succeed without exception
        result = asyncio.run(
            get_location_by_id(
                location_id=1, session=mock_session, user=None  # Public user
            )
        )

        assert result == mock_location

    @patch("api.location.simple_get_by_id")
    def test_public_user_cannot_access_private_location(self, mock_get_by_id):
        """Public user gets 404 for location with release_status='private'"""
        from api.location import get_location_by_id
        import asyncio

        # Mock a private location
        mock_location = Mock()
        mock_location.release_status = "private"
        mock_get_by_id.return_value = mock_location

        mock_session = Mock()

        # Should raise HTTPException with 404
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                get_location_by_id(
                    location_id=1, session=mock_session, user=None  # Public user
                )
            )

        assert exc_info.value.status_code == 404
        assert "not publicly accessible" in exc_info.value.detail

    @patch("api.location.simple_get_by_id")
    def test_public_user_cannot_access_draft_location(self, mock_get_by_id):
        """Public user gets 404 for location with release_status='draft'"""
        from api.location import get_location_by_id
        import asyncio

        # Mock a draft location
        mock_location = Mock()
        mock_location.release_status = "draft"
        mock_get_by_id.return_value = mock_location

        mock_session = Mock()

        # Should raise HTTPException with 404
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                get_location_by_id(
                    location_id=1, session=mock_session, user=None  # Public user
                )
            )

        assert exc_info.value.status_code == 404

    @patch("api.location.simple_get_by_id")
    def test_staff_user_can_access_private_location(self, mock_get_by_id):
        """Staff user can access location with any release_status"""
        from api.location import get_location_by_id
        import asyncio

        # Mock a private location
        mock_location = Mock()
        mock_location.release_status = "private"
        mock_get_by_id.return_value = mock_location

        mock_session = Mock()
        staff_user = {"sub": "staff-123", "name": "Staff User"}

        # Should succeed without exception
        result = asyncio.run(
            get_location_by_id(
                location_id=1,
                session=mock_session,
                user=staff_user,  # Authenticated staff
            )
        )

        assert result == mock_location

    @patch("api.location.simple_get_by_id")
    def test_staff_user_can_access_draft_location(self, mock_get_by_id):
        """Staff user can access draft locations"""
        from api.location import get_location_by_id
        import asyncio

        # Mock a draft location
        mock_location = Mock()
        mock_location.release_status = "draft"
        mock_get_by_id.return_value = mock_location

        mock_session = Mock()
        staff_user = {"sub": "staff-123", "name": "Staff User"}

        # Should succeed without exception
        result = asyncio.run(
            get_location_by_id(
                location_id=1,
                session=mock_session,
                user=staff_user,  # Authenticated staff
            )
        )

        assert result == mock_location

    @patch("api.location.simple_get_by_id")
    def test_staff_user_can_access_public_location(self, mock_get_by_id):
        """Staff user can access public locations"""
        from api.location import get_location_by_id
        import asyncio

        # Mock a public location
        mock_location = Mock()
        mock_location.release_status = "public"
        mock_get_by_id.return_value = mock_location

        mock_session = Mock()
        staff_user = {"sub": "staff-123", "name": "Staff User"}

        # Should succeed without exception
        result = asyncio.run(
            get_location_by_id(
                location_id=1,
                session=mock_session,
                user=staff_user,  # Authenticated staff
            )
        )

        assert result == mock_location
