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
Admin authentication provider integrating with existing Authentik OIDC auth.

This module provides a Starlette Admin AuthProvider that integrates with the
existing Authentik-based authentication system used by the NMSampleLocations API.
"""
import os
from typing import Optional

from dataclasses import dataclass
from typing import List

from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed

from core.permissions import _get_token_payload, verify_token


@dataclass
class AdminUserWithRoles(AdminUser):
    """Extended AdminUser with roles for RBAC."""

    roles: List[str] = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = []


class NMSampleLocationsAuthProvider(AuthProvider):
    """
    Custom auth provider that integrates with existing Authentik OIDC authentication.

    Reuses the existing authentication infrastructure from core.permissions module.

    For MS Access users: This replaces Access file-level security with user-level
    authentication. Each user logs in with their Authentik credentials and gets
    assigned roles (Admin, Editor, Viewer) which control what they can do in the
    admin interface.
    """

    async def is_authenticated(self, request: Request) -> bool:
        """
        Check if user is authenticated by verifying their JWT token.

        This method is called on every admin page request to determine if the
        user should be allowed access.

        Returns:
            bool: True if user has a valid JWT token, False otherwise
        """
        # Check if authentication is disabled (development mode only)
        if int(os.environ.get("AUTHENTIK_DISABLE_AUTHENTICATION", 0)):
            from core.settings import settings

            if settings.mode != "production":
                # Allow unauthenticated access in development mode
                request.state.user = AdminUserWithRoles(
                    username="dev_user", roles=["admin"]
                )
                return True

        try:
            # Try to get token from Authorization header
            authorization = request.headers.get("Authorization")
            if not authorization:
                # Try to get token from session/cookie
                token = request.session.get("token")
                if not token:
                    return False
            else:
                # Extract token from "Bearer <token>" format
                token = (
                    authorization.split(" ")[1]
                    if " " in authorization
                    else authorization
                )

            # Verify token using existing authentication system
            is_valid = verify_token(token, scope=None, permissions=None)

            if is_valid:
                # Store user in request state for later access
                request.state.user = self._create_admin_user_from_token(token)

            return is_valid
        except Exception:
            return False

    def _create_admin_user_from_token(self, token: str) -> Optional[AdminUser]:
        """
        Extract user information from JWT token and create AdminUser instance.

        Args:
            token: JWT access token from Authentik

        Returns:
            AdminUser instance with username and roles, or None if token invalid
        """
        try:
            # Decode JWT payload
            payload = _get_token_payload(token)

            # Extract user information from JWT claims
            username = (
                payload.get("preferred_username")
                or payload.get("email")
                or payload.get("sub")
            )
            email = payload.get("email")
            groups = payload.get("groups", [])

            # Map Authentik groups to admin roles
            roles = []

            # Standard roles
            if "Admin" in groups:
                roles.append("admin")
            if "Editor" in groups:
                roles.append("editor")
            if "Viewer" in groups:
                roles.append("viewer")

            # AMP-specific roles (for AMPAPI-related data)
            if "AMPAdmin" in groups:
                roles.append("amp_admin")
            if "AMPEditor" in groups:
                roles.append("amp_editor")
            if "AMPViewer" in groups:
                roles.append("amp_viewer")

            # Lexicon-specific roles
            if "LexiconAdmin" in groups:
                roles.append("lexicon_admin")
            if "LexiconEditor" in groups:
                roles.append("lexicon_editor")

            return AdminUserWithRoles(
                username=username,
                photo_url=None,  # Could add user avatar URL from OIDC if available
                roles=roles,
            )
        except Exception:
            return None

    def get_admin_user(self, request: Request) -> Optional[AdminUser]:
        """
        Get the current admin user from the request.

        This method is called by Starlette Admin to get user information for
        display in the UI and permission checks.

        Returns:
            AdminUser instance with username and roles, or None if not authenticated
        """
        # Check if user is already stored in request state
        if hasattr(request.state, "user"):
            return request.state.user

        try:
            # Get token from request
            authorization = request.headers.get("Authorization")
            if not authorization:
                token = request.session.get("token")
                if not token:
                    return None
            else:
                token = (
                    authorization.split(" ")[1]
                    if " " in authorization
                    else authorization
                )

            # Create AdminUser from token
            admin_user = self._create_admin_user_from_token(token)

            # Store in request state for future calls
            if admin_user:
                request.state.user = admin_user

            return admin_user
        except Exception:
            return None

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
    ) -> RedirectResponse:
        """
        Redirect to Authentik OIDC login page.

        Note: Starlette Admin will show a login form, but we ignore the username/password
        and redirect to Authentik OAuth flow instead.

        Args:
            username: Ignored (OIDC handles authentication)
            password: Ignored (OIDC handles authentication)
            remember_me: Ignored
            request: Starlette request object

        Returns:
            RedirectResponse to Authentik authorization endpoint
        """
        # Redirect to Authentik OAuth authorization endpoint
        authentik_authorize_url = os.environ.get("AUTHENTIK_AUTHORIZE_URL")
        if not authentik_authorize_url:
            raise LoginFailed(
                "Authentik authentication is not configured. Please set AUTHENTIK_AUTHORIZE_URL environment variable."
            )

        # Store original URL to redirect back after login
        original_url = str(request.url_for("admin:index"))
        request.session["auth_redirect"] = original_url

        # Redirect to Authentik login
        return RedirectResponse(url=authentik_authorize_url, status_code=302)

    async def logout(self, request: Request) -> RedirectResponse:
        """
        Handle logout by clearing session and redirecting.

        Args:
            request: Starlette request object

        Returns:
            RedirectResponse to home page
        """
        # Clear session tokens
        request.session.pop("token", None)
        request.session.pop("auth_redirect", None)

        # Clear user from request state
        if hasattr(request.state, "user"):
            delattr(request.state, "user")

        # Redirect to home page
        # TODO: Consider redirecting to Authentik logout endpoint to fully log out
        return RedirectResponse(url="/", status_code=302)
