"""
aem_migrate.py — NMBGMR AEM Data Sharing Platform file migration

Reads the pre-generated gcs_path_mapping.csv (from aem_gcs_mapper.py) and
copies files from the local shared drive to Google Cloud Storage.

Key design decisions:
  - COPY only, never move or delete source files.  The shared drive remains
    the master copy until GCS is verified and the team agrees to cut over.
  - Only rows with action == 'MOVE' are uploaded.  FLAG_REVIEW and
    FLAG_UNKNOWN files require a human decision first — uploading them
    would create files in GCS that nobody has verified belong there.
  - normalization_needed == 'Y' files ARE uploaded (they're valid files
    in valid locations) but logged with a warning.  The normalization
    (renaming, wellid prefixing, CRS tagging) happens later in the
    ingest pipeline, not during migration.
  - Resumable: checks if GCS object already exists with matching size
    before uploading.  Safe to re-run after interruption.
  - Checksum verification: MD5 comparison after each upload.
  - Sidecar file warnings: .gi/.zon/.map (Geosoft) and .dbf/.shx/.prj
    etc. (shapefile) sidecars are useless without their parent file.
    The script warns if a parent is missing from the MOVE list but
    uploads the sidecar anyway — better to have it in GCS than not.

Usage:
  python aem_migrate.py --mapping gcs_path_mapping.csv --bucket nmbgmr-aem-data
  python aem_migrate.py --mapping gcs_path_mapping.csv --bucket nmbgmr-aem-data --dry-run
  python aem_migrate.py --mapping gcs_path_mapping.csv --bucket nmbgmr-aem-data --survey estancia_2025
  python aem_migrate.py --mapping gcs_path_mapping.csv --bucket nmbgmr-aem-data --root "G:\\My Drive\\NM AEM Exploration"

Authors: Marissa (data curator), Jake (platform engineer)
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from google.cloud import storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sidecar file detection
# ---------------------------------------------------------------------------

# Shapefile sidecars — meaningless without the parent .shp
SHAPEFILE_SIDECAR_EXTS = {".dbf", ".shx", ".prj", ".cpg", ".sbn", ".sbx"}

# Geosoft sidecars — meaningless without their parent GRD/GDB/TIF
GEOSOFT_SIDECAR_EXTS = {".gi", ".zon", ".map"}

# Combined set for quick membership check
ALL_SIDECAR_EXTS = SHAPEFILE_SIDECAR_EXTS | GEOSOFT_SIDECAR_EXTS


def _get_sidecar_parent_stem(filename: str, ext: str) -> str | None:
    """Determine the parent file stem for a sidecar file.

    Shapefile sidecars share the exact stem: CNMECLINES.shp → CNMECLINES.dbf
    Geosoft .gi sidecars append to the parent name: GL250194_CVG.grd.gi → parent is GL250194_CVG.grd
    Geosoft .zon/.map sidecars share stem or are loosely associated.

    Returns the expected parent filename (without path), or None if not a sidecar.
    """
    if ext in SHAPEFILE_SIDECAR_EXTS:
        # Parent is same stem + .shp
        stem = Path(filename).stem
        return f"{stem}.shp"

    if ext == ".gi":
        # .gi appends to parent: foo.grd.gi → parent is foo.grd
        # Also: foo.tif.gi → parent is foo.tif
        if filename.endswith(".grd.gi"):
            return filename[:-3]  # strip .gi
        if filename.endswith(".tif.gi"):
            return filename[:-3]
        return None

    if ext in (".zon", ".map"):
        # .zon and .map share stem with parent GRD
        stem = Path(filename).stem
        return f"{stem}.grd"

    return None


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class FileResult:
    """Result of processing a single file."""

    source_path: str
    gcs_path: str
    status: str  # uploaded | skipped_exists | skipped_action | failed | dry_run
    file_size_bytes: int = 0
    upload_duration_seconds: float = 0.0
    error_message: str = ""


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


class MigrationRunner:
    """Orchestrates the file migration from local drive to GCS.

    Reads the mapping CSV, filters by action/survey/stage, checks for
    existing uploads, copies files, verifies checksums, and writes
    output logs.
    """

    def __init__(
        self,
        mapping_path: str,
        bucket_name: str,
        root_override: str | None = None,
    ):
        """
        Args:
            mapping_path: Path to gcs_path_mapping.csv
            bucket_name: GCS bucket name
            root_override: If provided, replaces the source_path prefix
                from the CSV with this root.  Useful when running against
                a personal Drive copy instead of the original Shared Drive.
        """
        self.mapping_path = mapping_path
        self.bucket_name = bucket_name
        self.root_override = root_override

        self.df = pd.read_csv(mapping_path)
        logger.info("Loaded mapping CSV: %d rows from %s", len(self.df), mapping_path)

        self.gcs_client = storage.Client()
        self.bucket = self.gcs_client.bucket(bucket_name)

        # Results tracking
        self.results: list[FileResult] = []
        self.failed_rows: list[dict] = []
        self.retry_list: list[str] = []  # checksum mismatches

        # Detect root from CSV if not overridden
        if self.root_override is None:
            self._detected_root = self._detect_root()
        else:
            self._detected_root = self.root_override

        # Build set of MOVE file names for sidecar parent checking
        move_mask = self.df["action"] == "MOVE"
        self._move_filenames = set(self.df.loc[move_mask, "file_name"].values)

    def _detect_root(self) -> str | None:
        """Try to detect the common root prefix from source_path values."""
        paths = self.df["source_path"].dropna().head(20).tolist()
        if not paths:
            return None
        # Find common prefix
        prefix = os.path.commonpath([p.replace("\\", "/") for p in paths])
        logger.info("Auto-detected source root: %s", prefix)
        return prefix

    def _resolve_source_path(self, source_path: str) -> str:
        """Resolve the source path, applying root override if set."""
        if self.root_override is None:
            return source_path

        # The CSV contains paths like G:\Shared drives\NM AEM Exploration\...
        # If root_override is set, we need to replace the prefix.
        # Strategy: find the survey folder part and prepend the new root.
        # The survey_folder column tells us where the survey-specific part starts.
        # But simpler: just return the path as-is if it exists, or try root override.
        if os.path.exists(source_path):
            return source_path

        # Try replacing the detected root with the override
        if self._detected_root:
            normalized_source = source_path.replace("\\", "/")
            normalized_detected = self._detected_root.replace("\\", "/")
            if normalized_source.startswith(normalized_detected):
                relative = normalized_source[len(normalized_detected) :].lstrip("/")
                new_path = os.path.join(self.root_override, relative)
                return new_path

        return source_path

    # ----- GCS operations -----

    def check_exists(self, gcs_path: str, expected_size: int) -> bool:
        """Check if a GCS object already exists with matching size.

        This makes the script resumable — if interrupted and re-run,
        already-uploaded files are skipped.
        """
        blob = self.bucket.blob(gcs_path)
        if not blob.exists():
            return False
        blob.reload()
        if blob.size == expected_size:
            return True
        logger.warning(
            "GCS object exists but size differs: %s (GCS=%d, local=%d)",
            gcs_path,
            blob.size,
            expected_size,
        )
        return False

    def _compute_md5(self, filepath: str) -> str:
        """Compute MD5 hash of a local file, returned as base64."""
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return base64.b64encode(md5.digest()).decode("utf-8")

    def upload_file(self, source_path: str, gcs_path: str) -> FileResult:
        """Upload a single file to GCS with checksum verification.

        Returns a FileResult with status and timing.
        """
        try:
            file_size = os.path.getsize(source_path)
        except OSError as e:
            logger.error("Cannot access source file: %s — %s", source_path, e)
            return FileResult(
                source_path=source_path,
                gcs_path=gcs_path,
                status="failed",
                error_message=str(e),
            )

        # Check if already uploaded (resumable)
        if self.check_exists(gcs_path, file_size):
            logger.debug("Already exists, skipping: %s", gcs_path)
            return FileResult(
                source_path=source_path,
                gcs_path=gcs_path,
                status="skipped_exists",
                file_size_bytes=file_size,
            )

        # Upload
        t0 = time.monotonic()
        try:
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(source_path)
            duration = time.monotonic() - t0
        except Exception as e:
            duration = time.monotonic() - t0
            logger.error("Upload failed: %s → %s — %s", source_path, gcs_path, e)
            return FileResult(
                source_path=source_path,
                gcs_path=gcs_path,
                status="failed",
                file_size_bytes=file_size,
                upload_duration_seconds=duration,
                error_message=str(e),
            )

        # Checksum verification
        try:
            local_md5 = self._compute_md5(source_path)
            blob.reload()
            remote_md5 = blob.md5_hash
            if remote_md5 and local_md5 != remote_md5:
                logger.warning(
                    "CHECKSUM MISMATCH: %s (local=%s, remote=%s) — adding to retry list",
                    gcs_path,
                    local_md5,
                    remote_md5,
                )
                self.retry_list.append(gcs_path)
        except Exception as e:
            logger.warning("Checksum verification failed for %s: %s", gcs_path, e)

        logger.info(
            "Uploaded: %s (%.1f MB, %.1fs)",
            gcs_path,
            file_size / 1e6,
            duration,
        )

        return FileResult(
            source_path=source_path,
            gcs_path=gcs_path,
            status="uploaded",
            file_size_bytes=file_size,
            upload_duration_seconds=duration,
        )

    # ----- Sidecar validation -----

    def _check_sidecar_parents(self, move_df: pd.DataFrame) -> None:
        """Warn if any sidecar files in the MOVE list lack their parent file."""
        for _, row in move_df.iterrows():
            ext = row["extension"].lower()
            if ext not in ALL_SIDECAR_EXTS:
                continue
            parent_name = _get_sidecar_parent_stem(row["file_name"], ext)
            if parent_name is None:
                continue
            if parent_name not in self._move_filenames:
                logger.warning(
                    "Sidecar %s has no parent '%s' in MOVE list "
                    "— uploading anyway but verify manually",
                    row["file_name"],
                    parent_name,
                )

    # ----- Main run loop -----

    def run(
        self,
        dry_run: bool = False,
        survey_filter: str | None = None,
        stage_filter: str | None = None,
        workers: int = 4,
    ) -> None:
        """Process the mapping CSV and upload files to GCS.

        Args:
            dry_run: Log actions without uploading.
            survey_filter: Only process this survey_id.
            stage_filter: Only process this processing_stage.
            workers: Number of parallel upload threads.
        """
        df = self.df.copy()

        # Apply filters
        if survey_filter:
            df = df[df["survey_id"] == survey_filter]
            logger.info("Filtered to survey: %s (%d rows)", survey_filter, len(df))
        if stage_filter:
            df = df[df["processing_stage"] == stage_filter]
            logger.info("Filtered to stage: %s (%d rows)", stage_filter, len(df))

        if len(df) == 0:
            logger.warning("No rows match the given filters — nothing to do")
            return

        # Log skipped actions with specific reasons
        for action in ["FLAG_REVIEW", "FLAG_UNKNOWN", "HOLD", "SKIP"]:
            action_df = df[df["action"] == action]
            for _, row in action_df.iterrows():
                if action == "FLAG_REVIEW":
                    logger.info(
                        "Skipped — requires human decision before migration: %s — %s",
                        row["file_name"],
                        row.get("action_notes", ""),
                    )
                elif action == "FLAG_UNKNOWN":
                    logger.info(
                        "Skipped — archive must be opened and re-mapped: %s",
                        row["file_name"],
                    )
                elif action == "HOLD":
                    logger.info(
                        "Skipped — blocked on external dependency: %s — %s",
                        row["file_name"],
                        row.get("action_notes", ""),
                    )
                elif action == "SKIP":
                    logger.info(
                        "Skipped — system file, do not migrate: %s",
                        row["file_name"],
                    )

                self.results.append(
                    FileResult(
                        source_path=row["source_path"],
                        gcs_path=row.get("proposed_gcs_path", ""),
                        status="skipped_action",
                        file_size_bytes=int(row.get("size_bytes", 0)),
                    )
                )

        # Filter to MOVE only
        move_df = df[df["action"] == "MOVE"].copy()
        logger.info(
            "Files to upload: %d (%.1f GB)",
            len(move_df),
            move_df["size_bytes"].sum() / 1e9,
        )

        if len(move_df) == 0:
            logger.info("No MOVE files to process")
            return

        # Check sidecar parent relationships before uploading
        self._check_sidecar_parents(move_df)

        # Log normalization warnings
        norm_mask = move_df["normalization_needed"] == "Y"
        for _, row in move_df[norm_mask].iterrows():
            logger.warning(
                "Uploaded with normalization pending: %s — %s",
                row["file_name"],
                row.get("normalization_notes", ""),
            )

        if dry_run:
            self._dry_run(move_df)
            return

        # Upload with thread pool
        try:
            from tqdm import tqdm

            progress = tqdm(total=len(move_df), desc="Uploading", unit="file")
        except ImportError:
            progress = None
            logger.info("tqdm not available — progress bar disabled")

        def _process_row(row):
            source = self._resolve_source_path(row["source_path"])
            gcs_path = row["proposed_gcs_path"]
            result = self.upload_file(source, gcs_path)
            if result.status == "failed":
                self.failed_rows.append(row.to_dict())
            return result

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_row, row): idx
                for idx, (_, row) in enumerate(move_df.iterrows())
            }
            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                if progress:
                    progress.update(1)

        if progress:
            progress.close()

        logger.info("Upload complete: %d files processed", len(move_df))

    def _dry_run(self, move_df: pd.DataFrame) -> None:
        """Log what would be uploaded without actually uploading."""
        logger.info("=" * 60)
        logger.info("DRY RUN — no files will be uploaded")
        logger.info("=" * 60)

        total_size = move_df["size_bytes"].sum()
        logger.info("Would upload %d files (%.1f GB)", len(move_df), total_size / 1e9)

        # Breakdown by survey
        logger.info("— By survey:")
        for survey_id, group in move_df.groupby("survey_id"):
            logger.info(
                "  %s: %d files (%.1f GB)",
                survey_id,
                len(group),
                group["size_bytes"].sum() / 1e9,
            )

        # Breakdown by processing stage
        logger.info("— By processing stage:")
        for stage, group in move_df.groupby("processing_stage"):
            logger.info(
                "  %s: %d files (%.1f GB)",
                stage,
                len(group),
                group["size_bytes"].sum() / 1e9,
            )

        # Record dry-run results
        for _, row in move_df.iterrows():
            self.results.append(
                FileResult(
                    source_path=row["source_path"],
                    gcs_path=row["proposed_gcs_path"],
                    status="dry_run",
                    file_size_bytes=int(row.get("size_bytes", 0)),
                )
            )

    # ----- Output files -----

    def write_outputs(self) -> None:
        """Write migration_log.csv, migration_failures.csv, and migration_summary.txt."""
        self._write_log_csv()
        self._write_failures_csv()
        self._write_summary()

    def _write_log_csv(self) -> None:
        """One row per file processed — uploaded, skipped, or failed."""
        path = "migration_log.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source_path",
                    "gcs_path",
                    "status",
                    "file_size_bytes",
                    "upload_duration_seconds",
                    "error_message",
                ],
            )
            writer.writeheader()
            for r in self.results:
                writer.writerow(
                    {
                        "source_path": r.source_path,
                        "gcs_path": r.gcs_path,
                        "status": r.status,
                        "file_size_bytes": r.file_size_bytes,
                        "upload_duration_seconds": f"{r.upload_duration_seconds:.2f}",
                        "error_message": r.error_message,
                    }
                )
        logger.info("Wrote %s (%d rows)", path, len(self.results))

    def _write_failures_csv(self) -> None:
        """Rows from input CSV that failed — for re-run."""
        path = "migration_failures.csv"
        if not self.failed_rows:
            logger.info("No failures — %s not written", path)
            return

        df = pd.DataFrame(self.failed_rows)
        df.to_csv(path, index=False)
        logger.info("Wrote %s (%d failed files)", path, len(self.failed_rows))

    def _write_summary(self) -> None:
        """Human-readable summary with FLAG_REVIEW breakdown."""
        path = "migration_summary.txt"
        lines: list[str] = []
        lines.append("=" * 70)
        lines.append("NMBGMR AEM Migration Summary")
        lines.append("=" * 70)
        lines.append("")

        # Overall counts
        status_counts: dict[str, int] = {}
        total_uploaded_bytes = 0
        for r in self.results:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
            if r.status == "uploaded":
                total_uploaded_bytes += r.file_size_bytes

        lines.append("Overall:")
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status:<20s} {count:>5d} files")
        lines.append(f"  Total uploaded size: {total_uploaded_bytes / 1e9:.2f} GB")
        lines.append("")

        # Breakdown by survey
        lines.append("By survey:")
        survey_results: dict[str, dict] = {}
        for r in self.results:
            # Find survey_id from the original CSV by matching source_path
            pass  # We'll use the DataFrame instead

        by_survey = (
            self.df.groupby(["survey_id", "action"]).size().unstack(fill_value=0)
        )
        lines.append(by_survey.to_string())
        lines.append("")

        # ----- FLAG_REVIEW breakdown by detected_type -----
        lines.append("-" * 70)
        lines.append(
            "FLAG_REVIEW breakdown (requires human decision before migration):"
        )
        lines.append("-" * 70)

        fr = self.df[self.df["action"] == "FLAG_REVIEW"]

        # Separate Final GDBs from other GDBs
        is_gdb = fr["detected_type"] == "geosoft_gdb"
        is_final_gdb = is_gdb & fr["action_notes"].str.contains(
            "Final", case=False, na=False
        )

        final_gdbs = fr[is_final_gdb]
        other_gdbs = fr[is_gdb & ~is_final_gdb]

        # Build type breakdown
        type_groups = [
            (
                "geosoft_gdb (FINAL)",
                final_gdbs,
                "HIGH PRIORITY — open and inspect before moving",
            ),
            (
                "geosoft_gdb (other)",
                other_gdbs,
                "Confirm file vs folder structure before move",
            ),
            (
                "pik_inversion",
                fr[fr["detected_type"] == "pik_inversion"],
                "Confirm processing stage with Ahsan/DBS&A",
            ),
            (
                "ahsan_inversion_csv",
                fr[fr["detected_type"] == "ahsan_inversion_csv"],
                "Confirm processing stage with Ahsan (per-line inversion CSVs)",
            ),
            (
                "geosoft_native_grd",
                fr[fr["detected_type"] == "geosoft_native_grd"],
                "Need GDAL conversion to GeoTIFF before ingest",
            ),
            (
                "grd_unknown_format",
                fr[fr["detected_type"] == "grd_unknown_format"],
                "Unknown GRD variant — investigate format",
            ),
            (
                "lfview",
                fr[fr["detected_type"] == "lfview"],
                "Request open re-export from DBS&A before archiving",
            ),
        ]

        for label, group_df, note in type_groups:
            if len(group_df) == 0:
                continue
            lines.append(f"  {label:30s} {len(group_df):>3d} files — {note}")

        # Catch any types not in our explicit list
        known_types = {
            "geosoft_gdb",
            "pik_inversion",
            "ahsan_inversion_csv",
            "geosoft_native_grd",
            "grd_unknown_format",
            "lfview",
        }
        unknown_fr = fr[~fr["detected_type"].isin(known_types)]
        if len(unknown_fr) > 0:
            for dt, group_df in unknown_fr.groupby("detected_type"):
                lines.append(
                    f"  {dt:30s} {len(group_df):>3d} files — unlisted type, review manually"
                )

        lines.append("")

        # ----- Final GDBs — high priority call-out -----
        if len(final_gdbs) > 0:
            lines.append("-" * 70)
            lines.append("HIGH PRIORITY: Final GDBs requiring inspection")
            lines.append("-" * 70)
            for _, row in final_gdbs.iterrows():
                lines.append(f"  {row['file_name']}")
                lines.append(f"    Survey: {row['survey_id']}")
                lines.append(f"    Path:   {row['source_path']}")
                lines.append(f"    Notes:  {row['action_notes']}")
            lines.append("")

        # ----- Ahsan CSVs — email-ready list -----
        ahsan_csvs = fr[fr["detected_type"] == "ahsan_inversion_csv"]
        if len(ahsan_csvs) > 0:
            lines.append("-" * 70)
            lines.append("ACTION: Confirm processing stage with Ahsan for these files:")
            lines.append("-" * 70)
            for _, row in ahsan_csvs.iterrows():
                lines.append(f"  {row['file_name']}")
            lines.append(f"  ({len(ahsan_csvs)} files total)")
            lines.append(f"  Survey: {ahsan_csvs['survey_id'].iloc[0]}")
            lines.append(
                f"  Question: Are these preliminary, refined, or final inversions?"
            )
            lines.append("")

        # ----- FLAG_UNKNOWN -----
        fu = self.df[self.df["action"] == "FLAG_UNKNOWN"]
        if len(fu) > 0:
            lines.append("-" * 70)
            lines.append(
                f"FLAG_UNKNOWN ({len(fu)} files — must be opened and re-mapped):"
            )
            lines.append("-" * 70)
            for _, row in fu.iterrows():
                lines.append(f"  {row['file_name']} — {row.get('action_notes', '')}")
            lines.append("")

        # ----- HOLD -----
        hold = self.df[self.df["action"] == "HOLD"]
        if len(hold) > 0:
            lines.append("-" * 70)
            lines.append(f"HOLD ({len(hold)} files — blocked on external dependency):")
            lines.append("-" * 70)
            # Group by reason
            for notes, group in hold.groupby("action_notes"):
                lines.append(f"  {len(group):>3d} files — {notes[:100]}")
            lines.append("")

        # ----- Checksum mismatches -----
        if self.retry_list:
            lines.append("-" * 70)
            lines.append(
                f"CHECKSUM MISMATCHES ({len(self.retry_list)} files — re-upload recommended):"
            )
            lines.append("-" * 70)
            for gcs_path in self.retry_list:
                lines.append(f"  {gcs_path}")
            lines.append("")

        # ----- Failed uploads -----
        if self.failed_rows:
            lines.append("-" * 70)
            lines.append(
                f"FAILED UPLOADS ({len(self.failed_rows)} files — see migration_failures.csv):"
            )
            lines.append("-" * 70)
            for row in self.failed_rows:
                lines.append(
                    f"  {row['file_name']} — {row.get('proposed_gcs_path', '')}"
                )
            lines.append("")

        # ----- Normalization pending -----
        norm = self.df[
            (self.df["action"] == "MOVE") & (self.df["normalization_needed"] == "Y")
        ]
        if len(norm) > 0:
            lines.append("-" * 70)
            lines.append(
                f"NORMALIZATION PENDING ({len(norm)} files uploaded but need cleanup before ingest):"
            )
            lines.append("-" * 70)
            for _, row in norm.iterrows():
                lines.append(
                    f"  {row['file_name']} — {row.get('normalization_notes', '')[:80]}"
                )
            lines.append("")

        summary_text = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(summary_text)
        logger.info("Wrote %s", path)

        # Also print to console
        print(summary_text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="NMBGMR AEM migration — copy files from shared drive to GCS"
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
        help=(
            "Local root path override. If the mapping CSV was generated "
            "against a Shared Drive but you're running against a personal "
            "Drive copy, set this to the new root. "
            "e.g. 'G:\\My Drive\\NM AEM Exploration'"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log all actions without uploading anything",
    )
    parser.add_argument(
        "--survey",
        default=None,
        help="Only migrate this survey_id (e.g. estancia_2025)",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help="Only migrate this processing_stage (e.g. preliminary_inversion)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel upload threads (default: 4)",
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

    runner = MigrationRunner(
        mapping_path=args.mapping,
        bucket_name=args.bucket,
        root_override=args.root,
    )

    runner.run(
        dry_run=args.dry_run,
        survey_filter=args.survey,
        stage_filter=args.stage,
        workers=args.workers,
    )

    runner.write_outputs()

    # Exit with error code if there were failures
    if runner.failed_rows:
        logger.error(
            "%d files failed — see migration_failures.csv", len(runner.failed_rows)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
