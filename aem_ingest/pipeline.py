"""
aem_ingest.pipeline — Orchestrates the full ingest pipeline.

Architecture note: the GCS mapper (aem_gcs_mapper.py) is the single source
of truth for where every file lives in GCS.  This pipeline does NOT decide
GCS paths — it receives the mapper's proposed_gcs_path via config.source_gcs_path
and records it in the PostGIS source_file column and in the STAC asset link.

Steps per file:
  1. Validate config (Pydantic, including mapper-provided source_gcs_path)
  2. Detect format
  3. Parse to canonical long-format DataFrame
  4. Load into PostGIS (aem_soundings + aem_sounding_metadata)
  5. Write Parquet to GCS
  6. Write raw file manifest to GCS
  7. Build and return STAC item (queries PostGIS for bbox/geometry/stats)
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage
from shapely.geometry import MultiPoint, mapping

from aem_ingest.db import get_raw_connection, get_engine
from aem_ingest.models import AemSounding, AemSoundingMetadata
from aem_ingest.parsers import detect_format, parse_agf_lci, parse_bylayer, parse_seogi_rho
from aem_ingest.parsers.common import CANONICAL_COLUMNS, TARGET_EPSG
from aem_ingest.schemas import IngestConfig, SourceFormat, SURVEY_METADATA

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PostGIS loading
# ---------------------------------------------------------------------------

INSERT_COLUMNS = [
    "survey_id", "processing_stage", "inversion_code", "contractor",
    "source_file", "source_epsg", "line_id", "record_id", "layer_no",
    "easting_m", "northing_m", "longitude_dd", "latitude_dd",
    "elevation_m", "sensor_alt_m", "terrain_clear_m",
    "depth_top_m", "depth_bot_m", "thickness_m",
    "resistivity_ohmm", "resistivity_std", "conductivity_sm",
    "doi_conservative_m", "doi_standard_m",
    "resdata", "restotal", "plni", "date_acquired",
]

REQUIRED_COLUMNS = [
    "line_id", "layer_no", "easting_m", "northing_m",
    "depth_top_m", "depth_bot_m", "resistivity_ohmm",
]


def load_to_postgis(
    df: pd.DataFrame,
    config: IngestConfig,
) -> int:
    """Bulk-insert normalized DataFrame into aem_soundings and
    aem_sounding_metadata.

    Uses a staging-table approach:
      1. COPY into a temp table via psycopg2's copy_expert (fast bulk load)
      2. INSERT INTO aem_soundings with ST_Transform(ST_GeomFromEWKT(...))
      3. Aggregate and upsert into aem_sounding_metadata

    The source_file column stores the mapper's GCS path (config.source_gcs_path).

    Returns:
        Number of rows inserted into aem_soundings.
    """
    logger.info(
        "Loading to PostGIS: survey=%s, stage=%s, %d rows",
        config.survey_id, config.processing_stage.value, len(df),
    )

    df = df.copy()
    df["survey_id"] = config.survey_id
    df["processing_stage"] = config.processing_stage.value
    df["inversion_code"] = config.inversion_code.value
    df["contractor"] = config.contractor
    df["source_file"] = config.source_gcs_path

    df["geom_wkt"] = (
        "SRID=" + df["source_epsg"].astype(int).astype(str)
        + ";POINT(" + df["easting_m"].astype(str)
        + " " + df["northing_m"].astype(str) + ")"
    )

    pre_count = len(df)
    mask = df[REQUIRED_COLUMNS].notna().all(axis=1)
    df = df[mask]
    dropped = pre_count - len(df)
    if dropped > 0:
        logger.warning("Dropped %d rows with NULLs in required columns", dropped)

    raw_conn = get_raw_connection(config.db_conn_string)
    cur = raw_conn.cursor()

    try:
        cur.execute("""
            CREATE TEMP TABLE _ingest_staging (
                survey_id TEXT, processing_stage TEXT, inversion_code TEXT,
                contractor TEXT, source_file TEXT, source_epsg INTEGER,
                line_id TEXT, record_id TEXT, layer_no SMALLINT,
                easting_m DOUBLE PRECISION, northing_m DOUBLE PRECISION,
                longitude_dd DOUBLE PRECISION, latitude_dd DOUBLE PRECISION,
                elevation_m DOUBLE PRECISION, sensor_alt_m DOUBLE PRECISION,
                terrain_clear_m DOUBLE PRECISION,
                depth_top_m DOUBLE PRECISION, depth_bot_m DOUBLE PRECISION,
                thickness_m DOUBLE PRECISION,
                resistivity_ohmm DOUBLE PRECISION, resistivity_std DOUBLE PRECISION,
                conductivity_sm DOUBLE PRECISION,
                doi_conservative_m DOUBLE PRECISION, doi_standard_m DOUBLE PRECISION,
                resdata DOUBLE PRECISION, restotal DOUBLE PRECISION,
                plni DOUBLE PRECISION, date_acquired DATE,
                geom_wkt TEXT
            ) ON COMMIT DROP;
        """)

        staging_cols = INSERT_COLUMNS + ["geom_wkt"]
        buf = io.StringIO()
        df[staging_cols].to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)

        copy_sql = (
            f"COPY _ingest_staging ({', '.join(staging_cols)}) "
            f"FROM STDIN WITH (FORMAT csv, NULL '\\N')"
        )
        cur.copy_expert(copy_sql, buf)
        logger.info("COPY to staging: %d rows", len(df))

        cur.execute(f"""
            INSERT INTO aem_soundings (
                {', '.join(INSERT_COLUMNS)}, geom
            )
            SELECT
                {', '.join(INSERT_COLUMNS)},
                ST_Transform(ST_GeomFromEWKT(geom_wkt), {TARGET_EPSG})
            FROM _ingest_staging;
        """)
        sounding_rows = cur.rowcount
        logger.info("Inserted %d rows into aem_soundings", sounding_rows)

        _insert_metadata(
            cur, config.survey_id, config.processing_stage.value,
            config.inversion_code.value, df,
        )

        raw_conn.commit()
        logger.info("PostGIS load committed successfully")
        return sounding_rows

    except Exception:
        raw_conn.rollback()
        logger.exception("PostGIS load failed, transaction rolled back")
        raise
    finally:
        cur.close()
        raw_conn.close()


def _insert_metadata(
    cur, survey_id: str, processing_stage: str, inversion_code: str,
    df: pd.DataFrame,
) -> None:
    """Aggregate sounding-level summaries and upsert into aem_sounding_metadata."""
    group_cols = ["line_id", "record_id"]
    meta = df.groupby(group_cols, as_index=False).agg(
        easting_m=("easting_m", "first"),
        northing_m=("northing_m", "first"),
        num_layers=("layer_no", "count"),
        max_depth_m=("depth_bot_m", "min"),
        has_uncertainty=("resistivity_std", lambda x: x.notna().any()),
        has_doi=("doi_conservative_m", lambda x: x.notna().any()),
        source_epsg=("source_epsg", "first"),
    )

    meta["survey_id"] = survey_id
    meta["processing_stage"] = processing_stage
    meta["inversion_code"] = inversion_code

    if "_flight_id" in df.columns:
        meta["flight_id"] = df.groupby(group_cols)["_flight_id"].first().values
    else:
        meta["flight_id"] = None

    meta["date_acquired"] = None
    meta["num_layers"] = meta["num_layers"].astype("Int16")

    for _, row in meta.iterrows():
        cur.execute(
            """
            INSERT INTO aem_sounding_metadata (
                survey_id, line_id, record_id, processing_stage,
                geom, easting_m, northing_m,
                flight_id, date_acquired, num_layers, max_depth_m,
                has_uncertainty, has_doi, inversion_code, source_epsg
            ) VALUES (
                %s, %s, %s, %s,
                ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), %s), %s),
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (survey_id, line_id, record_id, processing_stage)
            DO UPDATE SET
                num_layers = EXCLUDED.num_layers,
                max_depth_m = EXCLUDED.max_depth_m,
                has_uncertainty = EXCLUDED.has_uncertainty,
                has_doi = EXCLUDED.has_doi
            """,
            (
                row["survey_id"], row["line_id"], row["record_id"],
                row["processing_stage"],
                row["easting_m"], row["northing_m"],
                int(row["source_epsg"]), TARGET_EPSG,
                row["easting_m"], row["northing_m"],
                row.get("flight_id"), row.get("date_acquired"),
                int(row["num_layers"]) if pd.notna(row["num_layers"]) else None,
                float(row["max_depth_m"]) if pd.notna(row["max_depth_m"]) else None,
                bool(row["has_uncertainty"]), bool(row["has_doi"]),
                row["inversion_code"],
                int(row["source_epsg"]),
            ),
        )

    logger.info("Inserted/updated %d rows in aem_sounding_metadata", len(meta))


# ---------------------------------------------------------------------------
# Parquet output
# ---------------------------------------------------------------------------


def write_parquet(
    df: pd.DataFrame,
    config: IngestConfig,
    gcs_client: storage.Client,
) -> str:
    """Write canonical DataFrame to Parquet and upload to GCS.

    Returns:
        GCS path of the uploaded Parquet file.
    """
    stage_short = config.processing_stage.value.replace("_inversion", "")
    gcs_path = (
        f"surveys/{config.survey_id}/aem/inversion/{stage_short}"
        f"/parquet/{config.survey_id}_{config.processing_stage.value}.parquet"
    )

    logger.info("Writing Parquet: %s", gcs_path)

    out_cols = [c for c in CANONICAL_COLUMNS if c in df.columns]
    out_df = df[out_cols].copy()

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        table = pa.Table.from_pandas(out_df, preserve_index=False)
        pq.write_table(table, tmp_path, compression="snappy")

        file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        logger.info("Parquet written: %.1f MB, %d rows", file_size_mb, len(out_df))

        bucket = gcs_client.bucket(config.gcs_bucket)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(tmp_path, content_type="application/x-parquet")
        logger.info("Uploaded to gs://%s/%s", config.gcs_bucket, gcs_path)
    finally:
        os.unlink(tmp_path)

    return gcs_path


# ---------------------------------------------------------------------------
# Raw file manifest
# ---------------------------------------------------------------------------


def write_raw_manifest(
    survey_id: str,
    raw_file_paths: list[dict],
    gcs_bucket: str,
    gcs_client: storage.Client,
    notes: str = "",
) -> str:
    """Write a raw_files.json manifest to GCS for researcher discovery.

    The manifest lists every raw acquisition file for this survey so
    researchers can find and download raw data for re-inversion without
    needing to know the GCS folder structure.  Referenced by the
    raw_manifest asset in the STAC item.

    Args:
        survey_id: e.g. 'gila_animas_2025'
        raw_file_paths: List of dicts, each with keys:
            file (str), gcs_path (str), flight_id (str|None),
            size_bytes (int), normalization_needed (bool)
        gcs_bucket: GCS bucket name
        gcs_client: GCS client
        notes: Free-text notes about the survey's raw data

    Returns:
        GCS path of the uploaded manifest.
    """
    gcs_path = f"surveys/{survey_id}/metadata/raw_files.json"

    manifest = {
        "survey_id": survey_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "leveled_xyz": raw_file_paths,
        "companions": [],  # populated separately for SkyTEM surveys
        "notes": notes,
    }

    logger.info("Writing raw manifest: %s (%d files)", gcs_path, len(raw_file_paths))

    manifest_json = json.dumps(manifest, indent=2)

    bucket = gcs_client.bucket(gcs_bucket)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(manifest_json, content_type="application/json")
    logger.info("Raw manifest uploaded to gs://%s/%s", gcs_bucket, gcs_path)

    return gcs_path


# ---------------------------------------------------------------------------
# STAC item builder — queries PostGIS for bbox/geometry/statistics
# ---------------------------------------------------------------------------


def _query_postgis_stac_fields(
    db_conn_string: str, survey_id: str, processing_stage: str
) -> dict | None:
    """Run the three PostGIS queries that populate STAC bbox, geometry,
    and summary statistics.

    Returns a dict with all derived fields, or None if queries fail.
    """
    raw_conn = get_raw_connection(db_conn_string)
    cur = raw_conn.cursor()

    try:
        # Query 1: bbox and convex hull geometry
        cur.execute(
            """
            SELECT
                ST_AsGeoJSON(ST_ConvexHull(ST_Collect(ST_Transform(geom, 4326)))) AS geometry,
                ST_XMin(ST_Extent(ST_Transform(geom, 4326))) AS min_lon,
                ST_YMin(ST_Extent(ST_Transform(geom, 4326))) AS min_lat,
                ST_XMax(ST_Extent(ST_Transform(geom, 4326))) AS max_lon,
                ST_YMax(ST_Extent(ST_Transform(geom, 4326))) AS max_lat
            FROM aem_soundings
            WHERE survey_id = %s AND processing_stage = %s
            """,
            (survey_id, processing_stage),
        )
        geo_row = cur.fetchone()

        # Query 2: temporal extent
        cur.execute(
            """
            SELECT
                MIN(date_acquired) AS start_datetime,
                MAX(date_acquired) AS end_datetime
            FROM aem_soundings
            WHERE survey_id = %s AND processing_stage = %s
            """,
            (survey_id, processing_stage),
        )
        time_row = cur.fetchone()

        # Query 3: summary statistics
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT record_id)               AS num_soundings,
                MAX(layer_no)                           AS num_layers,
                MIN(depth_top_m)                        AS depth_min_m,
                MAX(depth_bot_m)                        AS depth_max_m,
                BOOL_OR(resistivity_std IS NOT NULL)    AS has_uncertainty,
                BOOL_OR(doi_conservative_m IS NOT NULL) AS has_doi
            FROM aem_soundings
            WHERE survey_id = %s AND processing_stage = %s
            """,
            (survey_id, processing_stage),
        )
        stats_row = cur.fetchone()

        if geo_row is None or geo_row[0] is None:
            logger.warning("PostGIS geometry query returned no results")
            return None

        # Parse geometry JSON
        geometry = json.loads(geo_row[0])
        bbox = [float(geo_row[1]), float(geo_row[2]),
                float(geo_row[3]), float(geo_row[4])]

        # Parse temporal
        start_dt = None
        end_dt = None
        if time_row and time_row[0] is not None:
            start_dt = time_row[0].strftime("%Y-%m-%dT00:00:00Z")
            end_dt = time_row[1].strftime("%Y-%m-%dT00:00:00Z")

        return {
            "geometry": geometry,
            "bbox": bbox,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "num_soundings": int(stats_row[0]) if stats_row[0] else 0,
            "num_layers": int(stats_row[1]) if stats_row[1] else 0,
            "depth_min_m": float(stats_row[2]) if stats_row[2] is not None else None,
            "depth_max_m": float(stats_row[3]) if stats_row[3] is not None else None,
            "has_uncertainty": bool(stats_row[4]) if stats_row[4] is not None else False,
            "has_doi": bool(stats_row[5]) if stats_row[5] is not None else False,
        }

    except Exception:
        logger.exception("PostGIS STAC queries failed — will fall back to DataFrame")
        return None
    finally:
        cur.close()
        raw_conn.close()


def _derive_stac_fields_from_df(df: pd.DataFrame) -> dict:
    """Fallback: derive STAC bbox/geometry/stats from the DataFrame
    when PostGIS queries are unavailable.
    """
    logger.warning("Using DataFrame fallback for STAC fields (PostGIS unavailable)")

    min_lon = float(df["longitude_dd"].min())
    max_lon = float(df["longitude_dd"].max())
    min_lat = float(df["latitude_dd"].min())
    max_lat = float(df["latitude_dd"].max())

    points = gpd.points_from_xy(df["longitude_dd"], df["latitude_dd"])
    hull = MultiPoint(list(points)).convex_hull
    geometry = mapping(hull)

    start_dt = None
    end_dt = None
    if "date_acquired" in df.columns and df["date_acquired"].notna().any():
        dates = pd.to_datetime(df["date_acquired"].dropna())
        start_dt = dates.min().strftime("%Y-%m-%dT00:00:00Z")
        end_dt = dates.max().strftime("%Y-%m-%dT00:00:00Z")

    return {
        "geometry": geometry,
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "num_soundings": df["record_id"].nunique(),
        "num_layers": int(df["layer_no"].max()) if df["layer_no"].notna().any() else 0,
        "depth_min_m": float(df["depth_top_m"].min()) if df["depth_top_m"].notna().any() else None,
        "depth_max_m": float(df["depth_bot_m"].max()) if df["depth_bot_m"].notna().any() else None,
        "has_uncertainty": bool(df["resistivity_std"].notna().any()),
        "has_doi": bool(df["doi_conservative_m"].notna().any()),
    }


def build_stac_stub(
    df: pd.DataFrame,
    config: IngestConfig,
    parquet_gcs_path: str,
    raw_manifest_gcs_path: str,
    survey_metadata: dict | None = None,
    geoserver_base_url: str = "https://data.nmbgmr.nmt.edu/geoserver",
    stac_base_url: str = "https://data.nmbgmr.nmt.edu/stac",
) -> dict:
    """Build a complete STAC 1.0.0 item matching the stac_schema.md spec.

    Queries PostGIS for bbox, geometry, and summary statistics.  Falls back
    to deriving these from the DataFrame if PostGIS is unavailable.

    Args:
        df: Loaded DataFrame (fallback only).
        config: Validated IngestConfig.
        parquet_gcs_path: GCS path of the Parquet output.
        raw_manifest_gcs_path: GCS path of raw_files.json.
        survey_metadata: Dict with static per-survey values (survey_region,
            system, line_spacing_m, line_km, is_skytem).  If None, looked up
            from SURVEY_METADATA by config.survey_id.
        geoserver_base_url: Base URL for GeoServer endpoints.
        stac_base_url: Base URL for STAC catalog.

    Returns:
        Dict conforming to STAC Item 1.0.0 with nmbgmr: namespace.
    """
    survey_id = config.survey_id
    processing_stage = config.processing_stage.value
    inversion_code = config.inversion_code.value
    contractor = config.contractor
    gcs_bucket = config.gcs_bucket
    source_gcs_path = config.source_gcs_path

    logger.info("Building STAC item for %s / %s", survey_id, processing_stage)

    # Resolve survey metadata — from argument, lookup table, or empty defaults
    if survey_metadata is None:
        meta = SURVEY_METADATA.get(survey_id)
        if meta is None:
            logger.warning(
                "No survey metadata found for '%s' — STAC nmbgmr: fields "
                "will have placeholder values. Add this survey to SURVEY_METADATA.",
                survey_id,
            )
            survey_metadata = {
                "survey_region": "Unknown",
                "system": "Unknown",
                "line_spacing_m": 0,
                "line_km": None,
                "is_skytem": False,
            }
        else:
            survey_metadata = meta.model_dump()

    # Query PostGIS for derived fields, fall back to DataFrame
    derived = _query_postgis_stac_fields(
        config.db_conn_string, survey_id, processing_stage
    )
    if derived is None:
        derived = _derive_stac_fields_from_df(df)

    source_epsg = int(df["source_epsg"].iloc[0]) if "source_epsg" in df.columns else None
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Item ID: {survey_id}_{processing_stage} — no inversion_code
    item_id = f"{survey_id}_{processing_stage}"

    stac_item: dict = {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": item_id,
        "collection": survey_id,
        "geometry": derived["geometry"],
        "bbox": derived["bbox"],
        "properties": {
            # Required temporal — datetime always null for multi-date datasets
            "datetime": None,
            "start_datetime": derived["start_datetime"],
            "end_datetime": derived["end_datetime"],
            "created": now_iso,
            "updated": now_iso,

            # Custom nmbgmr: namespace — survey identity
            "nmbgmr:survey_id": survey_id,
            "nmbgmr:survey_region": survey_metadata["survey_region"],
            "nmbgmr:processing_stage": processing_stage,
            "nmbgmr:inversion_code": inversion_code,
            "nmbgmr:contractor": contractor,
            "nmbgmr:system": survey_metadata["system"],
            "nmbgmr:line_spacing_m": survey_metadata["line_spacing_m"],
            "nmbgmr:line_km": survey_metadata["line_km"],
            "nmbgmr:source_epsg": source_epsg,

            # Statistics — derived from PostGIS after ingest
            "nmbgmr:num_soundings": derived["num_soundings"],
            "nmbgmr:num_layers": derived["num_layers"],
            "nmbgmr:depth_min_m": derived["depth_min_m"],
            "nmbgmr:depth_max_m": derived["depth_max_m"],

            # Quality flags
            "nmbgmr:has_uncertainty": derived["has_uncertainty"],
            "nmbgmr:has_doi": derived["has_doi"],

            # DOI — null until Phase 3 DataCite minting
            "nmbgmr:doi_url": None,
        },
        "assets": {
            "inversion_source": {
                "href": f"gs://{gcs_bucket}/{source_gcs_path}",
                "type": "text/plain",
                "title": f"Source inversion file — {inversion_code}",
                "roles": ["data", "source"],
            },
            "data_parquet": {
                "href": f"gs://{gcs_bucket}/{parquet_gcs_path}",
                "type": "application/x-parquet",
                "title": "Bulk download — canonical schema Parquet (all flights merged)",
                "roles": ["data"],
                "nmbgmr:note": (
                    "Canonical aem_soundings schema. Queryable with DuckDB, "
                    "pandas, pyarrow. HTTP range requests supported."
                ),
            },
            "data_wfs": {
                "href": (
                    f"{geoserver_base_url}/aem/ows?"
                    f"service=WFS&version=2.0.0&request=GetFeature"
                    f"&typeName=aem:aem_soundings"
                    f"&CQL_FILTER=survey_id='{survey_id}'"
                    f" AND processing_stage='{processing_stage}'"
                ),
                "type": "application/json",
                "title": "WFS endpoint — sounding locations and resistivity",
                "roles": ["data"],
            },
            "data_wms": {
                "href": (
                    f"{geoserver_base_url}/aem/ows?"
                    f"service=WMS&version=1.3.0&request=GetMap"
                    f"&layers=aem:aem_soundings"
                ),
                "type": "image/png",
                "title": "WMS endpoint — sounding location map",
                "roles": ["overview"],
            },
            "raw_manifest": {
                "href": f"gs://{gcs_bucket}/{raw_manifest_gcs_path}",
                "type": "application/json",
                "title": "Raw file manifest — all source files for this survey",
                "roles": ["metadata"],
                "nmbgmr:note": (
                    "Lists all raw acquisition files, companion files, "
                    "and their GCS paths."
                ),
            },
        },
        "links": [
            {
                "rel": "self",
                "href": f"{stac_base_url}/collections/{survey_id}/items/{item_id}",
            },
            {"rel": "root", "href": stac_base_url},
            {
                "rel": "collection",
                "href": f"{stac_base_url}/collections/{survey_id}",
            },
        ],
    }

    # Conditionally add companions asset for SkyTEM surveys
    if survey_metadata.get("is_skytem", False):
        stac_item["assets"]["companions"] = {
            "href": f"gs://{gcs_bucket}/surveys/{survey_id}/acquisition/companions/",
            "type": "application/json",
            "title": "Aarhus Workbench companion files — GEX + TTP + LIN",
            "roles": ["source"],
            "nmbgmr:note": (
                "Required for re-inversion in Aarhus Workbench. "
                "Contains system geometry (GEX), column definitions (TTP), "
                "and line definitions (LIN)."
            ),
        }

    logger.info(
        "STAC item built: %s — %d soundings, %d layers, "
        "uncertainty=%s, doi=%s",
        item_id,
        derived["num_soundings"],
        derived["num_layers"],
        derived["has_uncertainty"],
        derived["has_doi"],
    )
    return stac_item


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def run_ingest(
    config: IngestConfig,
    raw_file_paths: list[dict] | None = None,
    raw_manifest_notes: str = "",
) -> dict:
    """Orchestrate the full ingest pipeline for a single AEM inversion file.

    Args:
        config: Validated IngestConfig (from Typer CLI or programmatic call).
        raw_file_paths: List of raw file dicts for the manifest.
            If None, an empty manifest is written (populated later by
            the migration script).
        raw_manifest_notes: Free-text notes for the manifest.

    Returns:
        STAC item dict.
    """
    filepath = config.filepath

    logger.info("=" * 70)
    logger.info("INGEST START: %s", filepath)
    logger.info("  survey_id:        %s", config.survey_id)
    logger.info("  processing_stage: %s", config.processing_stage.value)
    logger.info("  inversion_code:   %s", config.inversion_code.value)
    logger.info("  contractor:       %s", config.contractor)
    logger.info("  source_gcs_path:  %s", config.source_gcs_path)
    logger.info("=" * 70)

    # Step 1: Detect format
    fmt = detect_format(filepath)
    logger.info("Step 1 — Format detected: %s", fmt.value)

    # Step 2: Parse to canonical DataFrame
    if fmt == SourceFormat.BYLAYER:
        df = parse_bylayer(filepath)
    elif fmt == SourceFormat.SEOGI_RHO:
        df = parse_seogi_rho(filepath, flight_id=config.flight_id)
    elif fmt == SourceFormat.AGF_LCI:
        if config.system is None:
            raise ValueError(
                "AGF LCI format requires --system parameter "
                "(e.g. '306hp' or '312hp')"
            )
        df = parse_agf_lci(filepath, system=config.system.value)
    else:
        raise ValueError(f"Unknown format: {fmt}")

    logger.info("Step 2 — Parsed: %d rows", len(df))

    if config.date_acquired:
        df["date_acquired"] = config.date_acquired

    # Step 3: Load into PostGIS
    n_rows = load_to_postgis(df, config)
    logger.info("Step 3 — PostGIS loaded: %d rows", n_rows)

    # Step 4: Write Parquet
    gcs_client = storage.Client()
    parquet_gcs_path = write_parquet(df, config, gcs_client)
    logger.info("Step 4 — Parquet written: %s", parquet_gcs_path)

    # Step 5: Write raw file manifest
    raw_manifest_gcs_path = write_raw_manifest(
        config.survey_id,
        raw_file_paths or [],
        config.gcs_bucket,
        gcs_client,
        notes=raw_manifest_notes,
    )
    logger.info("Step 5 — Raw manifest written: %s", raw_manifest_gcs_path)

    # Step 6: Build STAC item (queries PostGIS for derived fields)
    stac_item = build_stac_stub(
        df, config, parquet_gcs_path, raw_manifest_gcs_path,
    )
    logger.info("Step 6 — STAC item built: %s", stac_item["id"])

    logger.info("INGEST COMPLETE: %s → %d rows loaded", filepath, n_rows)
    return stac_item
