import os
from importlib.util import find_spec
from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from sqlalchemy import text

from db.engine import session_ctx


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "pygeoapi-config.yml"


def _mount_path() -> str:
    # Read and sanitize the configured mount path, defaulting to "/oapi".
    path = (os.environ.get("PYGEOAPI_MOUNT_PATH", "/oapi") or "").strip()

    # Treat empty or root ("/") values as invalid and fall back to the default.
    if path in {"", "/"}:
        path = "/oapi"

    # Ensure a single leading slash.
    if not path.startswith("/"):
        path = f"/{path}"

    # Remove any trailing slashes so "/oapi/" and "oapi/" both become "/oapi".
    path = path.rstrip("/")
    return path


def _server_url() -> str:
    configured = os.environ.get("PYGEOAPI_SERVER_URL")
    if configured:
        return configured.rstrip("/")
    return f"http://localhost:8000{_mount_path()}"


def _pygeoapi_dir() -> Path:
    path = _project_root() / ".pygeoapi"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_config(path: Path) -> None:
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB", "postgres")
    user = (os.environ.get("POSTGRES_USER") or "").strip()
    template = _template_path().read_text(encoding="utf-8")
    config = template.format(
        server_url=_server_url(),
        postgres_host=host,
        postgres_port=port,
        postgres_db=dbname,
        postgres_user=user,
        # Avoid storing the actual password in clear text; resolve from env at runtime.
        postgres_password="${POSTGRES_PASSWORD}",
    )
    path.write_text(config, encoding="utf-8")


def _required_tables_exist() -> bool:
    with session_ctx() as session:
        names = (
            "location",
            "thing",
            "location_thing_association",
        )
        for name in names:
            exists = session.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": f"public.{name}"},
            ).scalar_one()
            if not exists:
                return False
    return True


def _create_supporting_views() -> None:
    with session_ctx() as session:
        session.execute(text("""
                CREATE OR REPLACE VIEW ogc_wells AS
                WITH latest_location AS (
                    SELECT DISTINCT ON (lta.thing_id)
                        lta.thing_id,
                        lta.location_id,
                        lta.effective_start
                    FROM location_thing_association AS lta
                    WHERE lta.effective_end IS NULL
                    ORDER BY lta.thing_id, lta.effective_start DESC
                )
                SELECT
                    t.id,
                    t.name,
                    t.thing_type,
                    t.first_visit_date,
                    t.nma_pk_welldata,
                    t.well_depth,
                    t.hole_depth,
                    t.well_casing_diameter,
                    t.well_casing_depth,
                    t.well_completion_date,
                    t.well_driller_name,
                    t.well_construction_method,
                    t.well_pump_type,
                    t.well_pump_depth,
                    t.formation_completion_code,
                    t.nma_formation_zone,
                    t.release_status,
                    l.point
                FROM thing AS t
                JOIN latest_location AS ll ON ll.thing_id = t.id
                JOIN location AS l ON l.id = ll.location_id
                WHERE t.thing_type = 'water well'
                """))
        session.execute(text("""
                CREATE OR REPLACE VIEW ogc_springs AS
                WITH latest_location AS (
                    SELECT DISTINCT ON (lta.thing_id)
                        lta.thing_id,
                        lta.location_id,
                        lta.effective_start
                    FROM location_thing_association AS lta
                    WHERE lta.effective_end IS NULL
                    ORDER BY lta.thing_id, lta.effective_start DESC
                )
                SELECT
                    t.id,
                    t.name,
                    t.thing_type,
                    t.first_visit_date,
                    t.spring_type,
                    t.nma_pk_welldata,
                    t.release_status,
                    l.point
                FROM thing AS t
                JOIN latest_location AS ll ON ll.thing_id = t.id
                JOIN location AS l ON l.id = ll.location_id
                WHERE t.thing_type = 'spring'
                """))
        session.commit()


def _generate_openapi(_config_path: Path, openapi_path: Path) -> None:
    openapi = f"""openapi: 3.0.2
info:
  title: Ocotillo OGC API
  version: 1.0.0
servers:
  - url: {_server_url()}
paths: {{}}
"""
    openapi_path.write_text(openapi, encoding="utf-8")


def mount_pygeoapi(app: FastAPI) -> None:
    if getattr(app.state, "pygeoapi_mounted", False):
        return
    if find_spec("pygeoapi") is None:
        raise RuntimeError(
            "pygeoapi is not installed. Rebuild/sync dependencies so /oapi can be mounted."
        )

    pygeoapi_dir = _pygeoapi_dir()
    config_path = pygeoapi_dir / "pygeoapi-config.yml"
    openapi_path = pygeoapi_dir / "pygeoapi-openapi.yml"
    _write_config(config_path)
    _generate_openapi(config_path, openapi_path)

    os.environ["PYGEOAPI_CONFIG"] = str(config_path)
    os.environ["PYGEOAPI_OPENAPI"] = str(openapi_path)

    from pygeoapi.starlette_app import APP as pygeoapi_app

    mount_path = _mount_path()
    app.mount(mount_path, pygeoapi_app)

    if not getattr(app.state, "pygeoapi_view_setup_middleware_added", False):
        app.state.pygeoapi_views_ready = False
        app.state.pygeoapi_views_unavailable = False

        @app.middleware("http")
        async def _ensure_pygeoapi_views(request: Request, call_next):
            if (
                request.url.path.startswith(mount_path)
                and not app.state.pygeoapi_views_ready
                and not app.state.pygeoapi_views_unavailable
            ):
                try:
                    if _required_tables_exist():
                        _create_supporting_views()
                        app.state.pygeoapi_views_ready = True
                    else:
                        app.state.pygeoapi_views_unavailable = True
                except Exception:
                    pass
            return await call_next(request)

        app.state.pygeoapi_view_setup_middleware_added = True

    app.state.pygeoapi_mounted = True
