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
Admin authentication callback routes.
"""

import os

import httpx
from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse
from starlette_admin.exceptions import LoginFailed

router = APIRouter()


@router.get("/admin/auth/callback", name="admin_auth_callback", include_in_schema=False)
async def admin_auth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    expected_state = request.session.get("auth_state")

    if not code or not state or state != expected_state:
        raise LoginFailed("Invalid authentication response.")

    token_url = os.environ.get("AUTHENTIK_TOKEN_URL")
    client_id = os.environ.get("AUTHENTIK_CLIENT_ID")
    if not token_url or not client_id:
        raise LoginFailed(
            "Authentik authentication is not configured. Please set AUTHENTIK_TOKEN_URL and AUTHENTIK_CLIENT_ID."
        )

    redirect_uri = str(request.url_for("admin_auth_callback"))
    code_verifier = request.session.get("auth_code_verifier")

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    if code_verifier:
        data["code_verifier"] = code_verifier

    client_secret = os.environ.get("AUTHENTIK_CLIENT_SECRET")
    if client_secret:
        data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=data)
        if resp.status_code >= 400:
            raise LoginFailed("Failed to exchange token from Authentik.")
        token_payload = resp.json()

    access_token = token_payload.get("access_token")
    if not access_token:
        raise LoginFailed("Authentik did not return an access token.")

    request.session["token"] = access_token
    request.session.pop("auth_state", None)
    request.session.pop("auth_code_verifier", None)

    redirect_to = request.session.pop("auth_redirect", "/admin")
    return RedirectResponse(url=redirect_to, status_code=302)
