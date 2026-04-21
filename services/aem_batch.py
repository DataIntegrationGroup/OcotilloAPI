# flake8: noqa: E501
"""Batch runner for AEM migration + ingest."""

from __future__ import annotations

import argparse
import logging
import pandas as pd
import sys
import time
from pathlib import Path

from services.aem_migration import MigrationRunner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provenance resolution
# ---------------------------------------------------------------------------

# Maps detected_type from the mapper CSV to the ingest pipeline's format key
# and the provenance values it needs.  The mapper already knows survey_id
# and processing_stage — but inversion_code and contractor are not in the CSV,
# so we resolve them from the detected_type + survey_id combination.

INVERSION_INGESTIBLE_TYPES = {"seogi_rho", "aarhus_bylayer", "agf_lci_csv"}
GEOTIFF_INGESTIBLE_TYPES = {"geotiff"}
INGESTIBLE_TYPES = INVERSION_INGESTIBLE_TYPES | GEOTIFF_INGESTIBLE_TYPES

# detected_type → (inversion_code, contractor)
# Some types are survey-dependent, so we also check survey_id.
PROVENANCE_MAP = {
    "seogi_rho": ("seogi_python", "GeoTech/Seogi"),
    "aarhus_bylayer": ("aarhus_sci", "GIP/Aarhus"),
    "agf_lci_csv": ("aarhus_lci", "AGF/Aarhus"),
}

# Survey-specific overrides (if a survey uses a different contractor
# for the same format, add it here)
PROVENANCE_OVERRIDES = {
    # ("detected_type", "survey_id"): ("inversion_code", "contractor"),
    ("aarhus_bylayer", "santa_teresa"): ("aarhus_sci", "GIP/Aarhus"),
    ("aarhus_bylayer", "mrg_2025"): ("aarhus_sci", "GIP/Ramboll"),
}


def resolve_provenance(detected_type: str, survey_id: str) -> dict:
    """Resolve inversion_code and contractor from detected_type + survey_id.

    Returns dict with 'inversion_code' and 'contractor' keys.
    """
    key = (detected_type, survey_id)
    if key in PROVENANCE_OVERRIDES:
        code, contractor = PROVENANCE_OVERRIDES[key]
    elif detected_type in PROVENANCE_MAP:
        code, contractor = PROVENANCE_MAP[detected_type]
    else:
        raise ValueError(
            f"No provenance mapping for detected_type='{detected_type}', "
            f"survey_id='{survey_id}'. Add it to PROVENANCE_MAP or "
            f"PROVENANCE_OVERRIDES."
        )
    return {"inversion_code": code, "contractor": contractor}


def resolve_system(detected_type: str, filename: str) -> str | None:
    """Resolve the SkyTEM system for AGF LCI files from the filename.

    AGF files include '306' or '312' in the filename.
    Returns '306hp', '312hp', or None (not applicable).
    """
    if detected_type != "agf_lci_csv":
        return None

    fname_lower = filename.lower()
    if "306" in fname_lower:
        return "306hp"
    if "312" in fname_lower:
        return "312hp"

    logger.warning(
        "Cannot determine SkyTEM system from AGF filename '%s'. "
        "Expected '306' or '312' in the name.",
        filename,
    )
    return None


# ---------------------------------------------------------------------------
# Raw file list builder
# ---------------------------------------------------------------------------


def build_raw_file_list(df: pd.DataFrame, survey_id: str) -> list[dict]:
    """Build the raw_file_paths list for write_raw_manifest().

    Pulls all geotech_raw_csv rows for this survey from the mapping CSV.
    These are the raw acquisition files that researchers would need to
    re-run inversions.
    """
    raw_mask = (
        (df["survey_id"] == survey_id)
        & (df["detected_type"] == "geotech_raw_csv")
        & (df["action"] == "MOVE")
    )
    raw_df = df[raw_mask]

    raw_files = []
    for _, row in raw_df.iterrows():
        # Extract flight ID from filename (e.g. GL250194_F01.csv → F01)
        fname = row["file_name"]
        flight_id = None
        import re

        m = re.search(r"_F(\d+)", fname)
        if m:
            flight_id = f"F{m.group(1)}"

        raw_files.append(
            {
                "file": fname,
                "gcs_path": row["proposed_gcs_path"],
                "flight_id": flight_id,
                "size_bytes": int(row.get("size_bytes", 0)),
                "normalization_needed": row.get("normalization_needed", "N") == "Y",
            }
        )

    return raw_files


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------


def run_batch(
    mapping_path: str,
    gcs_bucket: str,
    root_override: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    survey_filter: str | None = None,
    stage_filter: str | None = None,
    skip_soundings_upload: bool = False,
    skip_asset_db_publish: bool = False,
    skip_stac_uploads: bool = False,
) -> list[dict]:
    """Run migration for MOVE rows, then ingest/publish ingestible outputs.

    Args:
        mapping_path: Path to gcs_path_mapping.csv
        gcs_bucket: GCS bucket name
        root_override: Override source_path root (for personal Drive copies)
        dry_run: Show what would happen without running anything
        limit: Only process this many files (for testing)
        survey_filter: Only process this survey_id
        stage_filter: Only process this processing_stage
        skip_soundings_upload: Skip loading parsed soundings into PostGIS
        skip_asset_db_publish: Skip writing GeoTIFF asset metadata to Ocotillo DB
        skip_stac_uploads: Skip writing STAC payloads and loading them into pgstac

    Returns:
        List of ingest result dicts (empty list in dry-run mode).
    """
    migration_runner = MigrationRunner(
        mapping_path=mapping_path,
        bucket_name=gcs_bucket,
        root_override=root_override,
    )
    filtered_df = migration_runner.get_filtered_rows(
        survey_filter=survey_filter,
        stage_filter=stage_filter,
        limit=limit,
    )
    logger.info("Filtered mapping rows: %d", len(filtered_df))

    move_df = filtered_df[filtered_df["action"] == "MOVE"].copy()
    ingest_df = move_df[move_df["detected_type"].isin(INGESTIBLE_TYPES)].copy()
    logger.info("MOVE rows to migrate: %d", len(move_df))
    logger.info("Ingestible MOVE rows: %d", len(ingest_df))

    if len(filtered_df) == 0:
        logger.warning("No mapping rows match filters — nothing to do")
        return []

    # ----- Dry run -----
    if dry_run:
        migration_runner.run(
            dry_run=True,
            survey_filter=survey_filter,
            stage_filter=stage_filter,
            limit=limit,
        )
        return _dry_run(ingest_df, migration_runner.df, gcs_bucket)

    migration_runner.run(
        dry_run=False,
        survey_filter=survey_filter,
        stage_filter=stage_filter,
        limit=limit,
    )
    migration_runner.write_outputs()

    migration_status_by_gcs_path = {
        result.gcs_path: result.status for result in migration_runner.results
    }

    if len(ingest_df) == 0:
        logger.info("No ingestible MOVE rows matched filters after migration")
        return []

    ingest_df = ingest_df.sort_values(["survey_id", "file_name"]).reset_index(drop=True)

    # ----- Live run -----
    from schemas.aem import IngestConfig, InversionCode, ProcessingStage, SkytemSystem
    from services.aem_asset_ingest import (
        AEMIngestRecord,
        ingest_validated_aem_asset,
    )
    from services.gcs_helper import get_storage_bucket
    from services.aem_ingest import run_ingest
    from starlette.datastructures import Headers, UploadFile

    ingest_results = []
    succeeded = 0
    failed = 0
    errors = []
    gcs_bucket_obj = get_storage_bucket(bucket=gcs_bucket)

    for idx, (_, row) in enumerate(ingest_df.iterrows()):
        file_num = idx + 1
        total = len(ingest_df)
        filename = row["file_name"]
        survey_id = row["survey_id"]
        detected_type = row["detected_type"]

        logger.info(
            "=" * 60 + "\n[%d/%d] %s — %s / %s",
            file_num,
            total,
            filename,
            survey_id,
            detected_type,
        )

        try:
            migration_status = migration_status_by_gcs_path.get(
                row["proposed_gcs_path"]
            )
            if migration_status not in {"uploaded", "skipped_exists"}:
                raise RuntimeError(
                    "Migration step did not complete successfully "
                    f"(status={migration_status or 'missing'})"
                )

            source_path = migration_runner.resolve_source_path(row["source_path"])

            t0 = time.monotonic()
            if detected_type in INVERSION_INGESTIBLE_TYPES:
                # Resolve provenance
                prov = resolve_provenance(detected_type, survey_id)
                system = resolve_system(detected_type, filename)

                # Build raw file list for this survey (for manifest)
                raw_files = build_raw_file_list(migration_runner.df, survey_id)

                # Build IngestConfig
                config = IngestConfig(
                    filepath=source_path,
                    survey_id=survey_id,
                    processing_stage=ProcessingStage(row["processing_stage"]),
                    inversion_code=InversionCode(prov["inversion_code"]),
                    contractor=prov["contractor"],
                    gcs_bucket=gcs_bucket,
                    source_gcs_path=row["proposed_gcs_path"],
                    flight_id=None,  # auto-extracted from filename by parser
                    system=SkytemSystem(system) if system else None,
                )

                ingest_result = run_ingest(
                    config,
                    raw_file_paths=raw_files,
                    raw_manifest_notes=(
                        f"Generated by aem_batch.py during batch ingest. "
                        f"{len(raw_files)} raw files for survey {survey_id}."
                    ),
                    skip_soundings_upload=skip_soundings_upload,
                    skip_stac_uploads=skip_stac_uploads,
                )
            elif detected_type in GEOTIFF_INGESTIBLE_TYPES:
                file_path = Path(source_path)
                with file_path.open("rb") as stream:
                    upload = UploadFile(
                        file=stream,
                        filename=filename,
                        size=file_path.stat().st_size,
                        headers=Headers({"content-type": "image/tiff"}),
                    )
                    asset_record = AEMIngestRecord(
                        survey_id=survey_id,
                        file_name=filename,
                        proposed_gcs_path=row["proposed_gcs_path"],
                        action=row["action"],
                        normalization_needed=(
                            row.get("normalization_needed", "N") == "Y"
                        ),
                        detected_type=detected_type,
                        processing_stage=row["processing_stage"],
                    )
                    if skip_asset_db_publish:
                        asset_result = ingest_validated_aem_asset(
                            None,
                            upload,
                            asset_record,
                            bucket=gcs_bucket_obj,
                            persist_asset_metadata=False,
                        )
                    else:
                        from db.engine import session_ctx

                        with session_ctx() as session:
                            asset_result = ingest_validated_aem_asset(
                                session,
                                upload,
                                asset_record,
                                bucket=gcs_bucket_obj,
                            )
                            session.commit()

                publish_result = asset_result.publish_result
                ingest_result = {
                    "asset_id": asset_result.asset.id,
                    "asset_name": asset_result.asset.name,
                    "asset_storage_path": asset_result.asset.storage_path,
                    "asset_uri": asset_result.asset.uri,
                    "asset_db_publish_skipped": skip_asset_db_publish,
                    "publish_target": (
                        publish_result.target if publish_result else None
                    ),
                    "publish_status": (
                        publish_result.status if publish_result else None
                    ),
                    "publish_workspace": (
                        publish_result.workspace if publish_result else None
                    ),
                    "publish_store_name": (
                        publish_result.store_name if publish_result else None
                    ),
                    "publish_layer_name": (
                        publish_result.layer_name if publish_result else None
                    ),
                    "publish_detail": (
                        publish_result.detail if publish_result else None
                    ),
                    "processing_stage": row["processing_stage"],
                    "source_gcs_path": row["proposed_gcs_path"],
                    "survey_id": survey_id,
                }
            else:
                raise ValueError(
                    f"Unsupported detected_type for batch ingest: {detected_type}"
                )
            duration = time.monotonic() - t0

            ingest_results.append(ingest_result)
            succeeded += 1
            if "parquet_gcs_path" in ingest_result:
                logger.info(
                    "[%d/%d] SUCCESS: %s → %s (%.1fs)",
                    file_num,
                    total,
                    filename,
                    ingest_result["parquet_gcs_path"],
                    duration,
                )
            else:
                logger.info(
                    "[%d/%d] SUCCESS: %s → %s (%s, %.1fs)",
                    file_num,
                    total,
                    filename,
                    ingest_result["asset_storage_path"],
                    ingest_result["publish_status"],
                    duration,
                )

        except Exception as e:
            failed += 1
            errors.append({"file": filename, "survey": survey_id, "error": str(e)})
            logger.exception(
                "[%d/%d] FAILED: %s — %s",
                file_num,
                total,
                filename,
                e,
            )
            # Continue to next file — don't abort the batch
            continue

    # ----- Summary -----
    logger.info("=" * 60)
    logger.info(
        "BATCH COMPLETE: %d succeeded, %d failed, %d total",
        succeeded,
        failed,
        len(ingest_df),
    )

    if errors:
        logger.error("Failed files:")
        for err in errors:
            logger.error("  %s (%s): %s", err["file"], err["survey"], err["error"])

    return ingest_results


def _dry_run(
    ingest_df: pd.DataFrame,
    full_df: pd.DataFrame,
    gcs_bucket: str,
) -> list[dict]:
    """Show what would be ingested without running anything."""
    logger.info("=" * 70)
    logger.info("DRY RUN — nothing will be ingested")
    logger.info("=" * 70)

    logger.info("Files to ingest: %d", len(ingest_df))
    logger.info("Total size: %.1f MB", ingest_df["size_bytes"].sum() / 1e6)
    logger.info("Database: shared app engine (.env-driven)")
    logger.info("GCS bucket: %s", gcs_bucket)

    # By survey
    logger.info("By survey:")
    for survey_id, group in ingest_df.groupby("survey_id"):
        raw_count = len(
            full_df[
                (full_df["survey_id"] == survey_id)
                & (full_df["detected_type"] == "geotech_raw_csv")
                & (full_df["action"] == "MOVE")
            ]
        )
        inversion_count = int(
            group["detected_type"].isin(INVERSION_INGESTIBLE_TYPES).sum()
        )
        geotiff_count = int(group["detected_type"].isin(GEOTIFF_INGESTIBLE_TYPES).sum())
        logger.info(
            "  %s: %d inversion files, %d geotiffs, %d raw files for manifest",
            survey_id,
            inversion_count,
            geotiff_count,
            raw_count,
        )

    # File-by-file preview
    logger.info("Files that would be ingested:")
    logger.info("-" * 70)
    for idx, (_, row) in enumerate(ingest_df.iterrows()):
        detected_type = row["detected_type"]
        survey_id = row["survey_id"]
        if detected_type in INVERSION_INGESTIBLE_TYPES:
            try:
                prov = resolve_provenance(detected_type, survey_id)
                system = resolve_system(detected_type, row["file_name"])
            except ValueError:
                prov = {"inversion_code": "UNKNOWN", "contractor": "UNKNOWN"}
                system = None

            system_str = f" system={system}" if system else ""

            logger.info(
                "  [%2d] %s\n"
                "       survey=%s  stage=%s\n"
                "       code=%s  contractor=%s%s\n"
                "       source: %s...\n"
                "       →  gcs: %s\n"
                "       size: %s",
                idx + 1,
                row["file_name"],
                survey_id,
                row["processing_stage"],
                prov["inversion_code"],
                prov["contractor"],
                system_str,
                row["source_path"][:80],
                row["proposed_gcs_path"],
                row["size_human"],
            )
        else:
            logger.info(
                "  [%2d] %s\n"
                "       survey=%s  stage=%s\n"
                "       asset_type=%s  publish_target=geoserver\n"
                "       source: %s...\n"
                "       →  gcs: %s\n"
                "       size: %s",
                idx + 1,
                row["file_name"],
                survey_id,
                row["processing_stage"],
                detected_type,
                row["source_path"][:80],
                row["proposed_gcs_path"],
                row["size_human"],
            )

    # Warnings
    norm = ingest_df[ingest_df["normalization_needed"] == "Y"]
    if len(norm) > 0:
        logger.warning("NOTE: %d files have normalization_needed=Y", len(norm))
        logger.warning("  These will be ingested as-is. Normalization (wellid prefix)")
        logger.warning("  is handled by the parser, not the migration script.")

    logger.info("Batch dry-run includes the migration step for all filtered MOVE rows.")

    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            "NMBGMR AEM batch ingest — run the ingest pipeline for all "
            "ingestible files in the mapping CSV"
        ),
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="Path to gcs_path_mapping.csv",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="GCS bucket name (e.g. nmbgmr-aem-data)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Override source path root for local Drive copies",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be ingested without running anything",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only ingest the first N files (for testing — try --limit 2)",
    )
    parser.add_argument(
        "--survey",
        default=None,
        help="Only ingest files from this survey_id",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help="Only ingest files from this processing_stage",
    )
    parser.add_argument(
        "--skip-soundings-upload",
        action="store_true",
        help="Skip loading parsed soundings into PostGIS during batch ingest",
    )
    parser.add_argument(
        "--skip-asset-db-publish",
        action="store_true",
        help="Skip writing GeoTIFF asset metadata to Ocotillo DB during batch ingest",
    )
    parser.add_argument(
        "--skip-stac-uploads",
        action="store_true",
        help="Skip writing STAC payloads and loading them into pgstac during batch ingest",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Debug-level logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    ingest_results = run_batch(
        mapping_path=args.mapping,
        gcs_bucket=args.bucket,
        root_override=args.root,
        dry_run=args.dry_run,
        limit=args.limit,
        survey_filter=args.survey,
        stage_filter=args.stage,
        skip_soundings_upload=args.skip_soundings_upload,
        skip_asset_db_publish=args.skip_asset_db_publish,
        skip_stac_uploads=args.skip_stac_uploads,
    )

    if not args.dry_run:
        logger.info("Returned %d ingest results", len(ingest_results))


if __name__ == "__main__":
    main()
