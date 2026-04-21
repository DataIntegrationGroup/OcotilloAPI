# flake8: noqa: E501
from __future__ import annotations

import base64
import csv
import hashlib
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from google.cloud import storage

logger = logging.getLogger(__name__)

SHAPEFILE_SIDECAR_EXTS = {".dbf", ".shx", ".prj", ".cpg", ".sbn", ".sbx"}
GEOSOFT_SIDECAR_EXTS = {".gi", ".zon", ".map"}
ALL_SIDECAR_EXTS = SHAPEFILE_SIDECAR_EXTS | GEOSOFT_SIDECAR_EXTS


def _get_sidecar_parent_stem(filename: str, ext: str) -> str | None:
    if ext in SHAPEFILE_SIDECAR_EXTS:
        stem = Path(filename).stem
        return f"{stem}.shp"

    if ext == ".gi":
        if filename.endswith(".grd.gi") or filename.endswith(".tif.gi"):
            return filename[:-3]
        return None

    if ext in {".zon", ".map"}:
        stem = Path(filename).stem
        return f"{stem}.grd"

    return None


@dataclass
class FileResult:
    source_path: str
    gcs_path: str
    status: str
    file_size_bytes: int = 0
    upload_duration_seconds: float = 0.0
    error_message: str = ""


@dataclass
class UploadArtifact:
    local_path: str
    gcs_path: str
    cleanup_path: str | None = None


class MigrationRunner:
    """Shared migration workflow for AEM MOVE rows."""

    def __init__(
        self,
        mapping_path: str,
        bucket_name: str,
        root_override: str | None = None,
    ):
        self.mapping_path = mapping_path
        self.bucket_name = bucket_name
        self.root_override = root_override

        self.df = pd.read_csv(mapping_path)
        logger.info("Loaded mapping CSV: %d rows from %s", len(self.df), mapping_path)

        self.gcs_client = storage.Client()
        self.bucket = self.gcs_client.bucket(bucket_name)

        self.results: list[FileResult] = []
        self.failed_rows: list[dict] = []
        self.retry_list: list[str] = []

        if self.root_override is None:
            self._detected_root = self._detect_root()
        else:
            self._detected_root = self.root_override

        move_mask = self.df["action"] == "MOVE"
        self._move_filenames = set(self.df.loc[move_mask, "file_name"].values)

    def _detect_root(self) -> str | None:
        paths = self.df["source_path"].dropna().head(20).tolist()
        if not paths:
            return None
        prefix = os.path.commonpath([p.replace("\\", "/") for p in paths])
        logger.info("Auto-detected source root: %s", prefix)
        return prefix

    def _filtered_df(
        self,
        survey_filter: str | None = None,
        stage_filter: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        df = self.df.copy()
        if survey_filter:
            df = df[df["survey_id"] == survey_filter]
            logger.info("Filtered to survey: %s (%d rows)", survey_filter, len(df))
        if stage_filter:
            df = df[df["processing_stage"] == stage_filter]
            logger.info("Filtered to stage: %s (%d rows)", stage_filter, len(df))
        if limit is not None:
            df = df.head(limit)
            logger.info("Limited to first %d rows", limit)
        return df

    def get_filtered_rows(
        self,
        survey_filter: str | None = None,
        stage_filter: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self._filtered_df(survey_filter, stage_filter, limit)

    def resolve_source_path(self, source_path: str) -> str:
        if self.root_override is None:
            return source_path
        if os.path.exists(source_path):
            return source_path

        if self._detected_root:
            normalized_source = source_path.replace("\\", "/")
            normalized_detected = self._detected_root.replace("\\", "/")
            if normalized_source.startswith(normalized_detected):
                relative = normalized_source[len(normalized_detected) :].lstrip("/")
                return os.path.join(self.root_override, relative)
        return source_path

    def check_exists(self, gcs_path: str, expected_size: int) -> bool:
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
        md5 = hashlib.md5()
        with open(filepath, "rb") as stream:
            for chunk in iter(lambda: stream.read(8192), b""):
                md5.update(chunk)
        return base64.b64encode(md5.digest()).decode("utf-8")

    def _convert_kmz_to_geopackage(self, source_path: str) -> str:
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise RuntimeError(
                "KMZ upload requires geopandas to convert KMZ to GeoPackage."
            ) from exc

        fd, gpkg_path = tempfile.mkstemp(suffix=".gpkg")
        os.close(fd)
        try:
            try:
                gdf = gpd.read_file(source_path, driver="LIBKML")
            except Exception:
                gdf = gpd.read_file(source_path, driver="KML")
            gdf.to_file(gpkg_path, driver="GPKG")
        except Exception as exc:
            if os.path.exists(gpkg_path):
                os.unlink(gpkg_path)
            raise RuntimeError(
                f"KMZ to GeoPackage conversion failed for {source_path}: {exc}"
            ) from exc
        return gpkg_path

    def _upload_artifact(
        self, source_path: str, artifact: UploadArtifact
    ) -> FileResult:
        file_size = os.path.getsize(artifact.local_path)

        if self.check_exists(artifact.gcs_path, file_size):
            logger.debug("Already exists, skipping: %s", artifact.gcs_path)
            return FileResult(
                source_path=source_path,
                gcs_path=artifact.gcs_path,
                status="skipped_exists",
                file_size_bytes=file_size,
            )

        t0 = time.monotonic()
        try:
            blob = self.bucket.blob(artifact.gcs_path)
            blob.upload_from_filename(artifact.local_path)
            duration = time.monotonic() - t0
        except Exception as exc:
            duration = time.monotonic() - t0
            logger.error(
                "Upload failed: %s → %s — %s",
                source_path,
                artifact.gcs_path,
                exc,
            )
            return FileResult(
                source_path=source_path,
                gcs_path=artifact.gcs_path,
                status="failed",
                file_size_bytes=file_size,
                upload_duration_seconds=duration,
                error_message=str(exc),
            )

        try:
            local_md5 = self._compute_md5(artifact.local_path)
            blob.reload()
            remote_md5 = blob.md5_hash
            if remote_md5 and local_md5 != remote_md5:
                logger.warning(
                    "CHECKSUM MISMATCH: %s (local=%s, remote=%s) — adding to retry list",
                    artifact.gcs_path,
                    local_md5,
                    remote_md5,
                )
                self.retry_list.append(artifact.gcs_path)
        except Exception as exc:
            logger.warning(
                "Checksum verification failed for %s: %s",
                artifact.gcs_path,
                exc,
            )

        logger.info(
            "Uploaded: %s (%.1f MB, %.1fs)",
            artifact.gcs_path,
            file_size / 1e6,
            duration,
        )
        return FileResult(
            source_path=source_path,
            gcs_path=artifact.gcs_path,
            status="uploaded",
            file_size_bytes=file_size,
            upload_duration_seconds=duration,
        )

    def upload_file(self, source_path: str, gcs_path: str) -> FileResult:
        artifact = UploadArtifact(local_path=source_path, gcs_path=gcs_path)
        try:
            primary_result = self._upload_artifact(source_path, artifact)
            if primary_result.status == "failed":
                return primary_result

            if source_path.lower().endswith(".kmz"):
                gpkg_path = None
                try:
                    gpkg_path = self._convert_kmz_to_geopackage(source_path)
                    gpkg_result = self._upload_artifact(
                        source_path,
                        UploadArtifact(
                            local_path=gpkg_path,
                            gcs_path=str(Path(gcs_path).with_suffix(".gpkg")),
                            cleanup_path=gpkg_path,
                        ),
                    )
                except Exception as exc:
                    gpkg_result = FileResult(
                        source_path=source_path,
                        gcs_path=str(Path(gcs_path).with_suffix(".gpkg")),
                        status="failed",
                        error_message=str(exc),
                    )

                self.results.append(gpkg_result)
                if gpkg_result.status == "failed":
                    self.failed_rows.append(
                        {
                            "source_path": source_path,
                            "proposed_gcs_path": gpkg_result.gcs_path,
                            "file_name": Path(gpkg_result.gcs_path).name,
                        }
                    )
                if gpkg_path and os.path.exists(gpkg_path):
                    os.unlink(gpkg_path)

            return primary_result
        finally:
            if artifact.cleanup_path and os.path.exists(artifact.cleanup_path):
                os.unlink(artifact.cleanup_path)

    def _check_sidecar_parents(self, move_df: pd.DataFrame) -> None:
        for _, row in move_df.iterrows():
            ext = str(row["extension"]).lower()
            if ext not in ALL_SIDECAR_EXTS:
                continue
            parent_name = _get_sidecar_parent_stem(row["file_name"], ext)
            if parent_name and parent_name not in self._move_filenames:
                logger.warning(
                    "Sidecar %s has no parent '%s' in MOVE list — uploading anyway but verify manually",
                    row["file_name"],
                    parent_name,
                )

    def run(
        self,
        dry_run: bool = False,
        survey_filter: str | None = None,
        stage_filter: str | None = None,
        workers: int = 4,
        limit: int | None = None,
    ) -> None:
        df = self._filtered_df(survey_filter, stage_filter, limit)
        if len(df) == 0:
            logger.warning("No rows match the given filters — nothing to do")
            return

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
                else:
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

        move_df = df[df["action"] == "MOVE"].copy()
        logger.info(
            "Files to upload: %d (%.1f GB)",
            len(move_df),
            move_df["size_bytes"].sum() / 1e9,
        )

        if len(move_df) == 0:
            logger.info("No MOVE files to process")
            return

        self._check_sidecar_parents(move_df)

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

        try:
            from tqdm import tqdm

            progress = tqdm(total=len(move_df), desc="Uploading", unit="file")
        except ImportError:
            progress = None
            logger.info("tqdm not available — progress bar disabled")

        def _process_row(row):
            source = self.resolve_source_path(row["source_path"])
            result = self.upload_file(source, row["proposed_gcs_path"])
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
        logger.info("=" * 60)
        logger.info("DRY RUN — no files will be uploaded")
        logger.info("=" * 60)
        total_size = move_df["size_bytes"].sum()
        logger.info("Would upload %d files (%.1f GB)", len(move_df), total_size / 1e9)
        logger.info("— By survey:")
        for survey_id, group in move_df.groupby("survey_id"):
            logger.info(
                "  %s: %d files (%.1f GB)",
                survey_id,
                len(group),
                group["size_bytes"].sum() / 1e9,
            )
        logger.info("— By processing stage:")
        for stage, group in move_df.groupby("processing_stage"):
            logger.info(
                "  %s: %d files (%.1f GB)",
                stage,
                len(group),
                group["size_bytes"].sum() / 1e9,
            )
        for _, row in move_df.iterrows():
            self.results.append(
                FileResult(
                    source_path=row["source_path"],
                    gcs_path=row["proposed_gcs_path"],
                    status="dry_run",
                    file_size_bytes=int(row.get("size_bytes", 0)),
                )
            )

    def write_outputs(self) -> None:
        self._write_log_csv()
        self._write_failures_csv()
        self._write_summary()

    def _write_log_csv(self) -> None:
        path = "migration_log.csv"
        with open(path, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
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
            for result in self.results:
                writer.writerow(
                    {
                        "source_path": result.source_path,
                        "gcs_path": result.gcs_path,
                        "status": result.status,
                        "file_size_bytes": result.file_size_bytes,
                        "upload_duration_seconds": (
                            f"{result.upload_duration_seconds:.2f}"
                        ),
                        "error_message": result.error_message,
                    }
                )
        logger.info("Wrote %s (%d rows)", path, len(self.results))

    def _write_failures_csv(self) -> None:
        path = "migration_failures.csv"
        if not self.failed_rows:
            logger.info("No failures — %s not written", path)
            return
        pd.DataFrame(self.failed_rows).to_csv(path, index=False)
        logger.info("Wrote %s (%d failed files)", path, len(self.failed_rows))

    def _write_summary(self) -> None:
        path = "migration_summary.txt"
        lines: list[str] = []
        lines.append("=" * 70)
        lines.append("NMBGMR AEM Migration Summary")
        lines.append("=" * 70)
        lines.append("")

        status_counts: dict[str, int] = {}
        total_uploaded_bytes = 0
        for result in self.results:
            status_counts[result.status] = status_counts.get(result.status, 0) + 1
            if result.status == "uploaded":
                total_uploaded_bytes += result.file_size_bytes

        lines.append("Overall:")
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status:<20s} {count:>5d} files")
        lines.append(f"  Total uploaded size: {total_uploaded_bytes / 1e9:.2f} GB")
        lines.append("")

        lines.append("By survey:")
        by_survey = (
            self.df.groupby(["survey_id", "action"]).size().unstack(fill_value=0)
        )
        lines.append(by_survey.to_string())
        lines.append("")

        lines.append("-" * 70)
        lines.append(
            "FLAG_REVIEW breakdown (requires human decision before migration):"
        )
        lines.append("-" * 70)

        fr = self.df[self.df["action"] == "FLAG_REVIEW"]
        is_gdb = fr["detected_type"] == "geosoft_gdb"
        is_final_gdb = is_gdb & fr["action_notes"].str.contains(
            "Final", case=False, na=False
        )

        final_gdbs = fr[is_final_gdb]
        other_gdbs = fr[is_gdb & ~is_final_gdb]
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
            if len(group_df) > 0:
                lines.append(f"  {label:30s} {len(group_df):>3d} files — {note}")

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
            for detected_type, group_df in unknown_fr.groupby("detected_type"):
                lines.append(
                    f"  {detected_type:30s} {len(group_df):>3d} files — unlisted type, review manually"
                )

        lines.append("")

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
                "  Question: Are these preliminary, refined, or final inversions?"
            )
            lines.append("")

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

        hold = self.df[self.df["action"] == "HOLD"]
        if len(hold) > 0:
            lines.append("-" * 70)
            lines.append(f"HOLD ({len(hold)} files — blocked on external dependency):")
            lines.append("-" * 70)
            for notes, group in hold.groupby("action_notes"):
                lines.append(f"  {len(group):>3d} files — {notes[:100]}")
            lines.append("")

        if self.retry_list:
            lines.append("-" * 70)
            lines.append(
                f"CHECKSUM MISMATCHES ({len(self.retry_list)} files — re-upload recommended):"
            )
            lines.append("-" * 70)
            for gcs_path in self.retry_list:
                lines.append(f"  {gcs_path}")
            lines.append("")

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
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(summary_text)
        logger.info("Wrote %s", path)
        print(summary_text)
