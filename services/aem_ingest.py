# flake8: noqa: E501
"""
services.aem_ingest — Orchestrates the full ingest pipeline.

Architecture note: the GCS mapper (aem_gcs_mapper.py) is the single source
of truth for where every file lives in GCS. This pipeline does NOT decide
GCS paths — it receives the mapper's proposed_gcs_path via
config.source_gcs_path and records it in the PostGIS source_file column.

This service no longer owns any STAC API, OSEO, or GeoServer integration.
Instead, it builds deterministic STAC Collection and Item payloads, writes
those payloads to GCS for replay, and loads them into pgstac via pypgstac.

Steps per file:
  1. Validate config (Pydantic, including mapper-provided source_gcs_path)
  2. Detect format
  3. Parse to canonical long-format DataFrame
  4. Load into PostGIS (aem_soundings + aem_sounding_metadata)
  5. Write Parquet to GCS
  6. Write raw file manifest to GCS
  7. Write STAC payload artifacts for replay
  8. Load the payloads into pgstac with pypgstac
  9. Return ingest result metadata for operational logging
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import tempfile
from datetime import datetime, timezone
from google.cloud import storage
from schemas.aem import IngestConfig, REQUIRED_COLUMNS, SourceFormat
from services import aem_stac
from services.aem_db import get_raw_connection
from services.aem_parsers import (
    detect_format,
    parse_agf_lci,
    parse_bylayer,
    parse_seogi_rho,
)
from services.aem_parsers.detect import extract_flight_id
from services.aem_parsers.common import CANONICAL_COLUMNS

logger = logging.getLogger(__name__)

SEOGI_SOURCE_EPSG_OVERRIDES = {
    # Gila-Animas is in UTM zone 12N; treating it as zone 13 shifts geometries east.
    "gila_animas_2025": 32612,
}


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

DEFAULT_POSTGIS_COPY_BATCH_SIZE = 5_000


def _postgis_copy_batch_size() -> int:
    """Return the configured PostGIS batch size with a safe default."""
    raw = os.getenv("AEM_POSTGIS_COPY_BATCH_SIZE")
    if raw is None:
        return DEFAULT_POSTGIS_COPY_BATCH_SIZE

    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid AEM_POSTGIS_COPY_BATCH_SIZE=%r; using default %d",
            raw,
            DEFAULT_POSTGIS_COPY_BATCH_SIZE,
        )
        return DEFAULT_POSTGIS_COPY_BATCH_SIZE

    if value <= 0:
        logger.warning(
            "Non-positive AEM_POSTGIS_COPY_BATCH_SIZE=%r; using default %d",
            raw,
            DEFAULT_POSTGIS_COPY_BATCH_SIZE,
        )
        return DEFAULT_POSTGIS_COPY_BATCH_SIZE

    return value


def _next_batch_stop(df: pd.DataFrame, start: int, batch_size: int) -> int:
    """Advance the batch boundary so a sounding never spans two batches."""
    stop = min(start + batch_size, len(df))
    if stop >= len(df):
        return len(df)

    while stop < len(df):
        prev = df.iloc[stop - 1]
        current = df.iloc[stop]
        if (
            prev["line_id"] != current["line_id"]
            or prev["record_id"] != current["record_id"]
        ):
            break
        stop += 1

    return stop


def _resolve_seogi_source_epsg(survey_id: str) -> int:
    return SEOGI_SOURCE_EPSG_OVERRIDES.get(survey_id, 32613)


def _normalize_line_join_value(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except (TypeError, ValueError):
        return text
    return str(int(numeric)) if numeric.is_integer() else text


def _normalize_flight_id_for_join(flight_id: str | None) -> str | None:
    """Only use parsed flight IDs that match the expected F## pattern."""
    if flight_id is None:
        return None
    normalized = flight_id.strip()
    if re.fullmatch(r"F\d+(?:-F\d+)*", normalized):
        return normalized
    return None


def _apply_acquisition_metadata_timestamps(
    df: pd.DataFrame,
    acquisition_file_paths: list[dict] | None,
    flight_id: str | None = None,
) -> pd.DataFrame:
    """Join Date from raw acquisition CSVs onto parsed soundings."""
    if (
        not acquisition_file_paths
        or "_source_point_order" not in df.columns
        or "line_id" not in df.columns
    ):
        return df

    timestamp_frames: list[pd.DataFrame] = []
    for raw_file in acquisition_file_paths:
        raw_flight_id = raw_file.get("flight_id")
        if flight_id and raw_flight_id and raw_flight_id != flight_id:
            continue

        source_path = raw_file.get("source_path")
        if not source_path or not str(source_path).lower().endswith(".csv"):
            continue

        try:
            raw_df = pd.read_csv(source_path)
        except Exception as exc:
            logger.warning(
                "Skipping acquisition timestamp companion %s: %s",
                source_path,
                exc,
            )
            continue

        required_columns = {"Line", "Date"}
        if not required_columns.issubset(raw_df.columns):
            continue

        timestamps = raw_df.loc[:, ["Line", "Date"]].copy()
        timestamps["_join_line_id"] = timestamps["Line"].map(_normalize_line_join_value)
        timestamps["_source_point_order"] = (
            timestamps.groupby("_join_line_id", sort=False).cumcount() + 1
        )
        timestamps = timestamps.rename(columns={"Date": "date_acquired"})
        timestamp_frames.append(
            timestamps[["_join_line_id", "_source_point_order", "date_acquired"]]
        )

    if not timestamp_frames:
        return df

    timestamp_df = pd.concat(timestamp_frames, ignore_index=True)
    enriched_df = df.copy()
    enriched_df["_join_line_id"] = enriched_df["line_id"].map(
        _normalize_line_join_value
    )
    enriched_df = enriched_df.merge(
        timestamp_df,
        on=["_join_line_id", "_source_point_order"],
        how="left",
        suffixes=("", "_companion"),
    )

    for column in ["date_acquired"]:
        companion_column = f"{column}_companion"
        if companion_column in enriched_df.columns:
            if column not in enriched_df.columns:
                enriched_df[column] = enriched_df[companion_column]
            else:
                enriched_df[column] = enriched_df[column].where(
                    enriched_df[column].notna(), enriched_df[companion_column]
                )
            enriched_df = enriched_df.drop(columns=[companion_column])

    return enriched_df.drop(columns=["_join_line_id"])


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

    Uses a batched staging-table approach:
      1. COPY a bounded batch into a temp table via pg8000's
         execute(..., stream=...) support
      2. INSERT INTO aem_soundings with ST_Transform(ST_GeomFromEWKT(...), 4326)
      3. TRUNCATE the staging table before loading the next batch
      4. Aggregate and upsert into aem_sounding_metadata

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

    df = df.sort_values(
        ["line_id", "record_id", "layer_no"], kind="stable"
    ).reset_index(drop=True)

    raw_conn = get_raw_connection()
    cur = raw_conn.cursor()

    try:
        cur.execute("DROP TABLE IF EXISTS _ingest_staging;")
        cur.execute("DROP TABLE IF EXISTS _ingest_metadata_keys;")

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
            );
        """)

        cur.execute("""
            CREATE TEMP TABLE _ingest_metadata_keys (
                line_id TEXT,
                record_id TEXT
            );
        """)

        staging_cols = INSERT_COLUMNS + ["geom_wkt"]
        copy_sql = (
            f"COPY _ingest_staging ({', '.join(staging_cols)}) "
            f"FROM STDIN WITH (FORMAT csv, NULL '\\N')"
        )
        insert_sql = f"""
            INSERT INTO aem_soundings (
                {', '.join(INSERT_COLUMNS)}, geom
            )
            SELECT
                {', '.join(INSERT_COLUMNS)},
                ST_Transform(ST_GeomFromEWKT(geom_wkt), 4326)
            FROM _ingest_staging;
        """

        metadata_keys = df[["line_id", "record_id"]].drop_duplicates()
        key_buf = io.StringIO()
        metadata_keys.to_csv(key_buf, index=False, header=False, na_rep="\\N")
        key_buf.seek(0)
        cur.execute(
            "COPY _ingest_metadata_keys (line_id, record_id) "
            "FROM STDIN WITH (FORMAT csv, NULL '\\N')",
            stream=key_buf,
        )

        cur.execute(
            """
            DELETE FROM aem_sounding_metadata m
            USING _ingest_metadata_keys k
            WHERE m.survey_id = %s
              AND m.processing_stage = %s
              AND m.line_id = k.line_id
              AND m.record_id = k.record_id;
            """,
            (config.survey_id, config.processing_stage.value),
        )
        cur.execute(
            """
            DELETE FROM aem_soundings
            WHERE survey_id = %s
              AND processing_stage = %s
              AND source_file = %s;
            """,
            (
                config.survey_id,
                config.processing_stage.value,
                config.source_gcs_path,
            ),
        )

        sounding_rows = 0
        batch_size = _postgis_copy_batch_size()
        logger.info("Using PostGIS batch size: %d rows", batch_size)

        start = 0
        while start < len(df):
            stop = _next_batch_stop(df, start, batch_size)
            batch_df = df.iloc[start:stop]

            buf = io.StringIO()
            batch_df[staging_cols].to_csv(buf, index=False, header=False, na_rep="\\N")
            buf.seek(0)

            cur.execute(copy_sql, stream=buf)
            logger.info(
                "COPY to staging: rows %d-%d of %d",
                start + 1,
                stop,
                len(df),
            )

            cur.execute(insert_sql)
            batch_rows = cur.rowcount
            sounding_rows += batch_rows
            logger.info(
                "Inserted %d rows into aem_soundings for batch %d-%d",
                batch_rows,
                start + 1,
                stop,
            )

            _insert_metadata(
                cur,
                config.survey_id,
                config.processing_stage.value,
                config.inversion_code.value,
                batch_df,
            )

            cur.execute("TRUNCATE _ingest_staging;")
            raw_conn.commit()
            logger.info(
                "Committed PostGIS batch %d-%d for %s",
                start + 1,
                stop,
                config.source_gcs_path,
            )

            start = stop

        logger.info("Inserted %d rows into aem_soundings", sounding_rows)
        logger.info("PostGIS load committed successfully")
        return sounding_rows

    except Exception:
        raw_conn.rollback()
        logger.exception("PostGIS load failed, transaction rolled back")
        raise
    finally:
        try:
            cur.execute("DROP TABLE IF EXISTS _ingest_staging;")
            cur.execute("DROP TABLE IF EXISTS _ingest_metadata_keys;")
            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
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
    needing to know the GCS folder structure.

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
    acquisition_file_paths: list[dict] | None = None,
    raw_manifest_notes: str = "",
    skip_soundings_upload: bool = False,
    skip_stac_uploads: bool = False,
    debug_stac_limit: bool = False,
    debug_stac_remaining_by_collection: dict[str, int] | None = None,
) -> dict:
    """Orchestrate the full ingest pipeline for a single AEM inversion file.

    Args:
        config: Validated IngestConfig (from Typer CLI or programmatic call).
        raw_file_paths: List of raw file dicts for the manifest.
            If None, an empty manifest is written (populated later by
            the migration script).
        acquisition_file_paths: Local raw acquisition CSVs used to stamp
            Date onto parsed soundings before STAC generation.
        raw_manifest_notes: Free-text notes for the manifest.
        skip_soundings_upload: Skip loading parsed soundings into PostGIS.
        skip_stac_uploads: Skip writing STAC payloads and loading them into pgstac.
        debug_stac_limit: Limit STAC item uploads to 1000 records per collection.
        debug_stac_remaining_by_collection: Shared per-collection remaining item
            budget for debug-limited batch runs.

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
        source_epsg = _resolve_seogi_source_epsg(config.survey_id)
        df = parse_seogi_rho(
            filepath,
            flight_id=config.flight_id,
            source_epsg=source_epsg,
        )
    elif fmt == SourceFormat.AGF_LCI:
        if config.system is None:
            raise ValueError(
                "AGF LCI format requires --system parameter "
                "(e.g. '306hp' or '312hp')"
            )
        df = parse_agf_lci(filepath, system=config.system.value)
        source_epsg = (
            int(df["source_epsg"].dropna().iloc[0])
            if "source_epsg" in df.columns and df["source_epsg"].notna().any()
            else 26913
        )
    else:
        raise ValueError(f"Unknown format: {fmt}")
    if fmt == SourceFormat.BYLAYER:
        source_epsg = (
            int(df["source_epsg"].dropna().iloc[0])
            if "source_epsg" in df.columns and df["source_epsg"].notna().any()
            else 26913
        )

    logger.info("Step 2 — Parsed: %d rows", len(df))

    if config.date_acquired:
        df["date_acquired"] = config.date_acquired
    elif fmt == SourceFormat.SEOGI_RHO:
        df = _apply_acquisition_metadata_timestamps(
            df,
            acquisition_file_paths,
            flight_id=_normalize_flight_id_for_join(extract_flight_id(config.filepath)),
        )

    # Step 3: Load into PostGIS
    if skip_soundings_upload:
        n_rows = 0
        logger.info("Step 3 — PostGIS load skipped")
    else:
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

    stac_collections = []
    stac_items = []
    stac_payload_paths = {
        "collection_gcs_path": None,
        "items_gcs_path": None,
        "collection_gcs_paths": {},
    }
    if skip_stac_uploads:
        logger.info("Step 6 — STAC uploads skipped (--skip-stac-uploads)")
    else:
        raw_stac_df = aem_stac.build_raw_stac_dataframe(
            acquisition_file_paths=acquisition_file_paths,
            raw_file_paths=raw_file_paths,
            source_epsg=source_epsg,
        )
        stac_collections = [
            aem_stac.build_stac_collection(
                df=raw_stac_df if not raw_stac_df.empty else df,
                config=config,
                parquet_gcs_path=parquet_gcs_path,
                raw_manifest_gcs_path=raw_manifest_gcs_path,
                raw_file_paths=raw_file_paths,
                kind="raw",
            ),
            aem_stac.build_stac_collection(
                df=df,
                config=config,
                parquet_gcs_path=parquet_gcs_path,
                raw_manifest_gcs_path=raw_manifest_gcs_path,
                raw_file_paths=raw_file_paths,
                kind="inversion",
            ),
        ]
        raw_stac_items = aem_stac.build_raw_stac_items(
            raw_stac_df,
            config=config,
            raw_manifest_gcs_path=raw_manifest_gcs_path,
        )
        inversion_stac_items = aem_stac.build_stac_items(
            df=df,
            config=config,
            parquet_gcs_path=parquet_gcs_path,
            raw_manifest_gcs_path=raw_manifest_gcs_path,
        )
        stac_items = raw_stac_items + inversion_stac_items
        total_stac_items = len(stac_items)
        if debug_stac_limit:
            stac_items = aem_stac.limit_stac_items_per_collection(
                stac_items,
                max_items_per_collection=1000,
                remaining_by_collection=debug_stac_remaining_by_collection,
            )
            logger.warning(
                "Step 6 — Debug STAC limit enabled: uploading %d of %d items (max 1000 per collection)",
                len(stac_items),
                total_stac_items,
            )
            if debug_stac_remaining_by_collection is not None:
                logger.warning(
                    "Step 6 — Remaining debug STAC item budget by collection: %s",
                    debug_stac_remaining_by_collection,
                )
        stac_payload_paths = aem_stac.write_stac_payloads(
            stac_collections,
            stac_items,
            config,
            gcs_client,
            ensure_prefix_readmes=ensure_prefix_readmes,
        )
        logger.info(
            "Step 6 — STAC payloads written: %s, %s",
            stac_payload_paths["collection_gcs_path"],
            stac_payload_paths["items_gcs_path"],
        )

        aem_stac.load_stac_to_pgstac(stac_collections, stac_items)
        logger.info("Step 7 — pgstac upsert complete: %d items", len(stac_items))

    inversion_collection = next(
        (
            collection
            for collection in stac_collections
            if collection["ocotillo:collection_kind"] == "inversion"
        ),
        None,
    )
    raw_collection = next(
        (
            collection
            for collection in stac_collections
            if collection["ocotillo:collection_kind"] == "raw"
        ),
        None,
    )

    result = {
        "survey_id": config.survey_id,
        "processing_stage": config.processing_stage.value,
        "inversion_code": config.inversion_code.value,
        "source_gcs_path": config.source_gcs_path,
        "parquet_gcs_path": parquet_gcs_path,
        "raw_manifest_gcs_path": raw_manifest_gcs_path,
        "stac_collection_id": (
            inversion_collection["id"] if inversion_collection else None
        ),
        "stac_raw_collection_id": raw_collection["id"] if raw_collection else None,
        "stac_item_count": len(stac_items),
        "stac_debug_limit_applied": debug_stac_limit,
        "stac_collection_gcs_path": stac_payload_paths["collection_gcs_path"],
        "stac_collection_gcs_paths": stac_payload_paths["collection_gcs_paths"],
        "stac_items_gcs_path": stac_payload_paths["items_gcs_path"],
        "rows_loaded": n_rows,
    }
    logger.info(
        "Step 8 — Ingest result prepared: survey=%s stage=%s rows=%d",
        result["survey_id"],
        result["processing_stage"],
        result["rows_loaded"],
    )

    logger.info("INGEST COMPLETE: %s → %d rows loaded", filepath, n_rows)
    return result
