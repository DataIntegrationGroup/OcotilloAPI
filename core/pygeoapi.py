import os
import re
import textwrap
from importlib.util import find_spec
from pathlib import Path

import yaml
from fastapi import FastAPI

THING_COLLECTIONS = [
    {
        "id": "water_wells",
        "title": "Water Wells",
        "thing_type": "water well",
        "description": "Groundwater wells used for monitoring, production, and hydrogeologic investigations.",
        "keywords": ["well", "groundwater", "water-well"],
    },
    {
        "id": "springs",
        "title": "Springs",
        "thing_type": "spring",
        "description": "Natural spring features and associated spring monitoring points.",
        "keywords": ["springs", "groundwater-discharge"],
    },
    {
        "id": "diversions_surface_water",
        "title": "Surface Water Diversions",
        "thing_type": "diversion of surface water, etc.",
        "description": "Diversion structures such as ditches, canals, and intake points.",
        "keywords": ["surface-water", "diversion"],
    },
    {
        "id": "ephemeral_streams",
        "title": "Ephemeral Streams",
        "thing_type": "ephemeral stream",
        "description": "Stream reaches that flow only in direct response to precipitation events.",
        "keywords": ["ephemeral-stream", "surface-water"],
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
        "id": "abandoned_wells",
        "title": "Abandoned Wells",
        "thing_type": "abandoned well",
        "description": "Wells that are no longer active and are classified as abandoned.",
        "keywords": ["abandoned-well", "well"],
    },
    {
        "id": "artesian_wells",
        "title": "Artesian Wells",
        "thing_type": "artesian well",
        "description": "Wells that tap confined aquifers with artesian pressure conditions.",
        "keywords": ["artesian", "well"],
    },
    {
        "id": "dry_holes",
        "title": "Dry Holes",
        "thing_type": "dry hole",
        "description": "Drilled holes that did not produce usable groundwater.",
        "keywords": ["dry-hole", "well"],
    },
    {
        "id": "dug_wells",
        "title": "Dug Wells",
        "thing_type": "dug well",
        "description": "Large-diameter wells excavated by digging.",
        "keywords": ["dug-well", "well"],
    },
    {
        "id": "exploration_wells",
        "title": "Exploration Wells",
        "thing_type": "exploration well",
        "description": "Wells drilled to characterize geologic and groundwater conditions.",
        "keywords": ["exploration-well", "well"],
    },
    {
        "id": "injection_wells",
        "title": "Injection Wells",
        "thing_type": "injection well",
        "description": "Wells used to inject fluids into subsurface formations.",
        "keywords": ["injection-well", "well"],
    },
    {
        "id": "monitoring_wells",
        "title": "Monitoring Wells",
        "thing_type": "monitoring well",
        "description": "Wells primarily used for long-term groundwater monitoring.",
        "keywords": ["monitoring-well", "groundwater", "well"],
    },
    {
        "id": "observation_wells",
        "title": "Observation Wells",
        "thing_type": "observation well",
        "description": "Observation wells used for periodic water-level measurements.",
        "keywords": ["observation-well", "groundwater", "well"],
    },
    {
        "id": "piezometers",
        "title": "Piezometers",
        "thing_type": "piezometer",
        "description": "Piezometers used to measure hydraulic head at depth.",
        "keywords": ["piezometer", "groundwater", "well"],
    },
    {
        "id": "production_wells",
        "title": "Production Wells",
        "thing_type": "production well",
        "description": "Wells used for groundwater supply and extraction.",
        "keywords": ["production-well", "groundwater", "well"],
    },
    {
        "id": "test_wells",
        "title": "Test Wells",
        "thing_type": "test well",
        "description": "Temporary or investigative test wells.",
        "keywords": ["test-well", "well"],
    },
]


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "pygeoapi-config.yml"


def _mount_path() -> str:
    # Read and sanitize the configured mount path, defaulting to "/ogcapi".
    path = (os.environ.get("PYGEOAPI_MOUNT_PATH", "/ogcapi") or "").strip()

    # Treat empty or root ("/") values as invalid and fall back to the default.
    if path in {"", "/"}:
        path = "/ogcapi"

    # Ensure a single leading slash.
    if not path.startswith("/"):
        path = f"/{path}"

    # Remove any trailing slashes so "/ogcapi/" and "ogcapi/" both become "/ogcapi".
    path = path.rstrip("/")

    # Disallow traversal/current-directory segments.
    segments = [segment for segment in path.split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError(
            "Invalid PYGEOAPI_MOUNT_PATH: traversal segments are not allowed."
        )

    # Allow only slash-delimited segments of alphanumerics, underscore, or hyphen.
    if not re.fullmatch(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", path):
        raise ValueError(
            "Invalid PYGEOAPI_MOUNT_PATH: only letters, numbers, underscores, "
            "hyphens, and slashes are allowed."
        )

    return path


def _server_url() -> str:
    configured = os.environ.get("PYGEOAPI_SERVER_URL")
    if configured:
        return configured.rstrip("/")
    return f"http://localhost:8000{_mount_path()}"


def _pygeoapi_dir() -> Path:
    # Use instance-local ephemeral storage by default (GAE-safe).
    runtime_dir = (os.environ.get("PYGEOAPI_RUNTIME_DIR") or "").strip()
    path = Path(runtime_dir) if runtime_dir else Path("/tmp/pygeoapi")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _thing_collections_block(
    host: str,
    port: str,
    dbname: str,
    user: str,
    password_placeholder: str,
) -> str:
    resources: dict[str, dict] = {}
    for collection in THING_COLLECTIONS:
        resources[collection["id"]] = {
            "type": "collection",
            "title": collection["title"],
            "description": collection["description"],
            "keywords": collection["keywords"],
            "extents": {
                "spatial": {
                    "bbox": [-109.05, 31.33, -103.00, 37.00],
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                }
            },
            "providers": [
                {
                    "type": "feature",
                    "name": "PostgreSQL",
                    "data": {
                        "host": host,
                        "port": port,
                        "dbname": dbname,
                        "user": user,
                        "password": password_placeholder,
                        "search_path": ["public"],
                    },
                    "id_field": "id",
                    "table": f"ogc_{collection['id']}",
                    "geom_field": "point",
                }
            ],
        }

    block = yaml.safe_dump(
        resources,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    ).rstrip()
    return textwrap.indent(block, "  ")


def _pygeoapi_db_settings() -> tuple[str, str, str, str, str]:
    host = (
        (os.environ.get("PYGEOAPI_POSTGRES_HOST") or "").strip()
        or (os.environ.get("POSTGRES_HOST") or "").strip()
        or "127.0.0.1"
    )
    port = (
        (os.environ.get("PYGEOAPI_POSTGRES_PORT") or "").strip()
        or (os.environ.get("POSTGRES_PORT") or "").strip()
        or "5432"
    )
    dbname = (
        (os.environ.get("PYGEOAPI_POSTGRES_DB") or "").strip()
        or (os.environ.get("POSTGRES_DB") or "").strip()
        or "postgres"
    )
    user = (os.environ.get("PYGEOAPI_POSTGRES_USER") or "").strip() or (
        os.environ.get("POSTGRES_USER") or ""
    ).strip()
    if not user:
        raise RuntimeError(
            "PYGEOAPI_POSTGRES_USER or POSTGRES_USER must be set and non-empty "
            "to generate the pygeoapi configuration."
        )
    if (
        os.environ.get("PYGEOAPI_POSTGRES_PASSWORD") is None
        and os.environ.get("POSTGRES_PASSWORD") is None
    ):
        raise RuntimeError(
            "PYGEOAPI_POSTGRES_PASSWORD or POSTGRES_PASSWORD must be set to "
            "generate the pygeoapi configuration."
        )
    password_env_var = (
        "PYGEOAPI_POSTGRES_PASSWORD"
        if os.environ.get("PYGEOAPI_POSTGRES_PASSWORD") is not None
        else "POSTGRES_PASSWORD"
    )
    return host, port, dbname, user, f"${{{password_env_var}}}"


def _write_config(path: Path) -> None:
    host, port, dbname, user, password_placeholder = _pygeoapi_db_settings()
    template = _template_path().read_text(encoding="utf-8")
    config = template.format(
        server_url=_server_url(),
        postgres_host=host,
        postgres_port=port,
        postgres_db=dbname,
        postgres_user=user,
        postgres_password_env=password_placeholder,
        thing_collections_block=_thing_collections_block(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password_placeholder=password_placeholder,
        ),
    )
    # NOTE: The generated runtime config file at
    # `${PYGEOAPI_RUNTIME_DIR}/pygeoapi-config.yml` (default:
    # `/tmp/pygeoapi/pygeoapi-config.yml`) contains database connection details
    # (host, port, dbname, user). Although the password is expected to be
    # provided via environment variables at runtime by pygeoapi, this file
    # should still be treated as sensitive configuration:
    #   * Do not commit it to version control.
    #   * Do not expose it in logs, error messages, or diagnostics.
    #   * Ensure filesystem permissions restrict access appropriately.
    path.write_text(config, encoding="utf-8")


def _generate_openapi(config_path: Path, openapi_path: Path) -> None:
    from pygeoapi.openapi import generate_openapi_document

    # Avoid startup failures when backing tables are not yet present; pygeoapi
    # will skip invalid collections and still emit a standards-compliant spec.
    openapi = generate_openapi_document(
        config_path, "yaml", fail_on_invalid_collection=False
    )
    openapi_path.write_text(openapi, encoding="utf-8")


def mount_pygeoapi(app: FastAPI) -> None:
    if getattr(app.state, "pygeoapi_mounted", False):
        return
    if find_spec("pygeoapi") is None:
        raise RuntimeError(
            "pygeoapi is not installed. Rebuild/sync dependencies so /ogcapi can be mounted."
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

    app.state.pygeoapi_mounted = True
