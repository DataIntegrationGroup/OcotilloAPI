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
import logging
import os
import time
from uuid import uuid4
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Response, status
from fastapi import Request
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.engine import get_db_session

from .settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan event handler to seed data in development mode.
    """
    if settings.get_enum("MODE") == "development":
        from transfers.seed import seed_all

        seed_all(10, skip_if_exists=True)

    app.state.instance_ready_at = time.perf_counter()
    logger.info(
        "instance startup complete",
        extra={
            "event": "instance_startup_complete",
            "startup_ms": round(
                (app.state.instance_ready_at - app.state.process_boot_started_at)
                * 1000,
                2,
            ),
        },
    )

    yield


def create_base_app() -> FastAPI:
    app = FastAPI(
        title="Sample Location API",
        description="API for managing sample locations",
        version=settings.version,
        lifespan=lifespan,
    )
    app.state.process_boot_started_at = time.perf_counter()
    app.state.instance_ready_at = None

    @app.middleware("http")
    async def log_request_lifecycle(request: Request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        logger.info(
            "request started",
            extra={
                "event": "request_started",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            logger.info(
                "request completed",
                extra={
                    "event": "request_completed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                },
            )

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

    def public_openapi():
        schema = get_openapi(
            title="Ocotillo API (Public)",
            version=settings.version,
            description="Public API schema (anonymous users)",
            routes=app.routes,
        )

        # Keep only operations where the endpoint function is marked public.
        new_paths = {}
        for path, path_item in schema["paths"].items():
            new_methods = {}
            for method, operation in path_item.items():
                route = next(
                    (
                        r
                        for r in app.routes
                        if getattr(r, "path", None) == path
                        and method.upper() in getattr(r, "methods", set())
                    ),
                    None,
                )
                if not route:
                    continue

                endpoint = getattr(route, "endpoint", None)
                if getattr(endpoint, "_is_public", False):
                    operation["security"] = []
                    new_methods[method] = operation

            if new_methods:
                new_paths[path] = new_methods

        schema["paths"] = new_paths

        referenced = set()

        def collect_refs(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if (
                        key == "$ref"
                        and isinstance(value, str)
                        and value.startswith("#/components/schemas/")
                    ):
                        referenced.add(value.split("/")[-1])
                    else:
                        collect_refs(value)
            elif isinstance(obj, list):
                for item in obj:
                    collect_refs(item)

        collect_refs(schema["paths"])

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
            to_visit |= referenced - visited

        if "components" in schema and "schemas" in schema["components"]:
            schema["components"]["schemas"] = {
                name: model
                for name, model in schema["components"]["schemas"].items()
                if name in referenced
            }

        if "components" in schema and "securitySchemes" in schema["components"]:
            schema["components"].pop("securitySchemes", None)
        return schema

    app.openapi = public_openapi

    client_id = os.environ.get("AUTHENTIK_CLIENT_ID")

    @app.get("/docs-auth", include_in_schema=False)
    async def custom_swagger_ui():
        return get_swagger_ui_html(
            openapi_url="/openapi-auth.json",
            title="Swagger UI",
            oauth2_redirect_url="/docs-auth/oauth2-redirect",
            init_oauth={
                "clientId": client_id,
                "usePkceWithAuthorizationCodeGrant": True,
            },
        )

    @app.get("/openapi-auth.json", include_in_schema=False)
    async def get_openapi_auth():
        return full_openapi()

    @app.get("/docs-auth/oauth2-redirect", include_in_schema=False)
    async def swagger_ui_redirect():
        return get_swagger_ui_oauth2_redirect_html()

    @app.get("/_ah/warmup", include_in_schema=False)
    async def warmup():
        return {"status": "ok"}

    @app.get("/health", tags=["meta"])
    @public_route
    def health(response: Response, session: Session = Depends(get_db_session)):
        # Ping the database so a 200 actually proves PostGIS is reachable, not
        # just that the process is up. Uptime monitors / status pages assert on
        # the "db" field; on failure return 503 so they flag the outage.
        try:
            session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            logger.exception("health check: database ping failed")
            db_ok = False

        if not db_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "error",
            "version": settings.version,
        }

    return app


def public_route(func):
    """Mark a route as public for OpenAPI filtering."""
    setattr(func, "_is_public", True)
    return func


# ============= EOF =============================================
