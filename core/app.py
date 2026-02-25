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
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.openapi.utils import get_openapi

from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan event handler to seed data in development mode.
    """
    if settings.get_enum("MODE") == "development":
        from transfers.seed import seed_all

        seed_all(10, skip_if_exists=True)

    yield


app = FastAPI(
    title="Sample Location API",
    description="API for managing sample locations",
    version=settings.version,
    lifespan=lifespan,
)


# --- full OpenAPI schema ---
def full_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="Ocotillo API (Full)",
        version=settings.version,
        description="Full API schema (authorized users)",
        routes=app.routes,
    )
    app.openapi_schema = schema
    return app.openapi_schema


# --- public OpenAPI schema ---
def public_openapi():
    schema = get_openapi(
        title="Ocotillo API (Public)",
        version="0.0.1",
        description="Public API schema (anonymous users)",
        routes=app.routes,
    )

    # Keep only operations where the endpoint function is marked public
    new_paths = {}
    for path, path_item in schema["paths"].items():
        new_methods = {}
        for method, operation in path_item.items():
            # Recover the actual route handler

            route = next(
                (
                    r
                    for r in app.routes
                    if r.path == path and method.upper() in r.methods
                ),
                None,
            )
            if not route:
                continue

            endpoint = getattr(route, "endpoint", None)
            if getattr(endpoint, "_is_public", False):
                # Strip security info for public docs
                operation["security"] = []
                new_methods[method] = operation

        if new_methods:
            new_paths[path] = new_methods

    schema["paths"] = new_paths

    # --- Collect all referenced schemas recursively ---
    referenced = set()

    def collect_refs(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if (
                    k == "$ref"
                    and isinstance(v, str)
                    and v.startswith("#/components/schemas/")
                ):
                    referenced.add(v.split("/")[-1])
                else:
                    collect_refs(v)
        elif isinstance(obj, list):
            for item in obj:
                collect_refs(item)

    # Step 1: Collect refs from paths
    collect_refs(schema["paths"])

    # Step 2: Recursively resolve inside components
    visited = set()
    to_visit = set(referenced)

    while to_visit:
        name = to_visit.pop()
        if name in visited:
            continue
        visited.add(name)

        model = schema.get("components", {}).get("schemas", {}).get(name)
        if not model:
            continue

        collect_refs(model)
        # Add only new schemas we haven’t visited yet
        to_visit |= referenced - visited

    # Step 3: Filter components.schemas to only referenced ones
    if "components" in schema and "schemas" in schema["components"]:
        schema["components"]["schemas"] = {
            n: m for n, m in schema["components"]["schemas"].items() if n in referenced
        }

    # 4. Drop security schemes entirely for the public spec
    if "components" in schema and "securitySchemes" in schema["components"]:
        schema["components"].pop("securitySchemes", None)
    return schema


# set the public schema as the default
app.openapi = public_openapi

CLIENT_ID = os.environ.get("AUTHENTIK_CLIENT_ID")


@app.get("/docs-auth", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi-auth.json",
        title="Swagger UI",
        oauth2_redirect_url="/docs-auth/oauth2-redirect",
        init_oauth={
            "clientId": CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": True,  # if you use PKCE
        },
    )


@app.get("/openapi-auth.json", include_in_schema=False)
async def get_openapi_auth():
    return full_openapi()


@app.get("/docs-auth/oauth2-redirect", include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


def public_route(func):
    """Mark a route as public for OpenAPI filtering."""
    setattr(func, "_is_public", True)
    return func


# ============= EOF =============================================
