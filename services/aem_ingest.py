# flake8: noqa: E501
"""
services.aem_ingest — Orchestrates the full ingest pipeline.

Architecture note: the GCS mapper (aem_gcs_mapper.py) is the single source
of truth for where every file lives in GCS. This pipeline does NOT decide
GCS paths — it receives the mapper's proposed_gcs_path via
config.source_gcs_path and records it in the PostGIS source_file column.

GeoServer OpenSearch for EO is expected to read authoritative AEM metadata
directly from PostGIS. The OSEO tables live in the migrated `stac` schema.
This pipeline configures GeoServer against that schema and upserts
collections/products through the OSEO admin REST API when GeoServer
credentials are configured.

Steps per file:
  1. Validate config (Pydantic, including mapper-provided source_gcs_path)
  2. Detect format
  3. Parse to canonical long-format DataFrame
  4. Load into PostGIS (aem_soundings + aem_sounding_metadata)
  5. Write Parquet to GCS
  6. Write raw file manifest to GCS
  7. Configure GeoServer stores against the migrated stac schema
  8. Upsert OSEO collection/product metadata
  9. Return ingest result metadata for operational logging
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

from schemas.aem import IngestConfig, REQUIRED_COLUMNS, SourceFormat
from services.aem_db import get_raw_connection
from services.aem_oseo import (
    ingest_oseo_metadata,
    load_oseo_config,
    provision_oseo_services,
)
from services.aem_parsers import (
    detect_format,
    parse_agf_lci,
    parse_bylayer,
    parse_seogi_rho,
)
from services.aem_parsers.common import CANONICAL_COLUMNS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PostGIS loading
# ---------------------------------------------------------------------------

INSERT_COLUMNS = [
    "survey_id",
    "processing_stage",
    "inversion_code",
    "contractor",
    "source_file",
    "source_epsg",
    "line_id",
    "record_id",
    "layer_no",
    "elevation",
    "sensor_alt",
    "terrain_clear",
    "depth_top",
    "depth_bot",
    "thickness",
    "resistivity",
    "resistivity_std",
    "conductivity",
    "doi_conservative",
    "doi_standard",
    "resdata",
    "restotal",
    "plni",
    "date_acquired",
]


def _directory_readme_contents(directory_path: str) -> str:
    """Build a short README body for a GCS directory prefix."""
    return (
        f"# {directory_path}\n\n"
        "This prefix is managed by the Ocotillo AEM ingest pipeline.\n\n"
        "Contents may include canonical Parquet exports, ingest manifests, and\n"
        "other pipeline-generated artifacts used for downstream discovery and\n"
        "publication.\n"
    )


def ensure_prefix_readmes(
    gcs_bucket: str,
    gcs_client: storage.Client,
    gcs_paths: list[str],
) -> list[str]:
    """Ensure every written GCS directory prefix has a top-level README.md."""
    bucket = gcs_client.bucket(gcs_bucket)
    uploaded_paths: list[str] = []
    seen: set[str] = set()

    for gcs_path in gcs_paths:
        parts = gcs_path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            directory_path = "/".join(parts[:depth])
            readme_path = f"{directory_path}/README.md"
            if readme_path in seen:
                continue
            seen.add(readme_path)

            blob = bucket.blob(readme_path)
            exists = False
            if hasattr(blob, "exists"):
                exists = blob.exists()
            if exists:
                continue

            blob.upload_from_string(
                _directory_readme_contents(directory_path),
                content_type="text/markdown",
            )
            uploaded_paths.append(readme_path)
            logger.info("Created prefix README: gs://%s/%s", gcs_bucket, readme_path)

    return uploaded_paths


def load_to_postgis(
    df: pd.DataFrame,
    config: IngestConfig,
) -> int:
    """Bulk-insert normalized DataFrame into aem_soundings and
    aem_sounding_metadata.

    Uses a staging-table approach:
      1. COPY into a temp table via pg8000's execute(..., stream=...) support
      2. INSERT INTO aem_soundings with ST_Transform(ST_GeomFromEWKT(...), 4326)
      3. Aggregate and upsert into aem_sounding_metadata

    The source_file column stores the mapper's GCS path (config.source_gcs_path).

    Returns:
        Number of rows inserted into aem_soundings.
    """
    logger.info(
        "Loading to PostGIS: survey=%s, stage=%s, %d rows",
        config.survey_id,
        config.processing_stage.value,
        len(df),
    )

    df = df.copy()
    df["survey_id"] = config.survey_id
    df["processing_stage"] = config.processing_stage.value
    df["inversion_code"] = config.inversion_code.value
    df["contractor"] = config.contractor
    df["source_file"] = config.source_gcs_path

    df["geom_wkt"] = (
        "SRID="
        + df["source_epsg"].astype(int).astype(str)
        + ";POINT("
        + df["easting"].astype(str)
        + " "
        + df["northing"].astype(str)
        + ")"
    )

    pre_count = len(df)
    mask = df[REQUIRED_COLUMNS].notna().all(axis=1)
    df = df[mask]
    dropped = pre_count - len(df)
    if dropped > 0:
        logger.warning("Dropped %d rows with NULLs in required columns", dropped)

    raw_conn = get_raw_connection()
    cur = raw_conn.cursor()

    try:
        cur.execute("""
            CREATE TEMP TABLE _ingest_staging (
                survey_id TEXT, processing_stage TEXT, inversion_code TEXT,
                contractor TEXT, source_file TEXT, source_epsg INTEGER,
                line_id TEXT, record_id TEXT, layer_no SMALLINT,
                easting DOUBLE PRECISION, northing DOUBLE PRECISION,
                elevation DOUBLE PRECISION, sensor_alt DOUBLE PRECISION,
                terrain_clear DOUBLE PRECISION,
                depth_top DOUBLE PRECISION, depth_bot DOUBLE PRECISION,
                thickness DOUBLE PRECISION,
                resistivity DOUBLE PRECISION, resistivity_std DOUBLE PRECISION,
                conductivity DOUBLE PRECISION,
                doi_conservative DOUBLE PRECISION, doi_standard DOUBLE PRECISION,
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
        cur.execute(copy_sql, stream=buf)
        logger.info("COPY to staging: %d rows", len(df))

        cur.execute(f"""
            INSERT INTO aem_soundings (
                {', '.join(INSERT_COLUMNS)}, geom
            )
            SELECT
                {', '.join(INSERT_COLUMNS)},
                ST_Transform(ST_GeomFromEWKT(geom_wkt), 4326)
            FROM _ingest_staging;
        """)
        sounding_rows = cur.rowcount
        logger.info("Inserted %d rows into aem_soundings", sounding_rows)

        _insert_metadata(
            cur,
            config.survey_id,
            config.processing_stage.value,
            config.inversion_code.value,
            df,
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
    cur,
    survey_id: str,
    processing_stage: str,
    inversion_code: str,
    df: pd.DataFrame,
) -> None:
    """Aggregate sounding-level summaries and upsert into aem_sounding_metadata."""
    group_cols = ["line_id", "record_id"]
    meta = df.groupby(group_cols, as_index=False).agg(
        easting=("easting", "first"),
        northing=("northing", "first"),
        num_layers=("layer_no", "count"),
        max_depth=("depth_bot", "min"),
        has_uncertainty=("resistivity_std", lambda x: x.notna().any()),
        has_doi=("doi_conservative", lambda x: x.notna().any()),
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
                geom,
                flight_id, date_acquired, num_layers, max_depth,
                has_uncertainty, has_doi, inversion_code, source_epsg
            ) VALUES (
                %s, %s, %s, %s,
                ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), %s), 4326),
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (survey_id, line_id, record_id, processing_stage)
            DO UPDATE SET
                num_layers = EXCLUDED.num_layers,
                max_depth = EXCLUDED.max_depth,
                has_uncertainty = EXCLUDED.has_uncertainty,
                has_doi = EXCLUDED.has_doi
            """,
            (
                row["survey_id"],
                row["line_id"],
                row["record_id"],
                row["processing_stage"],
                row["easting"],
                row["northing"],
                int(row["source_epsg"]),
                row.get("flight_id"),
                row.get("date_acquired"),
                int(row["num_layers"]) if pd.notna(row["num_layers"]) else None,
                float(row["max_depth"]) if pd.notna(row["max_depth"]) else None,
                bool(row["has_uncertainty"]),
                bool(row["has_doi"]),
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

        ensure_prefix_readmes(config.gcs_bucket, gcs_client, [gcs_path])
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
    GeoServer/OpenSearch metadata can reference this manifest as needed.

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

    ensure_prefix_readmes(gcs_bucket, gcs_client, [gcs_path])
    bucket = gcs_client.bucket(gcs_bucket)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(manifest_json, content_type="application/json")
    logger.info("Raw manifest uploaded to gs://%s/%s", gcs_bucket, gcs_path)

    return gcs_path


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
        Ingest result summary.
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

    oseo_result = None
    oseo_config = load_oseo_config()
    if oseo_config is None:
        logger.warning(
            "Step 6 — OSEO publish skipped: missing GeoServer environment config"
        )
    else:
        provision_oseo_services(oseo_config)
        oseo_result = ingest_oseo_metadata(
            df,
            config,
            oseo_config,
        )
        logger.info(
            "Step 6 — OSEO metadata upserted: collection=%s product=%s",
            oseo_result["collection_id"],
            oseo_result["product_id"],
        )

    result = {
        "survey_id": config.survey_id,
        "processing_stage": config.processing_stage.value,
        "inversion_code": config.inversion_code.value,
        "source_gcs_path": config.source_gcs_path,
        "parquet_gcs_path": parquet_gcs_path,
        "raw_manifest_gcs_path": raw_manifest_gcs_path,
        "rows_loaded": n_rows,
        "oseo": oseo_result,
    }
    logger.info(
        "Step 7 — Ingest result prepared: survey=%s stage=%s rows=%d",
        result["survey_id"],
        result["processing_stage"],
        result["rows_loaded"],
    )

    logger.info("INGEST COMPLETE: %s → %d rows loaded", filepath, n_rows)
    return result
