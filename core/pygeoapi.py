import asyncio
import logging
import os
from importlib.util import find_spec
from pathlib import Path

import anyio
from fastapi import FastAPI, Request
from sqlalchemy import text

from db.engine import session_ctx

logger = logging.getLogger(__name__)

THING_COLLECTIONS = [
    {
        "id": "wells",
        "title": "Wells",
        "thing_type": "water well",
        "description": "Groundwater wells used for monitoring, production, and hydrogeologic investigations.",
        "keywords": ["wells", "groundwater", "water-well"],
    },
    {
        "id": "springs",
        "title": "Springs",
        "thing_type": "spring",
        "description": "Natural spring features and associated spring monitoring points.",
        "keywords": ["springs", "groundwater-discharge"],
    },
    {
        "id": "abandoned_wells",
        "title": "Abandoned Wells",
        "thing_type": "abandoned well",
        "description": "Wells that are no longer active and are classified as abandoned.",
        "keywords": ["abandoned-well"],
    },
    {
        "id": "artesian_wells",
        "title": "Artesian Wells",
        "thing_type": "artesian well",
        "description": "Wells that tap confined aquifers with artesian pressure conditions.",
        "keywords": ["artesian", "well"],
    },
    {
        "id": "diversions_surface_water",
        "title": "Surface Water Diversions",
        "thing_type": "diversion of surface water, etc.",
        "description": "Diversion structures such as ditches, canals, and intake points.",
        "keywords": ["surface-water", "diversion"],
    },
    {
        "id": "dry_holes",
        "title": "Dry Holes",
        "thing_type": "dry hole",
        "description": "Drilled holes that did not produce usable groundwater.",
        "keywords": ["dry-hole"],
    },
    {
        "id": "dug_wells",
        "title": "Dug Wells",
        "thing_type": "dug well",
        "description": "Large-diameter wells excavated by digging.",
        "keywords": ["dug-well"],
    },
    {
        "id": "ephemeral_streams",
        "title": "Ephemeral Streams",
        "thing_type": "ephemeral stream",
        "description": "Stream reaches that flow only in direct response to precipitation events.",
        "keywords": ["ephemeral-stream", "surface-water"],
    },
    {
        "id": "exploration_wells",
        "title": "Exploration Wells",
        "thing_type": "exploration well",
        "description": "Wells drilled to characterize geologic and groundwater conditions.",
        "keywords": ["exploration-well"],
    },
    {
        "id": "injection_wells",
        "title": "Injection Wells",
        "thing_type": "injection well",
        "description": "Wells used to inject fluids into subsurface formations.",
        "keywords": ["injection-well"],
    },
    {
        "id": "lakes_ponds_reservoirs",
        "title": "Lakes, Ponds, and Reservoirs",
        "thing_type": "lake, pond or reservoir",
        "description": "Surface-water bodies monitored as feature locations.",
        "keywords": ["lake", "pond", "reservoir", "surface-water"],
    },
    {
        "id": "meteorological_stations",
        "title": "Meteorological Stations",
        "thing_type": "meteorological station",
        "description": "Weather and climate monitoring station locations.",
        "keywords": ["meteorological-station", "weather"],
    },
    {
        "id": "monitoring_wells",
        "title": "Monitoring Wells",
        "thing_type": "monitoring well",
        "description": "Wells primarily used for long-term groundwater monitoring.",
        "keywords": ["monitoring-well", "groundwater"],
    },
    {
        "id": "observation_wells",
        "title": "Observation Wells",
        "thing_type": "observation well",
        "description": "Observation wells used for periodic water-level measurements.",
        "keywords": ["observation-well", "groundwater"],
    },
    {
        "id": "other_things",
        "title": "Other Thing Types",
        "thing_type": "other",
        "description": "Feature records that do not match another defined thing type.",
        "keywords": ["other"],
    },
    {
        "id": "outfalls_wastewater_return_flow",
        "title": "Outfalls and Return Flow",
        "thing_type": "outfall of wastewater or return flow",
        "description": "Outfall and return-flow monitoring points.",
        "keywords": ["outfall", "return-flow", "surface-water"],
    },
    {
        "id": "perennial_streams",
        "title": "Perennial Streams",
        "thing_type": "perennial stream",
        "description": "Stream reaches with continuous or near-continuous flow.",
        "keywords": ["perennial-stream", "surface-water"],
    },
    {
        "id": "piezometers",
        "title": "Piezometers",
        "thing_type": "piezometer",
        "description": "Piezometers used to measure hydraulic head at depth.",
        "keywords": ["piezometer", "groundwater"],
    },
    {
        "id": "production_wells",
        "title": "Production Wells",
        "thing_type": "production well",
        "description": "Wells used for groundwater supply and extraction.",
        "keywords": ["production-well", "groundwater"],
    },
    {
        "id": "rock_sample_locations",
        "title": "Rock Sample Locations",
        "thing_type": "rock sample location",
        "description": "Locations where rock samples were collected or documented.",
        "keywords": ["rock-sample"],
    },
    {
        "id": "soil_gas_sample_locations",
        "title": "Soil Gas Sample Locations",
        "thing_type": "soil gas sample location",
        "description": "Locations where soil gas measurements or samples were collected.",
        "keywords": ["soil-gas", "sample-location"],
    },
    {
        "id": "test_wells",
        "title": "Test Wells",
        "thing_type": "test well",
        "description": "Temporary or investigative test wells.",
        "keywords": ["test-well"],
    },
]


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


def _thing_collections_block(
    host: str,
    port: str,
    dbname: str,
    user: str,
    password: str,
) -> str:
    blocks = []
    for collection in THING_COLLECTIONS:
        keywords = ", ".join(collection["keywords"])
        blocks.append(
            f"""  {collection["id"]}:
    type: collection
    title: {collection["title"]}
    description: {collection["description"]}
    keywords: [{keywords}]
    extents:
      spatial:
        bbox: [-109.05, 31.33, -103.00, 37.00]
        crs: http://www.opengis.net/def/crs/OGC/1.3/CRS84
    providers:
      - type: feature
        name: PostgreSQL
        data:
          host: {host}
          port: {port}
          dbname: {dbname}
          user: {user}
          password: {password}
          search_path: [public]
        id_field: id
        table: ogc_{collection["id"]}
        geom_field: point"""
        )
    return "\n\n".join(blocks)


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
        postgres_password="${POSTGRES_PASSWORD}",
        thing_collections_block=_thing_collections_block(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password="${POSTGRES_PASSWORD}",
        ),
    )
    path.write_text(config, encoding="utf-8")


def _required_core_tables_exist() -> bool:
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


def _required_depth_tables_exist() -> bool:
    with session_ctx() as session:
        names = (
            "observation",
            "sample",
            "field_activity",
            "field_event",
        )
        for name in names:
            exists = session.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": f"public.{name}"},
            ).scalar_one()
            if not exists:
                return False
    return True


def _required_tds_tables_exist() -> bool:
    with session_ctx() as session:
        names = (
            'public."NMA_MajorChemistry"',
            'public."NMA_Chemistry_SampleInfo"',
        )
        for name in names:
            exists = session.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": name},
            ).scalar_one()
            if not exists:
                return False
    return True


def _required_view_names() -> list[str]:
    names = [f"ogc_{collection['id']}" for collection in THING_COLLECTIONS]
    names.append("ogc_latest_depth_to_water_wells")
    names.append("ogc_avg_tds_wells")
    return names


def _required_views_exist() -> bool:
    with session_ctx() as session:
        for name in _required_view_names():
            exists = session.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": f"public.{name}"},
            ).scalar_one()
            if not exists:
                return False
    return True


def _create_supporting_views() -> None:
    if not _required_core_tables_exist():
        return

    with session_ctx() as session:
        for collection in THING_COLLECTIONS:
            session.execute(text(f'DROP VIEW IF EXISTS ogc_{collection["id"]}'))
            thing_type = collection["thing_type"].replace("'", "''")
            session.execute(
                text(
                    f"""
                CREATE OR REPLACE VIEW ogc_{collection["id"]} AS
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
                WHERE t.thing_type = '{thing_type}'
                """
                )
            )
        if _required_depth_tables_exist():
            session.execute(text("DROP VIEW IF EXISTS ogc_latest_depth_to_water_wells"))
            session.execute(
                text(
                    """
                    CREATE OR REPLACE VIEW ogc_latest_depth_to_water_wells AS
                    WITH latest_location AS (
                        SELECT DISTINCT ON (lta.thing_id)
                            lta.thing_id,
                            lta.location_id,
                            lta.effective_start
                        FROM location_thing_association AS lta
                        WHERE lta.effective_end IS NULL
                        ORDER BY lta.thing_id, lta.effective_start DESC
                    ),
                    ranked_obs AS (
                        SELECT
                            fe.thing_id,
                            o.id AS observation_id,
                            o.observation_datetime,
                            o.value,
                            o.measuring_point_height,
                            (o.value - o.measuring_point_height) AS depth_to_water_bgs,
                            ROW_NUMBER() OVER (
                                PARTITION BY fe.thing_id
                                ORDER BY o.observation_datetime DESC, o.id DESC
                            ) AS rn
                        FROM observation AS o
                        JOIN sample AS s ON s.id = o.sample_id
                        JOIN field_activity AS fa ON fa.id = s.field_activity_id
                        JOIN field_event AS fe ON fe.id = fa.field_event_id
                        JOIN thing AS t ON t.id = fe.thing_id
                        WHERE
                            t.thing_type = 'water well'
                            AND fa.activity_type = 'groundwater level'
                            AND o.value IS NOT NULL
                            AND o.measuring_point_height IS NOT NULL
                    )
                    SELECT
                        t.id AS id,
                        t.name,
                        t.thing_type,
                        ro.observation_id,
                        ro.observation_datetime,
                        ro.value AS depth_to_water_reference,
                        ro.measuring_point_height,
                        ro.depth_to_water_bgs,
                        l.point
                    FROM ranked_obs AS ro
                    JOIN thing AS t ON t.id = ro.thing_id
                    JOIN latest_location AS ll ON ll.thing_id = t.id
                    JOIN location AS l ON l.id = ll.location_id
                    WHERE ro.rn = 1
                    """
                )
            )
        else:
            session.execute(text("DROP VIEW IF EXISTS ogc_latest_depth_to_water_wells"))
            session.execute(
                text(
                    """
                    CREATE OR REPLACE VIEW ogc_latest_depth_to_water_wells AS
                    SELECT
                        t.id AS id,
                        t.name,
                        t.thing_type,
                        NULL::integer AS observation_id,
                        NULL::timestamptz AS observation_datetime,
                        NULL::double precision AS depth_to_water_reference,
                        NULL::double precision AS measuring_point_height,
                        NULL::double precision AS depth_to_water_bgs,
                        l.point
                    FROM thing AS t
                    JOIN location_thing_association AS lta ON lta.thing_id = t.id
                    JOIN location AS l ON l.id = lta.location_id
                    WHERE FALSE
                    """
                )
            )
        if _required_tds_tables_exist():
            session.execute(text("DROP VIEW IF EXISTS ogc_avg_tds_wells"))
            session.execute(
                text(
                    """
                    CREATE OR REPLACE VIEW ogc_avg_tds_wells AS
                    WITH latest_location AS (
                        SELECT DISTINCT ON (lta.thing_id)
                            lta.thing_id,
                            lta.location_id,
                            lta.effective_start
                        FROM location_thing_association AS lta
                        WHERE lta.effective_end IS NULL
                        ORDER BY lta.thing_id, lta.effective_start DESC
                    ),
                    tds_obs AS (
                        SELECT
                            csi.thing_id,
                            mc.id AS major_chemistry_id,
                            mc."AnalysisDate" AS analysis_date,
                            mc."SampleValue" AS sample_value,
                            mc."Units" AS units
                        FROM "NMA_MajorChemistry" AS mc
                        JOIN "NMA_Chemistry_SampleInfo" AS csi
                            ON csi.id = mc.chemistry_sample_info_id
                        JOIN thing AS t ON t.id = csi.thing_id
                        WHERE
                            t.thing_type = 'water well'
                            AND mc."SampleValue" IS NOT NULL
                            AND (
                                lower(coalesce(mc."Analyte", '')) IN (
                                    'tds',
                                    'total dissolved solids'
                                )
                                OR lower(coalesce(mc."Symbol", '')) = 'tds'
                            )
                    )
                    SELECT
                        t.id AS id,
                        t.name,
                        t.thing_type,
                        COUNT(to2.major_chemistry_id)::integer AS tds_observation_count,
                        AVG(to2.sample_value)::double precision AS avg_tds_value,
                        MIN(to2.analysis_date) AS first_tds_observation_datetime,
                        MAX(to2.analysis_date) AS latest_tds_observation_datetime,
                        l.point
                    FROM tds_obs AS to2
                    JOIN thing AS t ON t.id = to2.thing_id
                    JOIN latest_location AS ll ON ll.thing_id = t.id
                    JOIN location AS l ON l.id = ll.location_id
                    GROUP BY t.id, t.name, t.thing_type, l.point
                    """
                )
            )
        else:
            session.execute(text("DROP VIEW IF EXISTS ogc_avg_tds_wells"))
            session.execute(
                text(
                    """
                    CREATE OR REPLACE VIEW ogc_avg_tds_wells AS
                    SELECT
                        t.id AS id,
                        t.name,
                        t.thing_type,
                        NULL::integer AS tds_observation_count,
                        NULL::double precision AS avg_tds_value,
                        NULL::timestamptz AS first_tds_observation_datetime,
                        NULL::timestamptz AS latest_tds_observation_datetime,
                        l.point
                    FROM thing AS t
                    JOIN location_thing_association AS lta ON lta.thing_id = t.id
                    JOIN location AS l ON l.id = lta.location_id
                    WHERE FALSE
                    """
                )
            )
        session.commit()


def _prepare_pygeoapi_views() -> str:
    if not _required_core_tables_exist():
        return "unavailable"
    _create_supporting_views()
    return "ready"


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

    # Eagerly create/refresh supporting views on startup so the first /oapi
    # request does not race pygeoapi provider reflection.
    try:
        status = _prepare_pygeoapi_views()
        if status == "ready":
            app.state.pygeoapi_views_ready = True
            app.state.pygeoapi_views_unavailable = False
            app.state.pygeoapi_views_error = None
            logger.info("pygeoapi supporting views are ready at startup")
        else:
            app.state.pygeoapi_views_ready = False
            app.state.pygeoapi_views_unavailable = True
            app.state.pygeoapi_views_error = "required tables not available"
            logger.warning(
                "pygeoapi supporting views unavailable at startup: required tables are missing"
            )
    except Exception:
        app.state.pygeoapi_views_ready = False
        app.state.pygeoapi_views_unavailable = True
        app.state.pygeoapi_views_error = "supporting view setup failed"
        logger.exception("pygeoapi supporting view setup failed at startup")

    if not getattr(app.state, "pygeoapi_view_setup_middleware_added", False):
        if not hasattr(app.state, "pygeoapi_views_ready"):
            app.state.pygeoapi_views_ready = False
        if not hasattr(app.state, "pygeoapi_views_unavailable"):
            app.state.pygeoapi_views_unavailable = False
        app.state.pygeoapi_views_recovery_attempted = False
        app.state.pygeoapi_view_setup_lock = asyncio.Lock()

        @app.middleware("http")
        async def _ensure_pygeoapi_views(request: Request, call_next):
            if request.url.path.startswith(mount_path):
                should_attempt = (
                    not app.state.pygeoapi_views_ready
                    and not app.state.pygeoapi_views_unavailable
                )

                # If app already marked ready, verify required views still exist
                # to handle incremental changes (new view added) without restart.
                if not should_attempt and app.state.pygeoapi_views_ready:
                    try:
                        views_exist = await anyio.to_thread.run_sync(
                            _required_views_exist
                        )
                        if not views_exist:
                            app.state.pygeoapi_views_ready = False
                            should_attempt = True
                    except Exception:
                        logger.exception("Failed checking pygeoapi view readiness")

                # One-time recovery path after an earlier unavailable/failure state.
                if (
                    not should_attempt
                    and app.state.pygeoapi_views_unavailable
                    and not app.state.pygeoapi_views_recovery_attempted
                ):
                    app.state.pygeoapi_views_recovery_attempted = True
                    should_attempt = True

            else:
                should_attempt = False

            if should_attempt:
                async with app.state.pygeoapi_view_setup_lock:
                    if not app.state.pygeoapi_views_ready and (
                        not app.state.pygeoapi_views_unavailable
                        or app.state.pygeoapi_views_recovery_attempted
                    ):
                        try:
                            status = await anyio.to_thread.run_sync(
                                _prepare_pygeoapi_views
                            )
                            if status == "ready":
                                app.state.pygeoapi_views_ready = True
                                app.state.pygeoapi_views_unavailable = False
                                app.state.pygeoapi_views_error = None
                                logger.info("pygeoapi supporting views are ready")
                            elif status == "unavailable":
                                app.state.pygeoapi_views_unavailable = True
                                app.state.pygeoapi_views_error = (
                                    "required tables not available"
                                )
                                logger.warning(
                                    "pygeoapi supporting views unavailable: required tables are missing"
                                )
                        except Exception:
                            app.state.pygeoapi_views_unavailable = True
                            app.state.pygeoapi_views_error = (
                                "supporting view setup failed"
                            )
                            logger.exception(
                                "pygeoapi supporting view setup failed; disabling retries"
                            )
            return await call_next(request)

        app.state.pygeoapi_view_setup_middleware_added = True

    app.state.pygeoapi_mounted = True
