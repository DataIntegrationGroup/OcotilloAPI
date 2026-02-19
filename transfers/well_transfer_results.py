# ===============================================================================
# Copyright 2026 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from db import Thing
from db.engine import session_ctx
from transfers.util import (
    filter_non_transferred_wells,
    get_transferable_wells,
    read_csv,
    replace_nans,
)


@dataclass
class ValidationIssue:
    pointid: str
    table: str
    field: str
    error: str


@dataclass
class WellTransferResults:
    source_count: int
    committed_count: int
    transferred_count: int
    skipped_by_decision: list[str]
    validation_issue_wells: list[str]
    validation_issues: list[ValidationIssue]
    metrics_file: Path | None
    skipped_by_existing_destination: list[str]


class WellTransferResultsBuilder:
    """Build well transfer outcome summaries by comparing source and destination."""

    def __init__(
        self,
        pointids: list[str] | None = None,
        metrics_file: Path | None = None,
        output_dir: Path | None = None,
    ):
        self.pointids = set(pointids or [])
        self.metrics_file = metrics_file
        self.output_dir = output_dir or (Path("transfers") / "metrics")

    def build(self) -> WellTransferResults:
        source_df = self._load_source_wells()
        committed_df = self._load_committed_wells(source_df)
        committed_without_existing_df = filter_non_transferred_wells(committed_df)

        source_ids = self._point_ids(source_df)
        committed_ids = self._point_ids(committed_df)
        committed_without_existing_ids = self._point_ids(committed_without_existing_df)
        destination_ids = self._load_destination_ids()

        skipped_by_decision = sorted(source_ids - committed_ids)
        skipped_by_existing_destination = sorted(
            committed_ids - committed_without_existing_ids
        )
        transferred_ids = committed_ids & destination_ids
        missing_committed_ids = committed_ids - transferred_ids

        validation_issues = self._load_well_validation_issues(
            self._resolve_metrics_file()
        )
        validation_issue_ids = {
            issue.pointid for issue in validation_issues if issue.pointid in source_ids
        }
        validation_issue_wells = sorted(validation_issue_ids & missing_committed_ids)

        return WellTransferResults(
            source_count=len(source_ids),
            committed_count=len(committed_ids),
            transferred_count=len(transferred_ids),
            skipped_by_decision=skipped_by_decision,
            validation_issue_wells=validation_issue_wells,
            validation_issues=validation_issues,
            metrics_file=self._resolve_metrics_file(),
            skipped_by_existing_destination=skipped_by_existing_destination,
        )

    def write_reports(self, results: WellTransferResults) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

        summary_path = self.output_dir / f"well_transfer_results_{stamp}.txt"
        not_migrated_path = self.output_dir / f"wells_not_migrated_{stamp}.csv"
        validation_path = self.output_dir / f"wells_validation_issues_{stamp}.csv"
        already_exists_path = (
            self.output_dir / f"wells_already_in_destination_{stamp}.csv"
        )

        summary_lines = [
            "Well Transfer Results",
            f"source_count={results.source_count}",
            f"committed_count={results.committed_count}",
            f"transferred_count={results.transferred_count}",
            f"not_transferred_by_decision_count={len(results.skipped_by_decision)}",
            f"not_transferred_validation_count={len(results.validation_issue_wells)}",
            (
                f"already_in_destination_count="
                f"{len(results.skipped_by_existing_destination)}"
            ),
            (
                f"metrics_file={results.metrics_file}"
                if results.metrics_file
                else "metrics_file=None"
            ),
        ]
        summary_path.write_text("\n".join(summary_lines) + "\n")

        self._write_pointids(not_migrated_path, "pointid", results.skipped_by_decision)
        self._write_pointids(
            already_exists_path, "pointid", results.skipped_by_existing_destination
        )
        self._write_validation_issues(
            validation_path,
            [
                issue
                for issue in results.validation_issues
                if issue.pointid in set(results.validation_issue_wells)
            ],
        )

        return {
            "summary": summary_path,
            "not_migrated": not_migrated_path,
            "validation_issues": validation_path,
            "already_in_destination": already_exists_path,
        }

    def _load_source_wells(self) -> pd.DataFrame:
        wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
        ldf = read_csv("Location")
        ldf = ldf.drop(columns=["PointID", "SSMA_TimeStamp"], errors="ignore")
        wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")

        wdf = wdf[wdf["SiteType"] == "GW"]
        wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]
        wdf = replace_nans(wdf)

        if self.pointids:
            wdf = wdf[wdf["PointID"].isin(self.pointids)]

        return wdf

    def _load_committed_wells(self, source_df: pd.DataFrame) -> pd.DataFrame:
        committed_df = get_transferable_wells(source_df)
        if self.pointids:
            committed_df = committed_df[committed_df["PointID"].isin(self.pointids)]

        duplicates = committed_df["PointID"].duplicated(keep=False)
        if duplicates.any():
            duplicate_ids = set(committed_df.loc[duplicates, "PointID"].tolist())
            committed_df = committed_df[~committed_df["PointID"].isin(duplicate_ids)]

        return committed_df.sort_values("PointID")

    @staticmethod
    def _point_ids(df: pd.DataFrame) -> set[str]:
        if df.empty:
            return set()
        return set(df["PointID"].dropna().astype(str).unique().tolist())

    def _load_destination_ids(self) -> set[str]:
        with session_ctx() as session:
            ids = session.execute(
                select(Thing.name).where(Thing.thing_type == "water well")
            ).scalars()
            thing_names = {str(name) for name in ids if name}

        if self.pointids:
            thing_names = thing_names & self.pointids

        return thing_names

    def _resolve_metrics_file(self) -> Path | None:
        if self.metrics_file:
            return self.metrics_file

        metrics_dir = Path("transfers") / "metrics"
        candidates = sorted(
            metrics_dir.glob("metrics_*.csv"), key=lambda p: p.stat().st_mtime
        )
        if not candidates:
            return None
        return candidates[-1]

    @staticmethod
    def _load_well_validation_issues(
        metrics_file: Path | None,
    ) -> list[ValidationIssue]:
        if metrics_file is None or not metrics_file.exists():
            return []

        issues: list[ValidationIssue] = []
        current_model: str | None = None
        with metrics_file.open(newline="") as f:
            reader = csv.reader(f, delimiter="|")
            for row in reader:
                if not row:
                    continue

                if len(row) >= 5 and row[0] not in {"model", "PointID"}:
                    current_model = row[0]
                    continue

                if row[0] == "PointID":
                    continue

                if len(row) < 4:
                    continue

                if current_model != "Well":
                    continue

                pointid, table, field, error = row[0], row[1], row[2], row[3]
                if table != "WellData":
                    continue
                if "Validation Error" not in error:
                    continue
                issues.append(
                    ValidationIssue(
                        pointid=pointid,
                        table=table,
                        field=field,
                        error=error,
                    )
                )
        return issues

    @staticmethod
    def _write_pointids(path: Path, header: str, pointids: list[str]) -> None:
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([header])
            for pointid in pointids:
                writer.writerow([pointid])

    @staticmethod
    def _write_validation_issues(path: Path, issues: list[ValidationIssue]) -> None:
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["pointid", "table", "field", "error"])
            for issue in issues:
                writer.writerow([issue.pointid, issue.table, issue.field, issue.error])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transfer results for wells.")
    parser.add_argument(
        "--metrics-file",
        type=Path,
        default=None,
        help="Optional metrics CSV to use for validation issue extraction.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("transfers") / "metrics",
        help="Directory where result files are written.",
    )
    parser.add_argument(
        "--pointids",
        default=None,
        help="Optional comma-separated list of PointID values to scope the report.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    pointids = args.pointids.split(",") if args.pointids else None
    builder = WellTransferResultsBuilder(
        pointids=pointids,
        metrics_file=args.metrics_file,
        output_dir=args.output_dir,
    )
    results = builder.build()
    outputs = builder.write_reports(results)

    print(f"Source wells: {results.source_count}")
    print(f"Committed to migrate: {results.committed_count}")
    print(f"Successfully transferred: {results.transferred_count}")
    print(
        f"Not transferred (decided not to migrate): {len(results.skipped_by_decision)}"
    )
    print(f"Not transferred (validation issues): {len(results.validation_issue_wells)}")
    print(
        f"Already in destination before migration filter: "
        f"{len(results.skipped_by_existing_destination)}"
    )
    print(f"Summary file: {outputs['summary']}")
    print(f"Not migrated wells file: {outputs['not_migrated']}")
    print(f"Validation issue wells file: {outputs['validation_issues']}")
    print(f"Already-in-destination wells file: {outputs['already_in_destination']}")

    print("\nWells not transferred (decided not to migrate):")
    for pointid in results.skipped_by_decision:
        print(pointid)

    print("\nWells not transferred (data validation issues):")
    for pointid in results.validation_issue_wells:
        print(pointid)


if __name__ == "__main__":
    main()
