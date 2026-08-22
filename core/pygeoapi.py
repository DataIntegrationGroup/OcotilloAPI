import importlib.util
import os
import re
import sys
import textwrap
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import urlparse

import yaml
from fastapi import FastAPI

# Consumed by pygeoapi at import time only; see _load_pygeoapi_app.
_PYGEOAPI_ENV_KEYS = ("PYGEOAPI_CONFIG", "PYGEOAPI_OPENAPI")

THING_COLLECTIONS = [
    {
        "id": "water_wells",
        "title": "Water Wells",
        "thing_type": "water well",
        "description": (
            "Groundwater wells: drilled or dug access points into an aquifer, "
            "used for monitoring, production, and hydrogeologic investigation. "
            "Each feature is one well from the monitoring-point register, placed "
            "at the most recent location recorded for it, and carries the "
            "construction details held for it -- total and hole depth, casing "
            "diameter and depth, completion date, driller, construction method, "
            "pump type and depth, and the geologic formation it is completed in. "
            "This is the starting point for groundwater work: the water-level and "
            "chemistry layers are all derived from these same wells."
        ),
        "keywords": [
            "water-wells",
            "wells",
            "groundwater",
            "aquifer",
            "monitoring-points",
            "well-construction",
        ],
    },
    {
        "id": "springs",
        "title": "Springs",
        "thing_type": "spring",
        "description": (
            "Springs: places where groundwater reaches the land surface under its "
            "own pressure, without pumping. Each feature is one spring from the "
            "monitoring-point register, placed at the most recent location "
            "recorded for it. Use it to map natural groundwater discharge, the "
            "groundwater contribution to streamflow, and the water sources that "
            "support desert ecosystems."
        ),
        "keywords": [
            "springs",
            "groundwater-discharge",
            "monitoring-points",
            "surface-water",
            "seeps",
        ],
    },
    {
        "id": "diversions_surface_water",
        "title": "Surface Water Diversions",
        "thing_type": "diversion of surface water, etc.",
        "description": (
            "Surface-water diversions: structures that take water out of a "
            "stream, river, or canal -- ditches, acequias, headgates and intakes. "
            "Each feature is one diversion from the monitoring-point register, "
            "placed at the most recent location recorded for it. Use it to see "
            "where surface water is withdrawn and to pair those points with "
            "downstream flow records."
        ),
        "keywords": [
            "surface-water",
            "diversion",
            "ditches",
            "acequias",
            "headgates",
            "monitoring-points",
        ],
    },
    {
        "id": "ephemeral_streams",
        "title": "Ephemeral Streams",
        "thing_type": "ephemeral stream",
        "description": (
            "Ephemeral stream reaches: channels that carry water only in direct "
            "response to rain or snowmelt and are dry the rest of the year. Each "
            "feature is one monitored reach from the register, placed at the most "
            "recent location recorded for it. Use it for flash-flow and "
            "storm-response work, and to distinguish these channels from reaches "
            "that flow year-round."
        ),
        "keywords": [
            "ephemeral-stream",
            "surface-water",
            "intermittent-flow",
            "storm-response",
            "monitoring-points",
        ],
    },
    {
        "id": "lakes_ponds_reservoirs",
        "title": "Lakes, Ponds, and Reservoirs",
        "thing_type": "lake, pond or reservoir",
        "description": (
            "Standing bodies of surface water monitored as sites -- natural "
            "lakes, ponds, and built reservoirs. Each feature is one water body "
            "from the monitoring-point register, placed at the most recent "
            "location recorded for it. Use it for storage and surface-water "
            "quality work, and as context for nearby groundwater levels."
        ),
        "keywords": [
            "lake",
            "pond",
            "reservoir",
            "surface-water",
            "storage",
            "monitoring-points",
        ],
    },
    {
        "id": "meteorological_stations",
        "title": "Meteorological Stations",
        "thing_type": "meteorological station",
        "description": (
            "Weather and climate stations: sites that record conditions such as "
            "precipitation, temperature, and evaporation. Each feature is one "
            "station from the monitoring-point register, placed at the most "
            "recent location recorded for it. Use it to relate groundwater and "
            "streamflow behaviour to the weather that drives it."
        ),
        "keywords": [
            "meteorological-station",
            "weather",
            "climate",
            "precipitation",
            "monitoring-points",
        ],
    },
    {
        "id": "other_things",
        "title": "Other Thing Types",
        "thing_type": "other",
        "description": (
            "Monitoring points that do not fall into any of the defined feature "
            "types. Each feature is one such point from the register, placed at "
            "the most recent location recorded for it. The set is small and "
            "mixed, with no shared meaning between its members, so it is "
            "published only on the internal mount for staff triage -- typically "
            "to find records that need reclassifying."
        ),
        "keywords": [
            "other",
            "unclassified",
            "monitoring-points",
            "internal",
            "triage",
        ],
        # "Thing" is internal data-model vocabulary and "other" names no
        # recognisable feature class, so this layer is not published on the
        # public mount (BDMS-979). Staff GIS clients still reach it through
        # /ogcapi-internal, and ogc_other_things is retained either way.
        "internal_only": True,
    },
    {
        "id": "outfalls_wastewater_return_flow",
        "title": "Outfalls and Return Flow",
        "thing_type": "outfall of wastewater or return flow",
        "description": (
            "Outfalls and return flow: points where treated wastewater or unused "
            "irrigation water re-enters a stream or channel. Each feature is one "
            "outfall from the monitoring-point register, placed at the most "
            "recent location recorded for it. Use it in water-quality work, where "
            "these points mark deliberate inputs to a watercourse."
        ),
        "keywords": [
            "outfall",
            "return-flow",
            "wastewater",
            "surface-water",
            "water-quality",
            "monitoring-points",
        ],
    },
    {
        "id": "perennial_streams",
        "title": "Perennial Streams",
        "thing_type": "perennial stream",
        "description": (
            "Perennial stream reaches: channels that flow year-round in most "
            "years, sustained between storms by groundwater discharge. Each "
            "feature is one monitored reach from the register, placed at the most "
            "recent location recorded for it. Use it for base-flow and "
            "surface-water/groundwater interaction work."
        ),
        "keywords": [
            "perennial-stream",
            "surface-water",
            "base-flow",
            "streamflow",
            "monitoring-points",
        ],
    },
    {
        "id": "rock_sample_locations",
        "title": "Rock Sample Locations",
        "thing_type": "rock sample location",
        "description": (
            "Places where rock samples were collected or outcrop geology was "
            "documented. Each feature is one sample location from the "
            "monitoring-point register, placed at the most recent location "
            "recorded for it. Use it to find where physical samples backing "
            "geologic mapping and laboratory analysis came from."
        ),
        "keywords": [
            "rock-sample",
            "geology",
            "sample-location",
            "outcrop",
            "monitoring-points",
        ],
    },
    {
        "id": "soil_gas_sample_locations",
        "title": "Soil Gas Sample Locations",
        "thing_type": "soil gas sample location",
        "description": (
            "Places where gas held in the pore space of soil was sampled. Each "
            "feature is one sample location from the monitoring-point register, "
            "placed at the most recent location recorded for it. Soil gas is used "
            "to detect vapours rising from buried contamination or from geologic "
            "sources, so these points usually mark contamination or "
            "resource-exploration surveys."
        ),
        "keywords": [
            "soil-gas",
            "sample-location",
            "vapour-survey",
            "contamination",
            "monitoring-points",
        ],
    },
]


# OGC API - EDR collections (see ADR3). Each is backed by a publication-
# filtered ogc_* view and served by the custom PostgreSQL EDR provider.
EDR_COLLECTIONS = [
    {
        "id": "waterlevels",
        "title": "Water Levels",
        "description": (
            "Depth-to-water through time at each well, served as time series "
            "rather than as one point per well. Two kinds of record are combined: "
            "manual measurements taken by field staff during a visit, and "
            "continuous records from pressure transducers left down the well, "
            "which log automatically at a fixed interval. Each transducer "
            "deployment is exposed as its own EDR instance, so a well's record "
            "can be read deployment by deployment or as a whole. Use it to plot "
            "hydrographs and to see how water levels respond to pumping, "
            "recharge, and drought."
        ),
        "keywords": [
            "groundwater",
            "water-level",
            "depth-to-water",
            "time-series",
            "hydrograph",
            "transducer",
            "edr",
        ],
        "table": "ogc_waterlevels",
        "instance_field": "deployment_id",
    },
    {
        "id": "water_chemistry",
        "title": "Water Chemistry",
        "description": (
            "Water-chemistry analyses through time, one record per analyte per "
            "sample, served as time series. The layer draws together the major, "
            "minor and trace, and field-parameter analysis records from the "
            "legacy chemistry tables, keyed by the analyte name as the laboratory "
            "recorded it. Use it to follow one constituent at one site over time "
            "-- the chemistry feature layers, by contrast, give the latest value "
            "for every analyte at once."
        ),
        "keywords": [
            "water-chemistry",
            "water-quality",
            "analyte",
            "time-series",
            "laboratory-results",
            "edr",
        ],
        "table": "ogc_water_chemistry",
        "instance_field": None,
    },
]


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "pygeoapi-config.yml"


def _internal_template_path() -> Path:
    return Path(__file__).resolve().parent / "pygeoapi-config-internal.yml"


def _sanitized_mount_path(env_var: str, default: str) -> str:
    # Read and sanitize the configured mount path, falling back to `default`.
    path = (os.environ.get(env_var, default) or "").strip()

    # Treat empty or root ("/") values as invalid and fall back to the default.
    if path in {"", "/"}:
        path = default

    # Ensure a single leading slash.
    if not path.startswith("/"):
        path = f"/{path}"

    # Remove trailing slashes so "/ogcapi/" and "ogcapi/" both become
    # "/ogcapi".
    path = path.rstrip("/")

    # Disallow traversal/current-directory segments.
    segments = [segment for segment in path.split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError(f"Invalid {env_var}: traversal segments are not allowed.")

    # Allow only slash-delimited segments of alphanumerics, underscore,
    # or hyphen.
    if not re.fullmatch(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", path):
        raise ValueError(
            f"Invalid {env_var}: only letters, numbers, underscores, "
            "hyphens, and slashes are allowed."
        )

    return path


def _mount_path() -> str:
    return _sanitized_mount_path("PYGEOAPI_MOUNT_PATH", "/ogcapi")


def _internal_mount_path() -> str:
    return _sanitized_mount_path("PYGEOAPI_INTERNAL_MOUNT_PATH", "/ogcapi-internal")


def _server_url() -> str:
    configured = os.environ.get("PYGEOAPI_SERVER_URL")
    if configured:
        return configured.rstrip("/")
    return f"http://localhost:8000{_mount_path()}"


def _internal_server_url() -> str:
    configured = os.environ.get("PYGEOAPI_INTERNAL_SERVER_URL")
    if configured:
        return configured.rstrip("/")
    # Derived from the application root rather than hardcoded to localhost.
    # PYGEOAPI_INTERNAL_SERVER_URL is set in no deploy config -- not
    # app.template.yaml, not any of the three CD workflows -- so every
    # deployed environment fell into this branch and pygeoapi stamped
    # "http://localhost:8000/ogcapi-internal" into the `self` and `next` links
    # of every collection and items response. QGIS and ArcGIS Pro follow those
    # links to page, so both walked off to localhost after the first page.
    # _app_base_url() reads PYGEOAPI_SERVER_URL, which every deploy already
    # sets, and still resolves to http://localhost:8000 for local development.
    return f"{_app_base_url()}{_internal_mount_path()}"


def _app_base_url() -> str:
    # Derived from PYGEOAPI_SERVER_URL rather than a dedicated env var: that
    # variable is already set in app.template.yaml and all three CD workflows,
    # and a second base-URL variable would be a fourth place to get a deploy
    # wrong. PYGEOAPI_SERVER_URL points at the mount (".../ogcapi"), so strip
    # the mount path back off to recover the application root.
    server_url = _server_url()
    mount_path = _mount_path()
    if server_url.endswith(mount_path):
        return server_url[: -len(mount_path)].rstrip("/")
    # Deployment where the advertised OGC URL is not simply <root><mount>
    # (a rewriting proxy, say). Scheme + netloc is the best root available.
    parsed = urlparse(server_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return server_url.rstrip("/")


def _terms_of_service_url() -> str:
    return f"{_app_base_url()}/disclaimer"


def _pygeoapi_dir(
    runtime_dir_env: str = "PYGEOAPI_RUNTIME_DIR", default: str = "/tmp/pygeoapi"
) -> Path:
    # Use instance-local ephemeral storage by default (GAE-safe).
    runtime_dir = (os.environ.get(runtime_dir_env) or "").strip()
    path = Path(runtime_dir) if runtime_dir else Path(default)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _thing_collections_block(
    host: str,
    port: str,
    dbname: str,
    user: str,
    password_placeholder: str,
    table_prefix: str = "ogc_",
    include_internal_only: bool = False,
) -> str:
    resources: dict[str, dict] = {}
    for collection in THING_COLLECTIONS:
        if collection.get("internal_only") and not include_internal_only:
            continue
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
                    "name": "core.feature_provider.DescribedPostgreSQLProvider",
                    "data": {
                        "host": host,
                        "port": port,
                        "dbname": dbname,
                        "user": user,
                        "password": password_placeholder,
                        "search_path": ["public"],
                    },
                    "id_field": "id",
                    "table": f"{table_prefix}{collection['id']}",
                    "geom_field": "point",
                    "time_field": "first_visit_date",
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


def _edr_collections_block(
    host: str,
    port: str,
    dbname: str,
    user: str,
    password_placeholder: str,
    table_prefix: str = "ogc_",
) -> str:
    resources: dict[str, dict] = {}
    for collection in EDR_COLLECTIONS:
        # EDR_COLLECTIONS' table values are hardcoded to the public
        # ogc_waterlevels/ogc_water_chemistry names -- strip that literal
        # "ogc_" so table_prefix (here, "ogc_internal_" for the internal
        # mount) still applies, the same way _thing_collections_block does.
        table_name = table_prefix + collection["table"].removeprefix("ogc_")
        provider = {
            "type": "edr",
            "name": "core.edr_provider.WaterEDRProvider",
            "data": {
                "host": host,
                "port": port,
                "dbname": dbname,
                "user": user,
                "password": password_placeholder,
            },
            "id_field": "id",
            "table": table_name,
        }
        if collection["instance_field"]:
            provider["instance_field"] = collection["instance_field"]

        resources[collection["id"]] = {
            "type": "collection",
            "title": collection["title"],
            "description": collection["description"],
            "keywords": collection["keywords"],
            "extents": {
                "spatial": {
                    "bbox": [-109.05, 31.33, -103.00, 37.00],
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                },
                "temporal": {"begin": None, "end": None},
            },
            "providers": [provider],
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
            "PYGEOAPI_POSTGRES_USER or POSTGRES_USER must be set and "
            "non-empty to generate the pygeoapi configuration."
        )
    if os.environ.get("PYGEOAPI_POSTGRES_PASSWORD") is None:
        raise RuntimeError(
            "PYGEOAPI_POSTGRES_PASSWORD must be set to "
            "generate the pygeoapi configuration."
        )
    return host, port, dbname, user, "${PYGEOAPI_POSTGRES_PASSWORD}"


def _write_config(
    path: Path,
    *,
    server_url: str,
    table_prefix: str = "ogc_",
    template_path: Path | None = None,
    include_edr: bool = False,
    include_internal_only: bool = False,
) -> None:
    host, port, dbname, user, password_placeholder = _pygeoapi_db_settings()
    template = (template_path or _template_path()).read_text(encoding="utf-8")
    thing_collections_block = _thing_collections_block(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password_placeholder=password_placeholder,
        table_prefix=table_prefix,
        include_internal_only=include_internal_only,
    )
    if include_edr:
        # EDR collections (core/edr_provider.py), backed by
        # ogc_waterlevels/ogc_water_chemistry (public) or
        # ogc_internal_waterlevels/ogc_internal_water_chemistry (internal,
        # see 2d3c3a268652_create_internal_ogc_views.py) depending on
        # table_prefix.
        thing_collections_block = "\n".join(
            [
                thing_collections_block,
                _edr_collections_block(
                    host=host,
                    port=port,
                    dbname=dbname,
                    user=user,
                    password_placeholder=password_placeholder,
                    table_prefix=table_prefix,
                ),
            ]
        )
    config = template.format(
        server_url=server_url,
        terms_of_service_url=_terms_of_service_url(),
        postgres_host=host,
        postgres_port=port,
        postgres_db=dbname,
        postgres_user=user,
        postgres_password_env=password_placeholder,
        thing_collections_block=thing_collections_block,
    )
    # NOTE: The generated runtime config file (default:
    # `/tmp/pygeoapi/pygeoapi-config.yml` or
    # `/tmp/pygeoapi-internal/pygeoapi-config.yml`) contains database
    # connection details (host, port, dbname, user). Although the password is
    # expected to be provided via environment variables at runtime by
    # pygeoapi, this file should still be treated as sensitive configuration:
    #   * Do not commit it to version control.
    #   * Do not expose it in logs, error messages, or diagnostics.
    #   * Ensure filesystem permissions restrict access appropriately.
    path.write_text(config, encoding="utf-8")
    path.chmod(0o600)


def _assert_server_settings_match(
    public_config_path: Path, internal_config_path: Path
) -> None:
    # pygeoapi.api.API.__init__ mutates process-wide, module-level globals
    # (CHARSET, FORMAT_TYPES). Loading each mount from its own copy of
    # pygeoapi.starlette_app does not help here, since both copies still
    # share the one pygeoapi.api module -- whichever mount is constructed
    # last wins for both.
    # Inert as long as both configs agree on these settings; fail loudly at
    # startup rather than let a future divergence silently corrupt responses
    # on whichever mount lost the race.
    public_server = yaml.safe_load(public_config_path.read_text(encoding="utf-8")).get(
        "server", {}
    )
    internal_server = yaml.safe_load(
        internal_config_path.read_text(encoding="utf-8")
    ).get("server", {})
    for key in ("encoding", "gzip"):
        if public_server.get(key) != internal_server.get(key):
            raise RuntimeError(
                "pygeoapi public/internal config drift detected: "
                f"server.{key} differs ({public_server.get(key)!r} vs "
                f"{internal_server.get(key)!r}). Both configs must agree "
                "here since pygeoapi.api.API.__init__ mutates shared "
                "process-wide globals from these settings."
            )


def _generate_openapi(config_path: Path, openapi_path: Path) -> None:
    from pygeoapi.openapi import generate_openapi_document

    # Avoid startup failures when backing tables are not yet present; pygeoapi
    # will skip invalid collections and still emit a standards-compliant spec.
    openapi = generate_openapi_document(
        config_path, "yaml", fail_on_invalid_collection=False
    )
    openapi_path.write_text(openapi, encoding="utf-8")


def _load_pygeoapi_app(instance: str, config_path: Path, openapi_path: Path):
    # pygeoapi.starlette_app resolves PYGEOAPI_CONFIG at import time into a
    # module-level `api_`, and every route handler looks that name up in the
    # module's globals at request time. importlib.reload() rebinds those
    # globals *in place*, so reloading for the second mount retargets the
    # handlers of the app already built for the first one -- both mounts end
    # up serving whichever config was loaded last. Give each mount its own
    # module object so the two sets of globals can never alias.
    module_name = "pygeoapi.starlette_app"
    spec = find_spec(module_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to locate {module_name} for the {instance} mount.")

    module = importlib.util.module_from_spec(spec)
    # Registered before exec_module so the module can survive importing itself.
    sys.modules[f"{module_name}__ocotillo_{instance}"] = module

    previous = {key: os.environ.get(key) for key in _PYGEOAPI_ENV_KEYS}
    os.environ["PYGEOAPI_CONFIG"] = str(config_path)
    os.environ["PYGEOAPI_OPENAPI"] = str(openapi_path)
    try:
        spec.loader.exec_module(module)
    finally:
        # These are read only during import, so leaving the last mount's paths
        # behind would silently decide the config for any later importer.
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return module.APP


def mount_pygeoapi(app: FastAPI) -> None:
    if getattr(app.state, "pygeoapi_mounted", False):
        return
    if find_spec("pygeoapi") is None:
        raise RuntimeError(
            "pygeoapi is not installed. Rebuild/sync dependencies so "
            "/ogcapi can be mounted."
        )

    pygeoapi_dir = _pygeoapi_dir()
    config_path = pygeoapi_dir / "pygeoapi-config.yml"
    openapi_path = pygeoapi_dir / "pygeoapi-openapi.yml"
    _write_config(config_path, server_url=_server_url(), include_edr=True)
    _generate_openapi(config_path, openapi_path)

    pygeoapi_app = _load_pygeoapi_app("public", config_path, openapi_path)
    mount_path = _mount_path()
    app.mount(mount_path, pygeoapi_app)

    app.state.pygeoapi_mounted = True


def mount_pygeoapi_internal(app: FastAPI) -> None:
    if getattr(app.state, "pygeoapi_internal_mounted", False):
        return
    if find_spec("pygeoapi") is None:
        raise RuntimeError(
            "pygeoapi is not installed. Rebuild/sync dependencies so "
            "/ogcapi-internal can be mounted."
        )

    public_mount_path = _mount_path()
    internal_mount_path = _internal_mount_path()
    if internal_mount_path == public_mount_path:
        # Starlette doesn't error on duplicate mount paths -- it registers
        # both Mounts and matches whichever was registered first (the
        # public mount), leaving the internal mount silently unreachable.
        # Fail loudly at startup instead of that way blind.
        raise RuntimeError(
            "PYGEOAPI_MOUNT_PATH and PYGEOAPI_INTERNAL_MOUNT_PATH both "
            f"resolve to {internal_mount_path!r}. They must be distinct."
        )

    internal_dir = _pygeoapi_dir(
        "PYGEOAPI_INTERNAL_RUNTIME_DIR", "/tmp/pygeoapi-internal"
    )
    config_path = internal_dir / "pygeoapi-config.yml"
    openapi_path = internal_dir / "pygeoapi-openapi.yml"
    _write_config(
        config_path,
        server_url=_internal_server_url(),
        table_prefix="ogc_internal_",
        template_path=_internal_template_path(),
        include_edr=True,
        include_internal_only=True,
    )
    _generate_openapi(config_path, openapi_path)
    _assert_server_settings_match(_pygeoapi_dir() / "pygeoapi-config.yml", config_path)

    pygeoapi_app = _load_pygeoapi_app("internal", config_path, openapi_path)

    from core.internal_ogc_auth import InternalOGCAuthMiddleware

    app.add_middleware(InternalOGCAuthMiddleware, mount_path=internal_mount_path)
    app.mount(internal_mount_path, pygeoapi_app)

    app.state.pygeoapi_internal_mounted = True
