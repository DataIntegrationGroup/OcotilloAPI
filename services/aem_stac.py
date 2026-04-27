# flake8: noqa: E501
"""STAC document generation and pgstac loading helpers for AEM ingest."""

from __future__ import annotations

import json
import logging
import math
import os
import pandas as pd
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timezone
from pathlib import Path
from google.cloud import storage
from schemas.aem import SURVEY_METADATA, IngestConfig
from services.aem_parsers.common import TEMPORAL_DATETIME_COLUMNS
from services.util import transform_srid
from shapely.geometry import MultiPoint, Point, box, mapping
from urllib.parse import quote, quote_plus, urlencode

logger = logging.getLogger(__name__)

RAW_EASTING_COLUMNS = [
    "utmx",
    "utm_x",
    "utm_easting",
    "easting",
    "x",
]
RAW_NORTHING_COLUMNS = [
    "utmy",
    "utm_y",
    "utm_northing",
    "northing",
    "y",
]
RAW_LINE_COLUMNS = ["Line", "line", "line_no", "lineid", "line_id"]


def _round_bbox_outward(bounds: tuple[float, float, float, float]) -> list[float]:
    scale = 10**6
    minx, miny, maxx, maxy = bounds
    return [
        math.floor(float(minx) * scale) / scale,
        math.floor(float(miny) * scale) / scale,
        math.ceil(float(maxx) * scale) / scale,
        math.ceil(float(maxy) * scale) / scale,
    ]


def _stac_date_only_or_none(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return (
            datetime.combine(value.date(), datetime.min.time(), tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    if isinstance(value, date):
        return (
            datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        text_value = str(value).strip()
        if not text_value:
            return None
        if "T" in text_value:
            text_value = text_value.split("T", 1)[0]
        return f"{text_value}T00:00:00Z"
    return (
        datetime.combine(parsed.date(), datetime.min.time(), tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


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

    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().isoformat().replace("+00:00", "Z")


def _coerce_time_value(value) -> time | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.timetz().replace(tzinfo=None)
    if isinstance(value, time):
        return value.replace(tzinfo=None)

    text = str(value).strip()
    if not text:
        return None
    if ":" in text:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().time().replace(tzinfo=None)

    match = re.fullmatch(r"(\d+)(?:\.(\d+))?", text)
    if match is None:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime().time().replace(tzinfo=None)

    try:
        seconds_of_day = float(text)
    except ValueError:
        return None
    if seconds_of_day < 0 or seconds_of_day >= 86400:
        return None

    whole_seconds = int(seconds_of_day)
    fractional_microsecond = int(round((seconds_of_day - whole_seconds) * 1_000_000))
    if fractional_microsecond == 1_000_000:
        whole_seconds += 1
        fractional_microsecond = 0
    if whole_seconds >= 86400:
        return None
    hour, remainder = divmod(whole_seconds, 3600)
    minute, second = divmod(remainder, 60)
    return time(hour, minute, second, fractional_microsecond)


def _stac_datetime_from_date_and_time_or_none(
    date_value,
    time_value,
    require_time: bool = False,
) -> str | None:
    if date_value is None or pd.isna(date_value):
        return None
    parsed_date = pd.to_datetime(date_value, errors="coerce")
    if pd.isna(parsed_date):
        return None

    parsed_time = _coerce_time_value(time_value)
    if parsed_time is None:
        if require_time:
            return None
        combined = datetime.combine(
            parsed_date.date(), datetime.min.time(), tzinfo=timezone.utc
        )
    else:
        combined = datetime.combine(
            parsed_date.date(), parsed_time, tzinfo=timezone.utc
        )
    return combined.isoformat().replace("+00:00", "Z")


def _stac_datetimes_from_frame(df: pd.DataFrame) -> list[str]:
    for col in TEMPORAL_DATETIME_COLUMNS:
        if col not in df.columns:
            continue
        values = [_stac_date_only_or_none(value) for value in df[col]]
        cleaned = sorted({value for value in values if value is not None})
        if cleaned:
            return cleaned

    if "date_acquired" not in df.columns:
        return []

    values = [_stac_date_only_or_none(value) for value in df["date_acquired"]]
    return sorted({value for value in values if value is not None})


def _raw_stac_datetimes_from_frame(df: pd.DataFrame) -> list[str]:
    if "acquisition_datetime" in df.columns:
        values = [_stac_datetime_or_none(value) for value in df["acquisition_datetime"]]
        cleaned = sorted({value for value in values if value is not None})
        if cleaned:
            return cleaned

    if "Date" in df.columns:
        time_col = None
        for candidate in ["GTime", "Time", "time", "acquisition_time"]:
            if candidate in df.columns:
                time_col = candidate
                break
        if time_col is not None:
            values = [
                _stac_datetime_from_date_and_time_or_none(
                    date_value, time_value, require_time=True
                )
                for date_value, time_value in zip(
                    df["Date"], df[time_col], strict=False
                )
            ]
            cleaned = sorted({value for value in values if value is not None})
            if cleaned:
                return cleaned
    return _stac_datetimes_from_frame(df)


def _gcs_href(bucket: str, path: str) -> str:
    return (
        f"https://storage.googleapis.com/{bucket}/{quote(path.lstrip('/'), safe='/')}"
    )


def _stac_asset_key(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return normalized or "asset"


def _build_raw_data_assets(
    bucket: str,
    raw_file_paths: list[dict] | None,
) -> dict[str, dict]:
    if not raw_file_paths:
        return {}

    assets: dict[str, dict] = {}
    used_keys: set[str] = set()
    for raw_file in raw_file_paths:
        gcs_path = raw_file.get("gcs_path")
        filename = raw_file.get("file") or gcs_path
        if not gcs_path or not filename:
            continue

        base_key = f"raw_{_stac_asset_key(str(filename).rsplit('.', 1)[0])}"
        key = base_key
        suffix = 2
        while key in used_keys:
            key = f"{base_key}_{suffix}"
            suffix += 1
        used_keys.add(key)

        asset = {
            "href": _gcs_href(bucket, gcs_path),
            "roles": ["data"],
            "title": f"Raw acquisition file: {filename}",
        }
        if str(filename).lower().endswith(".csv"):
            asset["type"] = "text/csv"
        flight_id = raw_file.get("flight_id")
        if flight_id:
            asset["ocotillo:flight_id"] = flight_id
        assets[key] = asset

    return assets


def _get_env_or_none(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _build_geoserver_endpoint(
    public_url: str,
    default_path: str,
    override_env_name: str,
) -> str:
    def _join_url_path(base_url: str, path: str) -> str:
        normalized_base = base_url.rstrip("/")
        normalized_path = f"/{path.lstrip('/')}"
        if normalized_base.endswith(normalized_path):
            return normalized_base
        base_parts = normalized_base.split("/")
        path_parts = normalized_path.lstrip("/").split("/")
        overlap = 0
        max_overlap = min(len(base_parts), len(path_parts))
        for size in range(max_overlap, 0, -1):
            if base_parts[-size:] == path_parts[:size]:
                overlap = size
                break
        if overlap:
            suffix = "/".join(path_parts[overlap:])
            return normalized_base if not suffix else f"{normalized_base}/{suffix}"
        return f"{normalized_base}{normalized_path}"

    override = _get_env_or_none(override_env_name)
    if override is None:
        return _join_url_path(public_url, default_path)
    if override.startswith("http://") or override.startswith("https://"):
        return override
    return _join_url_path(public_url, override)


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


def _wgs84_points_from_dataframe(df: pd.DataFrame) -> list[Point]:
    if df.empty or "easting" not in df.columns or "northing" not in df.columns:
        return []

    coords = df[["easting", "northing", "source_epsg"]].dropna()
    if coords.empty:
        return []

    source_srids = coords["source_epsg"].astype(int).unique().tolist()
    if len(source_srids) != 1:
        raise ValueError(
            f"Expected one source_epsg for STAC handoff, got {source_srids}"
        )

    unique_points = (
        coords[["easting", "northing"]]
        .drop_duplicates()
        .sort_values(["easting", "northing"])
    )
    return [
        transform_srid(
            Point(float(row.easting), float(row.northing)),
            source_srids[0],
            4326,
        )
        for row in unique_points.itertuples(index=False)
    ]


def _wgs84_bbox_from_dataframe(df: pd.DataFrame) -> list[float] | None:
    wgs84_points = _wgs84_points_from_dataframe(df)
    if not wgs84_points:
        return None

    return _round_bbox_outward(MultiPoint(wgs84_points).bounds)


def _wgs84_geometry_from_dataframe(df: pd.DataFrame) -> dict | None:
    wgs84_points = _wgs84_points_from_dataframe(df)
    if not wgs84_points:
        return None

    if len(wgs84_points) == 1:
        geometry = wgs84_points[0]
    else:
        geometry = MultiPoint(wgs84_points).convex_hull
    return mapping(geometry)


def _stac_temporal_extent(
    df: pd.DataFrame,
    config: IngestConfig,
) -> tuple[str, str]:
    temporal_values = _stac_datetimes_from_frame(df)
    if not temporal_values:
        fallback = _fallback_stac_datetime(config)
        return fallback, fallback
    return temporal_values[0], temporal_values[-1]


def _stac_temporal_extent_from_values(
    values: list[str],
    config: IngestConfig,
) -> tuple[str, str]:
    if not values:
        fallback = _fallback_stac_datetime(config)
        return fallback, fallback
    return values[0], values[-1]


def _stac_temporal_properties(
    df: pd.DataFrame,
    config: IngestConfig,
) -> dict[str, str]:
    start, end = _stac_temporal_extent(df, config)
    if start == end:
        return {"datetime": start}
    return {"start_datetime": start, "end_datetime": end}


def _raw_stac_temporal_extent(
    df: pd.DataFrame,
    config: IngestConfig,
) -> tuple[str, str]:
    return _stac_temporal_extent_from_values(_raw_stac_datetimes_from_frame(df), config)


def _stac_collection_id(config: IngestConfig, kind: str) -> str:
    if kind == "raw":
        return f"aem-{config.survey_id.lower()}-raw"
    if kind == "inversion":
        return (
            f"aem-{config.survey_id.lower()}-"
            f"{config.processing_stage.value}-{config.inversion_code.value}"
        )
    raise ValueError(f"Unsupported STAC collection kind: {kind}")


def _first_matching_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowered = {col.lower(): col for col in df.columns}
    for candidate in candidates:
        match = lowered.get(candidate.lower())
        if match is not None:
            return match
    return None


def build_raw_stac_dataframe(
    acquisition_file_paths: list[dict] | None,
    raw_file_paths: list[dict] | None,
    source_epsg: int,
) -> pd.DataFrame:
    """Build a normalized raw-point frame from acquisition CSVs for STAC output."""
    if not acquisition_file_paths:
        return pd.DataFrame()

    raw_gcs_by_file = {
        raw_file.get("file"): raw_file
        for raw_file in (raw_file_paths or [])
        if raw_file.get("file")
    }
    frames: list[pd.DataFrame] = []

    for raw_file in acquisition_file_paths:
        source_path = raw_file.get("source_path")
        if not source_path or not str(source_path).lower().endswith(".csv"):
            continue

        try:
            raw_df = pd.read_csv(source_path)
        except Exception as exc:
            logger.warning("Skipping raw STAC companion %s: %s", source_path, exc)
            continue

        easting_col = _first_matching_column(raw_df, RAW_EASTING_COLUMNS)
        northing_col = _first_matching_column(raw_df, RAW_NORTHING_COLUMNS)
        if easting_col is None or northing_col is None:
            logger.warning(
                "Skipping raw STAC companion %s because coordinate columns were not found",
                source_path,
            )
            continue

        frame = raw_df.copy()
        frame["_csv_row_number"] = frame.index + 2
        frame["easting"] = pd.to_numeric(frame[easting_col], errors="coerce")
        frame["northing"] = pd.to_numeric(frame[northing_col], errors="coerce")
        frame = frame.dropna(subset=["easting", "northing"])
        if frame.empty:
            continue

        line_col = _first_matching_column(frame, RAW_LINE_COLUMNS)
        if line_col is not None:
            frame["line_id"] = frame[line_col].astype(str)
        else:
            frame["line_id"] = None

        frame["source_epsg"] = source_epsg
        frame["raw_file"] = raw_file.get("file")
        frame["flight_id"] = raw_file.get("flight_id")
        frame["source_path"] = source_path
        gcs_meta = raw_gcs_by_file.get(raw_file.get("file"), {})
        frame["raw_gcs_path"] = gcs_meta.get("gcs_path")
        frame["raw_point_order"] = range(1, len(frame) + 1)

        time_col = _first_matching_column(
            frame, ["GTime", "Time", "time", "acquisition_time"]
        )
        if "Date" in frame.columns:
            frame["acquisition_datetime"] = [
                _stac_datetime_from_date_and_time_or_none(
                    date_value,
                    time_value,
                    require_time=time_col is not None,
                )
                for date_value, time_value in zip(
                    frame["Date"],
                    frame[time_col] if time_col is not None else [None] * len(frame),
                    strict=False,
                )
            ]
            frame["date_acquired"] = frame["Date"]
            if time_col is not None:
                unusable_time_mask = (
                    frame["Date"].notna() & frame["acquisition_datetime"].isna()
                )
                if unusable_time_mask.any():
                    unusable_rows = frame.loc[unusable_time_mask, "_csv_row_number"]
                    sample_rows = unusable_rows.head(10).astype(int).tolist()
                    logger.warning(
                        "Raw acquisition file %s has %d rows with unusable %s values; sample CSV rows: %s",
                        raw_file.get("file") or source_path,
                        int(unusable_time_mask.sum()),
                        time_col,
                        sample_rows,
                    )

        frames.append(
            frame[
                [
                    "easting",
                    "northing",
                    "source_epsg",
                    "line_id",
                    "raw_file",
                    "flight_id",
                    "source_path",
                    "raw_gcs_path",
                    "raw_point_order",
                    *(
                        ["acquisition_datetime", "date_acquired"]
                        if "acquisition_datetime" in frame.columns
                        else []
                    ),
                ]
            ]
        )

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def limit_stac_items_per_collection(
    items: Iterable[dict],
    max_items_per_collection: int,
    remaining_by_collection: dict[str, int] | None = None,
) -> list[dict]:
    """Return at most N items per collection, preserving input order."""
    counts: dict[str, int] = defaultdict(int)
    limited_items: list[dict] = []
    for item in items:
        collection_id = item["collection"]
        remaining = (
            remaining_by_collection.get(collection_id, max_items_per_collection)
            if remaining_by_collection is not None
            else max_items_per_collection
        )
        if remaining <= 0 or counts[collection_id] >= remaining:
            continue
        limited_items.append(item)
        counts[collection_id] += 1

    if remaining_by_collection is not None:
        for collection_id, count in counts.items():
            current_remaining = remaining_by_collection.get(
                collection_id, max_items_per_collection
            )
            remaining_by_collection[collection_id] = max(current_remaining - count, 0)
    return limited_items


def build_stac_collection(
    df: pd.DataFrame,
    config: IngestConfig,
    parquet_gcs_path: str,
    raw_manifest_gcs_path: str,
    raw_file_paths: list[dict] | None = None,
    kind: str = "inversion",
) -> dict:
    """Build a deterministic STAC Collection document."""
    survey_metadata = SURVEY_METADATA.get(config.survey_id)
    bbox = _wgs84_bbox_from_dataframe(df)
    geometry = _wgs84_geometry_from_dataframe(df)
    collection_id = _stac_collection_id(config, kind)
    providers = [{"name": config.contractor, "roles": ["producer"]}]
    if survey_metadata:
        providers.append(
            {
                "name": "New Mexico Bureau of Geology and Mineral Resources",
                "roles": ["host"],
            }
        )

    if kind == "raw":
        start, end = _raw_stac_temporal_extent(df, config)
        assets = {
            "raw_manifest": {
                "href": _gcs_href(config.gcs_bucket, raw_manifest_gcs_path),
                "type": "application/json",
                "roles": ["metadata"],
                "title": "Raw source file manifest",
            },
        }
        assets.update(_build_raw_data_assets(config.gcs_bucket, raw_file_paths))
        item_assets = None
        temporal_interval = [[start, end]]
        title_suffix = "Raw Acquisition"
        description = (
            f"Airborne electromagnetic raw acquisition metadata for {config.survey_id}"
        )
    elif kind == "inversion":
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
        assets.update(
            build_geoserver_collection_assets(
                f"aem-{config.survey_id.lower()}-{config.processing_stage.value}-{config.inversion_code.value}"
            )
        )
        item_assets = {
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
        }
        temporal_interval = [[None, None]]
        title_suffix = "Inversion"
        description = (
            f"Airborne electromagnetic inversion outputs for {config.survey_id} "
            f"({config.processing_stage.value}, {config.inversion_code.value})"
        )
    else:
        raise ValueError(f"Unsupported STAC collection kind: {kind}")

    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": collection_id,
        "title": f"AEM Survey {title_suffix}: {config.survey_id}",
        "description": description,
        "license": "proprietary",
        "extent": {
            "spatial": {"bbox": [bbox or [-180.0, -90.0, 180.0, 90.0]]},
            "temporal": {"interval": temporal_interval},
        },
        **(
            {"geometry": geometry}
            if kind == "inversion" and geometry is not None
            else {}
        ),
        "links": [],
        "providers": providers,
        "keywords": [
            "aem",
            "resistivity",
            config.survey_id,
            kind,
            *(
                [config.processing_stage.value, config.inversion_code.value]
                if kind == "inversion"
                else []
            ),
        ],
        "summaries": {
            "contractor": [config.contractor],
            "collection_kind": [kind],
            **(
                {
                    "processing_stage": [config.processing_stage.value],
                    "inversion_code": [config.inversion_code.value],
                }
                if kind == "inversion"
                else {}
            ),
        },
        **({"item_assets": item_assets} if item_assets is not None else {}),
        "assets": assets,
        "ocotillo:survey_id": config.survey_id,
        "ocotillo:collection_kind": kind,
        "ocotillo:contractor": config.contractor,
        **(
            {
                "ocotillo:processing_stage": config.processing_stage.value,
                "ocotillo:inversion_code": config.inversion_code.value,
            }
            if kind == "inversion"
            else {}
        ),
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
                "collection": _stac_collection_id(config, "inversion"),
                "geometry": geometry,
                "bbox": bbox,
                "links": [],
                "properties": {
                    **_stac_temporal_properties(group, config),
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


def build_raw_stac_items(
    raw_df: pd.DataFrame,
    config: IngestConfig,
    raw_manifest_gcs_path: str,
) -> list[dict]:
    """Build STAC Items for each raw acquisition point."""
    if raw_df.empty:
        return []

    source_srids = raw_df["source_epsg"].dropna().astype(int).unique().tolist()
    if len(source_srids) != 1:
        raise ValueError(
            f"Expected one source_epsg for raw STAC items, got {source_srids}"
        )

    items: list[dict] = []
    collection_id = _stac_collection_id(config, "raw")
    for row in raw_df.itertuples(index=False):
        geometry_point = transform_srid(
            Point(float(row.easting), float(row.northing)),
            source_srids[0],
            4326,
        )
        geometry = mapping(geometry_point)
        bbox = [round(float(value), 6) for value in geometry_point.bounds]
        file_stem = _stac_asset_key(Path(str(row.raw_file or "raw")).stem)
        item_id = f"aem-{config.survey_id}-raw-{file_stem}-{int(row.raw_point_order)}"
        datetime_value = getattr(row, "acquisition_datetime", None)
        if datetime_value is None:
            datetime_value = _stac_date_only_or_none(
                getattr(row, "date_acquired", None)
            )
        if datetime_value is None:
            datetime_value = _fallback_stac_datetime(config)

        assets = {
            "raw_manifest": {
                "href": _gcs_href(config.gcs_bucket, raw_manifest_gcs_path),
                "type": "application/json",
                "roles": ["metadata"],
                "title": "Raw source file manifest",
            }
        }
        if getattr(row, "raw_gcs_path", None):
            assets["source"] = {
                "href": _gcs_href(config.gcs_bucket, row.raw_gcs_path),
                "type": "text/csv",
                "roles": ["data", "metadata"],
                "title": f"Raw acquisition file: {row.raw_file}",
            }

        items.append(
            {
                "type": "Feature",
                "stac_version": "1.0.0",
                "stac_extensions": [],
                "id": item_id,
                "collection": collection_id,
                "geometry": geometry,
                "bbox": bbox,
                "links": [],
                "properties": {
                    "datetime": datetime_value,
                    "proj:epsg": source_srids[0],
                    "ocotillo:survey_id": config.survey_id,
                    "ocotillo:collection_kind": "raw",
                    "ocotillo:contractor": config.contractor,
                    "ocotillo:line_id": row.line_id,
                    "ocotillo:flight_id": row.flight_id,
                    "ocotillo:raw_file": row.raw_file,
                    "ocotillo:point_order": int(row.raw_point_order),
                },
                "assets": assets,
            }
        )

    return items


def write_stac_payloads(
    collections: Iterable[dict],
    items: Iterable[dict],
    config: IngestConfig,
    gcs_client: storage.Client,
    ensure_prefix_readmes: Callable[[str, storage.Client, list[str]], list[str]],
) -> dict[str, str | dict[str, str]]:
    """Write replayable STAC payloads to GCS."""
    collections = list(collections)
    prefix = f"surveys/{config.survey_id}/metadata/stac"
    collection_paths: dict[str, str] = {}
    for collection in collections:
        kind = collection["ocotillo:collection_kind"]
        collection_paths[kind] = f"{prefix}/{config.survey_id}_{kind}_collection.json"
    items_path = (
        f"{prefix}/{config.survey_id}_{config.processing_stage.value}_"
        f"{config.inversion_code.value}_items.ndjson"
    )
    item_lines = [json.dumps(item) for item in items]

    ensure_prefix_readmes(
        config.gcs_bucket,
        gcs_client,
        [*collection_paths.values(), items_path],
    )
    bucket = gcs_client.bucket(config.gcs_bucket)
    for collection in collections:
        collection_payload = dict(collection)
        collection_payload["generated_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        bucket.blob(
            collection_paths[collection["ocotillo:collection_kind"]]
        ).upload_from_string(
            json.dumps(collection_payload, indent=2),
            content_type="application/json",
        )
    bucket.blob(items_path).upload_from_string(
        "\n".join(item_lines) + ("\n" if item_lines else ""),
        content_type="application/x-ndjson",
    )
    logger.info(
        "STAC payloads uploaded to collections=%s and items=gs://%s/%s",
        {
            kind: f"gs://{config.gcs_bucket}/{path}"
            for kind, path in collection_paths.items()
        },
        config.gcs_bucket,
        items_path,
    )
    return {
        "collection_gcs_path": collection_paths.get("inversion"),
        "items_gcs_path": items_path,
        "collection_gcs_paths": collection_paths,
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


def _should_skip_pgstac_load_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "failed to detect the target database version" in message
        or "pgstac is not installed" in message
        or 'relation "pgstac.migrations" does not exist' in message
        or "relation 'pgstac.migrations' does not exist" in message
        or 'schema "pgstac" does not exist' in message
        or "schema 'pgstac' does not exist" in message
    )


def load_stac_to_pgstac(collections: Iterable[dict], items: Iterable[dict]) -> None:
    """Upsert STAC payloads into pgstac using pypgstac."""
    collections = list(collections)
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
        try:
            loader.load_collections(iter(collections), insert_mode=Methods.upsert)
            loader.load_items(
                iter(items),
                insert_mode=Methods.upsert,
                chunksize=1000,
            )
        except Exception as exc:
            if not _should_skip_pgstac_load_error(exc):
                raise
            logger.warning(
                "Skipping pgstac load because the target database is not initialized for pgstac: %s",
                exc,
            )
    finally:
        db.disconnect()
