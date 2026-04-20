# flake8: noqa: E501
"""STAC document generation and pgstac loading helpers for AEM ingest."""

from __future__ import annotations

import json
import logging
import os
import pandas as pd
import re
from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone
from google.cloud import storage
from schemas.aem import SURVEY_METADATA, IngestConfig
from services.util import transform_srid
from shapely.geometry import box, mapping
from urllib.parse import quote_plus, urlencode

logger = logging.getLogger(__name__)


def _stac_datetime_or_none(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return (
            datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    text_value = str(value)
    if "T" not in text_value:
        return f"{text_value}T00:00:00Z"
    if text_value.endswith("Z") or "+" in text_value[10:]:
        return text_value
    return f"{text_value}Z"


def _gcs_href(bucket: str, path: str) -> str:
    return f"gs://{bucket}/{path}"


def _get_env_or_none(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _build_geoserver_endpoint(
    public_url: str,
    default_path: str,
    override_env_name: str,
) -> str:
    override = _get_env_or_none(override_env_name)
    if override is None:
        return f"{public_url.rstrip('/')}{default_path}"
    if override.startswith("http://") or override.startswith("https://"):
        return override
    return f"{public_url.rstrip('/')}/{override.lstrip('/')}"


def _geoserver_layer_name(collection_id: str, workspace: str) -> str:
    return f"{workspace}:{collection_id}"


def build_geoserver_collection_assets(collection_id: str) -> dict[str, dict]:
    """Build survey-level GeoServer assets from environment configuration."""
    public_url = _get_env_or_none("GEOSERVER_PUBLIC_URL")
    workspace = _get_env_or_none("GEOSERVER_WORKSPACE")
    if public_url is None or workspace is None:
        return {}

    layer_name = _geoserver_layer_name(collection_id, workspace)
    wms_endpoint = _build_geoserver_endpoint(
        public_url, "/geoserver/ows", "GEOSERVER_WMS_PATH"
    )
    wfs_endpoint = _build_geoserver_endpoint(
        public_url, "/geoserver/ows", "GEOSERVER_WFS_PATH"
    )
    wcs_endpoint = _build_geoserver_endpoint(
        public_url, "/geoserver/ows", "GEOSERVER_WCS_PATH"
    )

    return {
        "wms": {
            "href": f"{wms_endpoint}?{urlencode({'service': 'WMS', 'version': '1.3.0', 'request': 'GetCapabilities'})}",
            "type": "application/xml",
            "roles": ["visual", "metadata"],
            "title": "GeoServer WMS service",
            "geoserver:service": "WMS",
            "geoserver:workspace": workspace,
            "geoserver:layer": layer_name,
            "geoserver:request": "GetCapabilities",
        },
        "wfs": {
            "href": f"{wfs_endpoint}?{urlencode({'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': layer_name, 'outputFormat': 'application/json'})}",
            "type": "application/geo+json",
            "roles": ["data", "metadata"],
            "title": "GeoServer WFS feature access",
            "geoserver:service": "WFS",
            "geoserver:workspace": workspace,
            "geoserver:layer": layer_name,
            "geoserver:request": "GetFeature",
        },
        "wcs": {
            "href": f"{wcs_endpoint}?{urlencode({'service': 'WCS', 'version': '2.0.1', 'request': 'DescribeCoverage', 'coverageId': layer_name})}",
            "type": "application/xml",
            "roles": ["data", "metadata"],
            "title": "GeoServer WCS coverage metadata",
            "geoserver:service": "WCS",
            "geoserver:workspace": workspace,
            "geoserver:layer": layer_name,
            "geoserver:request": "DescribeCoverage",
        },
    }


def _fallback_stac_datetime(config: IngestConfig) -> str:
    match = re.search(r"(\d{4})$", config.survey_id)
    if match is None:
        raise ValueError(
            "STAC items require a datetime. Provide date_acquired or use a "
            "survey_id that ends with a 4-digit year."
        )
    return f"{match.group(1)}-01-01T00:00:00Z"


def _wgs84_bbox_from_dataframe(df: pd.DataFrame) -> list[float] | None:
    if df.empty or "easting" not in df.columns or "northing" not in df.columns:
        return None

    coords = df[["easting", "northing", "source_epsg"]].dropna()
    if coords.empty:
        return None

    source_srids = coords["source_epsg"].astype(int).unique().tolist()
    if len(source_srids) != 1:
        raise ValueError(
            f"Expected one source_epsg for STAC handoff, got {source_srids}"
        )

    projected_bbox = box(
        float(coords["easting"].min()),
        float(coords["northing"].min()),
        float(coords["easting"].max()),
        float(coords["northing"].max()),
    )
    wgs84_bbox = transform_srid(projected_bbox, source_srids[0], 4326).bounds
    return [round(float(value), 6) for value in wgs84_bbox]


def _stac_temporal_extent(
    df: pd.DataFrame,
    config: IngestConfig,
) -> tuple[str, str]:
    temporal_values = (
        sorted(
            {
                _stac_datetime_or_none(value)
                for value in df.get("date_acquired", pd.Series())
            }
        )
        if "date_acquired" in df.columns
        else []
    )
    temporal_values = [value for value in temporal_values if value is not None]
    if not temporal_values:
        fallback = _fallback_stac_datetime(config)
        return fallback, fallback
    return temporal_values[0], temporal_values[-1]


def build_stac_collection(
    df: pd.DataFrame,
    config: IngestConfig,
    parquet_gcs_path: str,
    raw_manifest_gcs_path: str,
) -> dict:
    """Build a deterministic STAC Collection document."""
    survey_metadata = SURVEY_METADATA.get(config.survey_id)
    start, end = _stac_temporal_extent(df, config)
    bbox = _wgs84_bbox_from_dataframe(df)
    providers = [{"name": config.contractor, "roles": ["producer"]}]
    if survey_metadata:
        providers.append(
            {
                "name": "New Mexico Bureau of Geology and Mineral Resources",
                "roles": ["host"],
            }
        )

    assets = {
        "source": {
            "href": _gcs_href(config.gcs_bucket, config.source_gcs_path),
            "type": "text/csv",
            "roles": ["data", "metadata"],
            "title": "Canonical source inversion file",
        },
        "parquet": {
            "href": _gcs_href(config.gcs_bucket, parquet_gcs_path),
            "type": "application/x-parquet",
            "roles": ["data"],
            "title": "Canonical sounding parquet export",
        },
        "raw_manifest": {
            "href": _gcs_href(config.gcs_bucket, raw_manifest_gcs_path),
            "type": "application/json",
            "roles": ["metadata"],
            "title": "Raw source file manifest",
        },
    }
    assets.update(build_geoserver_collection_assets(f"aem-{config.survey_id.lower()}"))

    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": f"aem-{config.survey_id.lower()}",
        "title": f"AEM Survey: {config.survey_id}",
        "description": (
            f"Airborne electromagnetic survey {config.survey_id} "
            f"({config.processing_stage.value})"
        ),
        "license": "proprietary",
        "extent": {
            "spatial": {"bbox": [bbox or [-180.0, -90.0, 180.0, 90.0]]},
            "temporal": {"interval": [[start, end]]},
        },
        "links": [],
        "providers": providers,
        "keywords": [
            "aem",
            "resistivity",
            config.survey_id,
            config.processing_stage.value,
            config.inversion_code.value,
        ],
        "summaries": {
            "processing_stage": [config.processing_stage.value],
            "inversion_code": [config.inversion_code.value],
            "contractor": [config.contractor],
        },
        "item_assets": {
            "source": {
                "type": "text/csv",
                "roles": ["data", "metadata"],
            },
            "parquet": {
                "type": "application/x-parquet",
                "roles": ["data"],
            },
            "raw_manifest": {
                "type": "application/json",
                "roles": ["metadata"],
            },
        },
        "assets": assets,
        "ocotillo:survey_id": config.survey_id,
        "ocotillo:processing_stage": config.processing_stage.value,
        "ocotillo:inversion_code": config.inversion_code.value,
        "ocotillo:contractor": config.contractor,
        "ocotillo:survey_region": (
            survey_metadata.survey_region if survey_metadata else None
        ),
        "ocotillo:system": survey_metadata.system if survey_metadata else None,
        "ocotillo:line_spacing_m": (
            survey_metadata.line_spacing if survey_metadata else None
        ),
        "ocotillo:line_length_km": (
            survey_metadata.line_length if survey_metadata else None
        ),
    }


def build_stac_items(
    df: pd.DataFrame,
    config: IngestConfig,
    parquet_gcs_path: str,
    raw_manifest_gcs_path: str,
) -> list[dict]:
    """Build deterministic STAC Items for each unique sounding."""
    source_srids = (
        df["source_epsg"].dropna().astype(int).unique().tolist()
        if "source_epsg" in df.columns
        else []
    )
    if len(source_srids) != 1:
        raise ValueError(f"Expected one source_epsg for STAC items, got {source_srids}")

    survey_metadata = SURVEY_METADATA.get(config.survey_id)
    grouped = (
        df.dropna(subset=["line_id", "record_id", "easting", "northing"])
        .sort_values(
            ["line_id", "record_id"]
            + (["layer_no"] if "layer_no" in df.columns else [])
        )
        .groupby(["line_id", "record_id"], as_index=False, sort=True)
    )
    items: list[dict] = []

    for sounding in grouped:
        (line_id, record_id), group = sounding
        geometry_point = transform_srid(
            box(
                float(group["easting"].iloc[0]),
                float(group["northing"].iloc[0]),
                float(group["easting"].iloc[0]),
                float(group["northing"].iloc[0]),
            ).centroid,
            source_srids[0],
            4326,
        )
        geometry = mapping(geometry_point)
        bbox = [round(float(value), 6) for value in geometry_point.bounds]
        datetimes = [
            _stac_datetime_or_none(value)
            for value in group.get("date_acquired", pd.Series())
        ]
        datetimes = sorted({value for value in datetimes if value is not None})
        if datetimes:
            datetime_value = datetimes[0] if len(datetimes) == 1 else None
            start_datetime = datetimes[0]
            end_datetime = datetimes[-1]
            estimated_datetime = False
        else:
            fallback = _fallback_stac_datetime(config)
            datetime_value = fallback
            start_datetime = fallback
            end_datetime = fallback
            estimated_datetime = True
        item_id = (
            "aem-"
            f"{config.survey_id}-{config.processing_stage.value}-"
            f"{line_id}-{record_id}"
        )
        items.append(
            {
                "type": "Feature",
                "stac_version": "1.0.0",
                "stac_extensions": [],
                "id": item_id,
                "collection": f"aem-{config.survey_id.lower()}",
                "geometry": geometry,
                "bbox": bbox,
                "links": [],
                "properties": {
                    "datetime": datetime_value,
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "proj:epsg": source_srids[0],
                    "ocotillo:survey_id": config.survey_id,
                    "ocotillo:processing_stage": config.processing_stage.value,
                    "ocotillo:inversion_code": config.inversion_code.value,
                    "ocotillo:contractor": config.contractor,
                    "ocotillo:line_id": line_id,
                    "ocotillo:record_id": record_id,
                    "ocotillo:num_layers": (
                        int(group["layer_no"].count())
                        if "layer_no" in group
                        else int(len(group))
                    ),
                    "ocotillo:max_depth_m": (
                        float(group["depth_bot"].max())
                        if "depth_bot" in group and group["depth_bot"].notna().any()
                        else None
                    ),
                    "ocotillo:datetime_estimated": estimated_datetime,
                    "ocotillo:survey_region": (
                        survey_metadata.survey_region if survey_metadata else None
                    ),
                    "ocotillo:system": (
                        survey_metadata.system if survey_metadata else None
                    ),
                },
                "assets": {
                    "source": {
                        "href": _gcs_href(config.gcs_bucket, config.source_gcs_path),
                        "type": "text/csv",
                        "roles": ["data", "metadata"],
                        "title": "Source inversion file",
                    },
                    "parquet": {
                        "href": _gcs_href(config.gcs_bucket, parquet_gcs_path),
                        "type": "application/x-parquet",
                        "roles": ["data"],
                        "title": "Sounding parquet export",
                    },
                    "raw_manifest": {
                        "href": _gcs_href(config.gcs_bucket, raw_manifest_gcs_path),
                        "type": "application/json",
                        "roles": ["metadata"],
                        "title": "Raw source file manifest",
                    },
                },
            }
        )

    return items


def write_stac_payloads(
    collection: dict,
    items: Iterable[dict],
    config: IngestConfig,
    gcs_client: storage.Client,
    ensure_prefix_readmes: Callable[[str, storage.Client, list[str]], list[str]],
) -> dict[str, str]:
    """Write replayable STAC payloads to GCS."""
    prefix = f"surveys/{config.survey_id}/metadata/stac"
    collection_path = (
        f"{prefix}/{config.survey_id}_{config.processing_stage.value}_"
        f"{config.inversion_code.value}_collection.json"
    )
    items_path = (
        f"{prefix}/{config.survey_id}_{config.processing_stage.value}_"
        f"{config.inversion_code.value}_items.ndjson"
    )
    collection_payload = dict(collection)
    collection_payload["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    item_lines = [json.dumps(item) for item in items]

    ensure_prefix_readmes(config.gcs_bucket, gcs_client, [collection_path, items_path])
    bucket = gcs_client.bucket(config.gcs_bucket)
    bucket.blob(collection_path).upload_from_string(
        json.dumps(collection_payload, indent=2),
        content_type="application/json",
    )
    bucket.blob(items_path).upload_from_string(
        "\n".join(item_lines) + ("\n" if item_lines else ""),
        content_type="application/x-ndjson",
    )
    logger.info(
        "STAC payloads uploaded to gs://%s/%s and gs://%s/%s",
        config.gcs_bucket,
        collection_path,
        config.gcs_bucket,
        items_path,
    )
    return {
        "collection_gcs_path": collection_path,
        "items_gcs_path": items_path,
    }


def _build_pgstac_dsn() -> str:
    explicit_dsn = os.environ.get("PGSTAC_DSN", "").strip()
    if explicit_dsn:
        return explicit_dsn

    user = (os.environ.get("POSTGRES_USER") or "").strip()
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = (os.environ.get("POSTGRES_HOST") or "localhost").strip()
    port = (os.environ.get("POSTGRES_PORT") or "5432").strip()
    database = (os.environ.get("POSTGRES_DB") or "postgres").strip()

    auth = quote_plus(user)
    if password:
        auth = f"{auth}:{quote_plus(password)}"
    return f"postgresql://{auth}@{host}:{port}/{database}"


def _import_pypgstac():
    from pypgstac.db import PgstacDB
    from pypgstac.load import Loader, Methods

    return PgstacDB, Loader, Methods


def load_stac_to_pgstac(collection: dict, items: Iterable[dict]) -> None:
    """Upsert STAC payloads into pgstac using pypgstac."""
    try:
        PgstacDB, Loader, Methods = _import_pypgstac()
    except ImportError as exc:
        raise RuntimeError(
            "pypgstac is required for CLI AEM ingest runs. "
            "Install the project with the `cli` extra."
        ) from exc

    db = PgstacDB(dsn=_build_pgstac_dsn())
    loader = Loader(db)
    try:
        loader.load_collections(iter([collection]), insert_mode=Methods.upsert)
        loader.load_items(
            iter(items),
            insert_mode=Methods.upsert,
            chunksize=1000,
        )
    finally:
        db.disconnect()
