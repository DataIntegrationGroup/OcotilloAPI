"""
aem_batch.py — Batch runner for the NMBGMR AEM ingest pipeline

Connects the migration script (aem_migrate.py) to the ingest pipeline
(aem_ingest).  Reads gcs_path_mapping.csv, filters to ingestible file
types (seogi_rho, aarhus_bylayer, agf_lci_csv), resolves provenance
for each file, and calls run_ingest() with the correct parameters.

Run sequence:
  1. aem_migrate.py  — copies all files from shared drive to GCS
  2. aem_batch.py    — reads same CSV, ingests inversion files into PostGIS
  3. PostGIS + Parquet + STAC are now populated and GeoServer-ready

Usage:
  # See what would be ingested without touching anything
  aem-batch --mapping gcs_path_mapping.csv --db-conn ... --bucket ... --dry-run

  # Test with 2 files from one survey
  aem-batch --mapping gcs_path_mapping.csv --db-conn ... --bucket ... --limit 2 --survey estancia_2025

  # Full run — all ingestible files
  aem-batch --mapping gcs_path_mapping.csv --db-conn ... --bucket ...

Authors: Marissa (data curator), Jake (platform engineer)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provenance resolution
# ---------------------------------------------------------------------------

# Maps detected_type from the mapper CSV to the ingest pipeline's format key
# and the provenance values it needs.  The mapper already knows survey_id
# and processing_stage — but inversion_code and contractor are not in the CSV,
# so we resolve them from the detected_type + survey_id combination.

INGESTIBLE_TYPES = {"seogi_rho", "aarhus_bylayer", "agf_lci_csv"}

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

        raw_files.append({
            "file": fname,
            "gcs_path": row["proposed_gcs_path"],
            "flight_id": flight_id,
            "size_bytes": int(row.get("size_bytes", 0)),
            "normalization_needed": row.get("normalization_needed", "N") == "Y",
        })

    return raw_files


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------


def run_batch(
    mapping_path: str,
    db_conn_string: str,
    gcs_bucket: str,
    root_override: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    survey_filter: str | None = None,
    stage_filter: str | None = None,
) -> list[dict]:
    """Run the ingest pipeline for all ingestible files in the mapping CSV.

    Args:
        mapping_path: Path to gcs_path_mapping.csv
        db_conn_string: PostgreSQL connection string
        gcs_bucket: GCS bucket name
        root_override: Override source_path root (for personal Drive copies)
        dry_run: Show what would happen without running anything
        limit: Only process this many files (for testing)
        survey_filter: Only process this survey_id
        stage_filter: Only process this processing_stage

    Returns:
        List of STAC item dicts (empty list in dry-run mode).
    """
    df = pd.read_csv(mapping_path)
    logger.info("Loaded mapping CSV: %d total rows", len(df))

    # Filter to ingestible types with MOVE action
    mask = (
        df["detected_type"].isin(INGESTIBLE_TYPES)
        & (df["action"] == "MOVE")
    )
    ingest_df = df[mask].copy()
    logger.info("Ingestible files: %d", len(ingest_df))

    # Apply filters
    if survey_filter:
        ingest_df = ingest_df[ingest_df["survey_id"] == survey_filter]
        logger.info("Filtered to survey '%s': %d files", survey_filter, len(ingest_df))
    if stage_filter:
        ingest_df = ingest_df[ingest_df["processing_stage"] == stage_filter]
        logger.info("Filtered to stage '%s': %d files", stage_filter, len(ingest_df))

    if len(ingest_df) == 0:
        logger.warning("No ingestible files match filters — nothing to do")
        return []

    # Apply limit
    if limit is not None:
        ingest_df = ingest_df.head(limit)
        logger.info("Limited to first %d files", limit)

    # Sort by survey then filename for predictable order
    ingest_df = ingest_df.sort_values(["survey_id", "file_name"]).reset_index(drop=True)

    # ----- Dry run -----
    if dry_run:
        return _dry_run(ingest_df, df, db_conn_string, gcs_bucket)

    # ----- Live run -----
    from aem_ingest.pipeline import run_ingest
    from aem_ingest.schemas import (
        IngestConfig,
        InversionCode,
        ProcessingStage,
        SkytemSystem,
    )

    stac_items = []
    succeeded = 0
    failed = 0
    errors = []

    for idx, (_, row) in enumerate(ingest_df.iterrows()):
        file_num = idx + 1
        total = len(ingest_df)
        filename = row["file_name"]
        survey_id = row["survey_id"]
        detected_type = row["detected_type"]

        logger.info(
            "=" * 60 + "\n[%d/%d] %s — %s / %s",
            file_num, total, filename, survey_id, detected_type,
        )

        try:
            # Resolve provenance
            prov = resolve_provenance(detected_type, survey_id)
            system = resolve_system(detected_type, filename)

            # Resolve source path
            source_path = row["source_path"]
            if root_override and not os.path.exists(source_path):
                # Try substituting root
                common = os.path.commonpath(
                    [p.replace("\\", "/") for p in df["source_path"].head(20)]
                )
                relative = source_path.replace("\\", "/").replace(
                    common.replace("\\", "/"), ""
                ).lstrip("/")
                source_path = os.path.join(root_override, relative)

            # Build raw file list for this survey (for manifest)
            raw_files = build_raw_file_list(df, survey_id)

            # Build IngestConfig
            config = IngestConfig(
                filepath=source_path,
                survey_id=survey_id,
                processing_stage=ProcessingStage(row["processing_stage"]),
                inversion_code=InversionCode(prov["inversion_code"]),
                contractor=prov["contractor"],
                db_conn_string=db_conn_string,
                gcs_bucket=gcs_bucket,
                source_gcs_path=row["proposed_gcs_path"],
                flight_id=None,  # auto-extracted from filename by parser
                system=SkytemSystem(system) if system else None,
            )

            # Run ingest
            t0 = time.monotonic()
            stac_item = run_ingest(
                config,
                raw_file_paths=raw_files,
                raw_manifest_notes=(
                    f"Generated by aem_batch.py during batch ingest. "
                    f"{len(raw_files)} raw files for survey {survey_id}."
                ),
            )
            duration = time.monotonic() - t0

            stac_items.append(stac_item)
            succeeded += 1
            logger.info(
                "[%d/%d] SUCCESS: %s → %s (%.1fs)",
                file_num, total, filename, stac_item["id"], duration,
            )

        except Exception as e:
            failed += 1
            errors.append({"file": filename, "survey": survey_id, "error": str(e)})
            logger.exception(
                "[%d/%d] FAILED: %s — %s", file_num, total, filename, e,
            )
            # Continue to next file — don't abort the batch
            continue

    # ----- Summary -----
    logger.info("=" * 60)
    logger.info("BATCH COMPLETE: %d succeeded, %d failed, %d total",
                succeeded, failed, len(ingest_df))

    if errors:
        logger.error("Failed files:")
        for err in errors:
            logger.error("  %s (%s): %s", err["file"], err["survey"], err["error"])

    # Write STAC items to JSON for downstream catalog registration
    if stac_items:
        stac_output = f"batch_stac_items_{int(time.time())}.json"
        with open(stac_output, "w") as f:
            json.dump(stac_items, f, indent=2, default=str)
        logger.info("STAC items written to %s", stac_output)

    return stac_items


def _dry_run(
    ingest_df: pd.DataFrame,
    full_df: pd.DataFrame,
    db_conn_string: str,
    gcs_bucket: str,
) -> list[dict]:
    """Show what would be ingested without running anything."""
    print("=" * 70)
    print("DRY RUN — nothing will be ingested")
    print("=" * 70)
    print()

    print(f"Files to ingest: {len(ingest_df)}")
    print(f"Total size: {ingest_df['size_bytes'].sum() / 1e6:.1f} MB")
    print(f"Database: {db_conn_string[:40]}...")
    print(f"GCS bucket: {gcs_bucket}")
    print()

    # By survey
    print("By survey:")
    for survey_id, group in ingest_df.groupby("survey_id"):
        raw_count = len(
            full_df[
                (full_df["survey_id"] == survey_id)
                & (full_df["detected_type"] == "geotech_raw_csv")
                & (full_df["action"] == "MOVE")
            ]
        )
        print(f"  {survey_id}: {len(group)} inversion files, {raw_count} raw files for manifest")
    print()

    # File-by-file preview
    print("Files that would be ingested:")
    print("-" * 70)
    for idx, (_, row) in enumerate(ingest_df.iterrows()):
        detected_type = row["detected_type"]
        survey_id = row["survey_id"]
        try:
            prov = resolve_provenance(detected_type, survey_id)
            system = resolve_system(detected_type, row["file_name"])
        except ValueError as e:
            prov = {"inversion_code": "UNKNOWN", "contractor": "UNKNOWN"}
            system = None

        system_str = f" system={system}" if system else ""

        print(
            f"  [{idx + 1:2d}] {row['file_name']}\n"
            f"       survey={survey_id}  stage={row['processing_stage']}\n"
            f"       code={prov['inversion_code']}  contractor={prov['contractor']}{system_str}\n"
            f"       source: {row['source_path'][:80]}...\n"
            f"       →  gcs: {row['proposed_gcs_path']}\n"
            f"       size: {row['size_human']}"
        )
        print()

    # Warnings
    norm = ingest_df[ingest_df["normalization_needed"] == "Y"]
    if len(norm) > 0:
        print(f"NOTE: {len(norm)} files have normalization_needed=Y")
        print("  These will be ingested as-is. Normalization (wellid prefix)")
        print("  is handled by the parser, not the migration script.")
        print()

    # Check for files not yet in GCS
    print("PRE-FLIGHT CHECK:")
    print("  Make sure aem_migrate.py has been run first —")
    print("  the ingest pipeline reads from local paths but records")
    print("  the GCS path as source_file provenance in PostGIS.")
    print()

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
        "--mapping", required=True,
        help="Path to gcs_path_mapping.csv",
    )
    parser.add_argument(
        "--db-conn", required=True,
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--bucket", required=True,
        help="GCS bucket name (e.g. nmbgmr-aem-data)",
    )
    parser.add_argument(
        "--root", default=None,
        help="Override source path root for local Drive copies",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be ingested without running anything",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only ingest the first N files (for testing — try --limit 2)",
    )
    parser.add_argument(
        "--survey", default=None,
        help="Only ingest files from this survey_id",
    )
    parser.add_argument(
        "--stage", default=None,
        help="Only ingest files from this processing_stage",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Debug-level logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    stac_items = run_batch(
        mapping_path=args.mapping,
        db_conn_string=args.db_conn,
        gcs_bucket=args.bucket,
        root_override=args.root,
        dry_run=args.dry_run,
        limit=args.limit,
        survey_filter=args.survey,
        stage_filter=args.stage,
    )

    if not args.dry_run:
        logger.info("Returned %d STAC items", len(stac_items))


if __name__ == "__main__":
    main()
