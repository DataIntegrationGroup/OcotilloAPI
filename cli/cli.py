# ===============================================================================
# Copyright 2025 ross
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
import os
import re
from collections import Counter, defaultdict
from enum import Enum
from pathlib import Path
from textwrap import shorten, wrap

import pandas as pd
import typer
from dotenv import load_dotenv

from cli.aem_ingest import app as aem_ingest_app

# CLI should load `.env` defaults without clobbering an explicitly prepared environment.
load_dotenv(override=False)
os.environ.setdefault("OCO_LOG_CONTEXT", "cli")

cli = typer.Typer(help="Command line interface for managing the application.")
water_levels = typer.Typer(help="Water-level utilities")
data_migrations = typer.Typer(help="Data migration utilities")
cli.add_typer(water_levels, name="water-levels")
cli.add_typer(data_migrations, name="data-migrations")

cli.add_typer(aem_ingest_app, name="aem-ingest")


class OutputFormat(str, Enum):
    json = "json"


class ThemeMode(str, Enum):
    auto = "auto"
    light = "light"
    dark = "dark"


class SmokePopulation(str, Enum):
    all = "all"
    agreed = "agreed"


PYGEOAPI_MATERIALIZED_VIEWS = (
    "ogc_latest_depth_to_water_wells",
    "ogc_water_elevation_wells",
    "ogc_avg_tds_wells",
    "ogc_depth_to_water_trend_wells",
    "ogc_water_well_summary",
    "ogc_major_chemistry_results",
    "ogc_minor_chemistry_wells",
)


def _resolve_theme(theme: ThemeMode) -> ThemeMode:
    if theme != ThemeMode.auto:
        return theme

    env_theme = os.environ.get("OCO_THEME", "").strip().lower()
    if env_theme in (ThemeMode.light.value, ThemeMode.dark.value):
        return ThemeMode(env_theme)

    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            bg = int(colorfgbg.split(";")[-1])
            return ThemeMode.light if bg >= 8 else ThemeMode.dark
        except (TypeError, ValueError):
            pass

    return ThemeMode.dark


def _validate_sql_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise typer.BadParameter(f"Invalid SQL identifier: {identifier!r}")
    return identifier


def _palette(theme: ThemeMode) -> dict[str, str]:
    mode = _resolve_theme(theme)
    if mode == ThemeMode.light:
        return {
            "ok": typer.colors.GREEN,
            "issue": typer.colors.RED,
            "accent": typer.colors.BLUE,
            "muted": typer.colors.BLACK,
            "field": typer.colors.RED,
        }
    return {
        "ok": typer.colors.GREEN,
        "issue": typer.colors.MAGENTA,
        "accent": typer.colors.BRIGHT_BLUE,
        "muted": typer.colors.BRIGHT_BLACK,
        "field": typer.colors.BRIGHT_YELLOW,
    }


@cli.command("initialize-lexicon")
def initialize_lexicon(
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from core.initializers import init_lexicon

    init_lexicon()


@cli.command("associate-assets")
def associate_assets_command(
    root_directory: str = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from cli.service_adapter import associate_assets

    associate_assets(root_directory)


@cli.command("restore-local-db")
def restore_local_db(
    source: str = typer.Argument(
        ...,
        help="Local .sql/.sql.gz path or gs://bucket/path.sql[.gz] URI.",
    ),
    db_name: str | None = typer.Option(
        None,
        "--db-name",
        help="Override POSTGRES_DB for the restore target.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from cli.db_restore import LocalDbRestoreError, restore_local_db_from_sql

    try:
        result = restore_local_db_from_sql(source, db_name=db_name)
    except LocalDbRestoreError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        "Restored "
        f"{result.source} into {result.db_name} "
        f"on {result.host}:{result.port} as {result.user}."
    )


@cli.command("transfer-results")
def transfer_results(
    summary_path: Path = typer.Option(
        Path("transfers") / "metrics" / "transfer_results_summary.md",
        "--summary-path",
        help="Output path for markdown summary table.",
    ),
    sample_limit: int = typer.Option(
        25,
        "--sample-limit",
        min=1,
        help="Max missing/extra key samples stored per transfer.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from transfers.transfer_results_builder import TransferResultsBuilder

    builder = TransferResultsBuilder(sample_limit=sample_limit)
    results = builder.build()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    TransferResultsBuilder.write_summary(summary_path, results)
    typer.echo(f"Wrote comparison summary: {summary_path}")
    typer.echo(f"Transfer comparisons: {len(results.results)}")


@cli.command("scoped-transfer")
def scoped_transfer(
    pointid: list[str] = typer.Option(
        ...,
        "--pointid",
        help="Legacy PointID to transfer. Repeat --pointid for multiple values.",
    ),
    only: list[str] = typer.Option(
        None,
        "--only",
        help="Optional transfer family to include. Repeat for multiple values.",
    ),
    skip: list[str] = typer.Option(
        None,
        "--skip",
        help="Optional transfer family to skip. Repeat for multiple values.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Plan the scoped transfer without writing any records.",
    ),
    output_format: OutputFormat | None = typer.Option(
        None,
        "--output",
        help="Optional output format",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from services.scoped_transfer import (
        ScopedTransferError,
        ScopedTransferOptions,
        format_scoped_transfer_json,
        run_scoped_transfer,
    )

    colors = _palette(theme)
    normalized_pointids = [
        pid.strip().upper() for pid in pointid if pid and pid.strip()
    ]

    if output_format != OutputFormat.json:
        # Print a quick status line so a long scoped run does not look stuck.
        verb = "Planning" if dry_run else "Starting"
        phase = "planning" if dry_run else "execution"
        typer.secho(
            f"{verb} scoped transfer for PointIDs: {', '.join(normalized_pointids)}",
            fg=colors["accent"],
            bold=True,
        )
        typer.secho(
            f"Validating requested scope and preparing {phase}...",
            fg=colors["muted"],
        )

    try:
        result = run_scoped_transfer(
            ScopedTransferOptions(
                pointids=pointid,
                only=only or [],
                skip=skip or [],
                dry_run=dry_run,
            )
        )
    except ScopedTransferError as exc:
        typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
        raise typer.Exit(1) from exc

    if output_format == OutputFormat.json:
        typer.echo(format_scoped_transfer_json(result))
        raise typer.Exit(result.exit_code)

    header = "[SCOPED TRANSFER] DRY RUN" if result.dry_run else "[SCOPED TRANSFER]"
    header_color = colors["ok"] if result.exit_code == 0 else colors["issue"]
    typer.secho(header, fg=header_color, bold=True)
    typer.secho("=" * 72, fg=colors["accent"])
    typer.secho(
        f"Requested PointIDs: {', '.join(result.pointids)}",
        fg=colors["accent"],
    )
    typer.secho(
        f"Selected families: {', '.join(result.selected_families)}",
        fg=colors["accent"],
    )
    if result.added_prerequisites:
        typer.secho(
            f"Auto-added prerequisites: {', '.join(result.added_prerequisites)}",
            fg=colors["muted"],
        )
    typer.echo()

    typer.secho("FAMILY SUMMARY", fg=colors["accent"], bold=True)
    for family_result in result.family_results:
        detail_parts = [f"rows={family_result.applicable_source_rows}"]
        if family_result.created is not None:
            detail_parts.append(f"created={family_result.created}")
        if family_result.skipped_existing is not None:
            detail_parts.append(f"skipped_existing={family_result.skipped_existing}")
        if family_result.added_as_prerequisite:
            detail_parts.append("prerequisite")
        if family_result.detail:
            detail_parts.append(family_result.detail)
        typer.secho(
            f"  {family_result.family:<28} {family_result.status:<10} {'  '.join(detail_parts)}",
            fg=(
                colors["ok"]
                if family_result.status in ("completed", "planned")
                else colors["muted"]
            ),
        )

    if result.validation_errors:
        typer.echo()
        typer.secho("VALIDATION ERRORS", fg=colors["issue"], bold=True)
        for error in result.validation_errors:
            typer.secho(f"  - {error}", fg=colors["issue"])

    if result.execution_error:
        typer.echo()
        typer.secho("EXECUTION ERROR", fg=colors["issue"], bold=True)
        typer.secho(result.execution_error, fg=colors["issue"])

    raise typer.Exit(result.exit_code)


@cli.command("compare-duplicated-welldata")
def compare_duplicated_welldata(
    pointid: list[str] = typer.Option(
        None,
        "--pointid",
        help="Optional PointID filter. Repeat --pointid for multiple values.",
    ),
    apply_transfer_filters: bool = typer.Option(
        True,
        "--apply-transfer-filters/--no-apply-transfer-filters",
        help=(
            "Apply WellTransferer-like pre-filters (GW + coordinates + transferable), "
            "excluding DB-dependent non-transferred filtering."
        ),
    ),
    summary_path: Path = typer.Option(
        Path("transfers") / "metrics" / "welldata_duplicate_comparison_summary.csv",
        "--summary-path",
        help="Output CSV path for duplicate PointID summary.",
    ),
    detail_path: Path = typer.Option(
        Path("transfers") / "metrics" / "welldata_duplicate_comparison_detail.csv",
        "--detail-path",
        help="Output CSV path for row x differing-column detail values.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from transfers.util import get_transferable_wells, read_csv, replace_nans

    df = read_csv("WellData", dtype={"OSEWelltagID": str})

    if apply_transfer_filters:
        if "LocationId" in df.columns:
            ldf = read_csv("Location")
            ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1, errors="ignore")
            df = df.join(ldf.set_index("LocationId"), on="LocationId")

        if "SiteType" in df.columns:
            df = df[df["SiteType"] == "GW"]

        if "Easting" in df.columns and "Northing" in df.columns:
            df = df[df["Easting"].notna() & df["Northing"].notna()]

        df = replace_nans(df)
        df = get_transferable_wells(df)
    else:
        df = replace_nans(df)

    if pointid:
        requested = {pid.strip() for pid in pointid if pid and pid.strip()}
        df = df[df["PointID"].isin(requested)]

    if "PointID" not in df.columns:
        typer.echo("WellData has no PointID column after filtering.")
        raise typer.Exit(code=1)

    dup_mask = df["PointID"].duplicated(keep=False)
    dup_df = df.loc[dup_mask].copy()

    summary_rows: list[dict] = []
    detail_rows: list[dict] = []

    if not dup_df.empty:
        for pid, group in dup_df.groupby("PointID", sort=True):
            diff_cols: list[str] = []
            for col in group.columns:
                series = group[col]
                non_null = series[~series.isna()]
                if non_null.empty:
                    continue
                if len({str(v) for v in non_null}) > 1:
                    diff_cols.append(col)

            summary_rows.append(
                {
                    "pointid": pid,
                    "duplicate_row_count": int(len(group)),
                    "differing_column_count": int(len(diff_cols)),
                    "differing_columns": "|".join(diff_cols),
                }
            )

            normalized = group.reset_index(drop=False).rename(
                columns={"index": "source_row_index"}
            )
            for row_num, row in normalized.iterrows():
                for col in diff_cols:
                    value = row.get(col, None)
                    detail_rows.append(
                        {
                            "pointid": pid,
                            "row_number": int(row_num),
                            "source_row_index": int(row["source_row_index"]),
                            "column": col,
                            "value": value,
                        }
                    )

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            by=["duplicate_row_count", "pointid"], ascending=[False, True]
        )

    detail_df = pd.DataFrame(detail_rows)
    if not detail_df.empty:
        detail_df = detail_df.sort_values(
            by=["pointid", "row_number", "column"], ascending=[True, True, True]
        )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_path, index=False)
    detail_df.to_csv(detail_path, index=False)

    if summary_df.empty:
        typer.echo("No duplicated WellData PointIDs found for current filters.")
        typer.echo(f"Wrote empty summary: {summary_path}")
        typer.echo(f"Wrote empty detail: {detail_path}")
        return

    total_dup_rows = int(len(dup_df))
    total_dup_pointids = int(summary_df["pointid"].nunique())
    typer.echo(
        f"Found {total_dup_pointids} duplicated PointIDs across {total_dup_rows} rows."
    )
    typer.echo(f"Wrote summary: {summary_path}")
    typer.echo(f"Wrote detail: {detail_path}")

    preview = summary_df.head(20)
    typer.echo("\nTop duplicate PointIDs:")
    for row in preview.itertuples(index=False):
        typer.echo(
            f"- {row.pointid}: rows={row.duplicate_row_count}, "
            f"differing_columns={row.differing_column_count}"
        )


@cli.command("well-smoke-test")
def well_smoke_test(
    sample_size: int = typer.Option(
        25,
        "--sample-size",
        min=1,
        help="Number of wells to sample.",
    ),
    population: SmokePopulation = typer.Option(
        SmokePopulation.agreed,
        "--population",
        help="Sample from all wells or transfer-agreed wells.",
    ),
    all_wells: bool = typer.Option(
        False,
        "--all-wells/--sampled",
        help="Check all wells in the selected population instead of sampling.",
    ),
    seed: int = typer.Option(
        42,
        "--seed",
        help="Random seed for deterministic sampling.",
    ),
    detail_path: Path = typer.Option(
        Path("transfers") / "metrics" / "well_smoke_test_detail.csv",
        "--detail-path",
        help="Output CSV path for per-well per-entity smoke-test rows.",
    ),
    summary_path: Path = typer.Option(
        Path("transfers") / "metrics" / "well_smoke_test_summary.json",
        "--summary-path",
        help="Output JSON path for smoke-test summary.",
    ),
    fail_on_mismatch: bool = typer.Option(
        False,
        "--fail-on-mismatch/--no-fail-on-mismatch",
        help="Exit with code 1 if any mismatches are found.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from transfers.smoke_test import (
        SmokePopulation as SmokePopulationModel,
        run_well_smoke_test,
        write_smoke_outputs,
    )

    payload = run_well_smoke_test(
        sample_size=sample_size,
        population=SmokePopulationModel(population.value),
        seed=seed,
        all_wells=all_wells,
    )
    write_smoke_outputs(payload, detail_path=detail_path, summary_path=summary_path)

    sampled_wells = payload.get("sampled_wells", 0)
    mismatch_count = payload.get("mismatch_count", 0)
    value_mismatch_count = payload.get("value_mismatch_count", 0)
    fail_count = payload.get("well_fail_count", 0)
    typer.echo(
        f"Smoke test complete: sampled_wells={sampled_wells}, "
        f"presence_mismatches={mismatch_count}, "
        f"value_mismatches={value_mismatch_count}, "
        f"failed_wells={fail_count}"
    )
    typer.echo(f"Wrote detail: {detail_path}")
    typer.echo(f"Wrote summary: {summary_path}")

    if mismatch_count or value_mismatch_count:
        failed_wells = payload.get("failed_wells", [])[:20]
        typer.echo(f"Sample failed wells (up to 20): {failed_wells}")

    if value_mismatch_count:
        entity_results = payload.get("entity_results", [])
        value_mismatches = [
            r
            for r in entity_results
            if r.get("value_status") not in {"MATCH", "NOT_APPLICABLE"}
        ]
        typer.echo("\nValue mismatches:")
        for row in value_mismatches[:100]:
            pointid = row.get("pointid")
            entity = row.get("entity")
            status = row.get("value_status")
            missing = row.get("missing_value_sample") or []
            extra = row.get("extra_value_sample") or []
            typer.echo(
                f"- {pointid} | {entity} | {status} | "
                f"missing={missing[:3]} | extra={extra[:3]}"
            )
        if len(value_mismatches) > 100:
            typer.echo(
                f"... truncated {len(value_mismatches) - 100} additional value mismatches"
            )

    if mismatch_count or value_mismatch_count:
        if fail_on_mismatch:
            raise typer.Exit(code=1)


@cli.command("well-inventory-csv")
def well_inventory_csv(
    file_path: str = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    parse and upload a csv to database
    """
    # TODO: use the same helper function used by api to parse and upload a WI csv
    from cli.service_adapter import well_inventory_csv

    result = well_inventory_csv(file_path)
    payload = result.payload if isinstance(result.payload, dict) else {}
    summary = payload.get("summary", {})
    validation_errors = payload.get("validation_errors", [])
    detail = payload.get("detail")
    colors = _palette(theme)

    if result.exit_code == 0:
        typer.secho("[WELL INVENTORY IMPORT] SUCCESS", fg=colors["ok"], bold=True)
    else:
        typer.secho(
            "[WELL INVENTORY IMPORT] COMPLETED WITH ISSUES",
            fg=colors["issue"],
            bold=True,
        )
    typer.secho("=" * 72, fg=colors["accent"])

    if summary:
        processed = summary.get("total_rows_processed", 0)
        imported = summary.get("total_rows_imported", 0)
        rows_with_issues = summary.get("validation_errors_or_warnings", 0)
        typer.secho("SUMMARY", fg=colors["accent"], bold=True)
        label_width = 16
        value_width = 8
        typer.secho("  " + "-" * (label_width + 3 + value_width), fg=colors["muted"])
        typer.secho(
            f"  {'processed':<{label_width}} | {processed:>{value_width}}",
            fg=colors["accent"],
        )
        typer.secho(
            f"  {'imported':<{label_width}} | {imported:>{value_width}}",
            fg=colors["ok"],
        )
        issue_color = colors["issue"] if rows_with_issues else colors["ok"]
        typer.secho(
            f"  {'rows_with_issues':<{label_width}} | {rows_with_issues:>{value_width}}",
            fg=issue_color,
        )
        typer.echo()

    if validation_errors:
        typer.secho("VALIDATION", fg=colors["accent"], bold=True)
        typer.secho(
            f"Validation errors: {len(validation_errors)}",
            fg=colors["issue"],
            bold=True,
        )
        common_errors = Counter()
        for err in validation_errors:
            field = err.get("field", "unknown")
            message = err.get("error") or err.get("msg") or "validation error"
            common_errors[(field, message)] += 1

        if common_errors:
            typer.secho(
                "Most common validation errors:", fg=colors["accent"], bold=True
            )
            field_width = 28
            count_width = 5
            error_width = 100
            typer.secho(
                f"  {'#':>2} | {'field':<{field_width}} | {'count':>{count_width}} | error",
                fg=colors["muted"],
                bold=True,
            )
            typer.secho(
                "  " + "-" * (2 + 3 + field_width + 3 + count_width + 3 + error_width),
                fg=colors["muted"],
            )
            for idx, ((field, message), count) in enumerate(
                common_errors.most_common(5), start=1
            ):
                error_one_line = shorten(
                    str(message).replace("\n", " "),
                    width=error_width,
                    placeholder="...",
                )
                field_text = shorten(str(field), width=field_width, placeholder="...")
                field_part = typer.style(
                    f"{field_text:<{field_width}}", fg=colors["field"], bold=True
                )
                count_part = f"{int(count):>{count_width}}"
                idx_part = typer.style(f"{idx:>2}", fg=colors["issue"])
                error_part = typer.style(error_one_line, fg=colors["issue"])
                typer.echo(f"  {idx_part} | {field_part} | {count_part} | {error_part}")
            typer.echo()

        grouped_errors = defaultdict(list)
        for err in validation_errors:
            row = err.get("row", "?")
            grouped_errors[row].append(err)

        def _row_sort_key(row_value):
            try:
                return (0, int(row_value))
            except (TypeError, ValueError):
                return (1, str(row_value))

        max_errors_to_show = 10
        shown = 0
        first_group = True
        for row in sorted(grouped_errors.keys(), key=_row_sort_key):
            if shown >= max_errors_to_show:
                break

            row_errors = grouped_errors[row]
            if not first_group:
                typer.secho("  " + "-" * 56, fg=colors["muted"])
            first_group = False
            typer.secho(
                f"  Row {row} ({len(row_errors)} issue{'s' if len(row_errors) != 1 else ''})",
                fg=colors["accent"],
                bold=True,
            )

            for idx, err in enumerate(row_errors, start=1):
                if shown >= max_errors_to_show:
                    break
                field = err.get("field", "unknown")
                message = err.get("error") or err.get("msg") or "validation error"
                input_value = err.get("value")
                prefix_raw = f"    {idx}. "
                field_raw = f"{field}:"
                msg_chunks = wrap(
                    str(message),
                    width=max(20, 200 - len(prefix_raw) - len(field_raw) - 1),
                ) or [""]
                prefix = typer.style(prefix_raw, fg=colors["issue"])
                field_part = typer.style(field_raw, fg=colors["field"], bold=True)
                first_msg_part = typer.style(msg_chunks[0], fg=colors["issue"])
                typer.echo(f"{prefix}{field_part} {first_msg_part}")
                msg_indent = " " * (len(prefix_raw) + len(field_raw) + 1)
                for chunk in msg_chunks[1:]:
                    typer.secho(f"{msg_indent}{chunk}", fg=colors["issue"])
                if input_value is not None:
                    input_prefix = "       input: "
                    input_chunks = wrap(
                        str(input_value), width=max(20, 200 - len(input_prefix))
                    ) or [""]
                    typer.echo(f"{input_prefix}{input_chunks[0]}")
                    input_indent = " " * len(input_prefix)
                    for chunk in input_chunks[1:]:
                        typer.echo(f"{input_indent}{chunk}")
                shown += 1
            typer.echo()

        if len(validation_errors) > shown:
            typer.secho(
                f"... and {len(validation_errors) - shown} more validation errors",
                fg=colors["issue"],
            )
    if detail:
        typer.secho("ERRORS", fg=colors["accent"], bold=True)
        typer.secho(f"Error: {detail}", fg=colors["issue"], bold=True)

    typer.secho("=" * 72, fg=colors["accent"])

    raise typer.Exit(result.exit_code)


@water_levels.command("bulk-upload")
def water_levels_bulk_upload(
    file_path: str = typer.Option(
        ...,
        "--file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to CSV file containing water level rows",
    ),
    output_format: OutputFormat | None = typer.Option(
        None,
        "--output",
        help="Optional output format",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    parse and upload a csv
    """
    # TODO: use the same helper function used by api to parse and upload a WL csv
    from cli.service_adapter import water_levels_csv

    colors = _palette(theme)
    source = Path(file_path)
    if not source.exists() or not source.is_file():
        typer.secho(
            f"File not found: {source}",
            fg=colors["issue"],
            bold=True,
            err=True,
        )
        raise typer.Exit(1)

    pretty_json = output_format == OutputFormat.json
    try:
        result = water_levels_csv(file_path, pretty_json=pretty_json)
    except (FileNotFoundError, PermissionError, IsADirectoryError) as exc:
        typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
        raise typer.Exit(1)

    # Backward compatibility for tests/mocks that return only an int.
    if isinstance(result, int):
        raise typer.Exit(result)

    if output_format == OutputFormat.json:
        typer.echo(result.stdout)
        raise typer.Exit(result.exit_code)

    payload = result.payload if isinstance(result.payload, dict) else {}
    summary = payload.get("summary", {})
    validation_errors = payload.get("validation_errors", [])
    rows_with_issues = summary.get("validation_errors_or_warnings", 0)

    if result.exit_code == 0 and not rows_with_issues:
        typer.secho("[WATER LEVEL IMPORT] SUCCESS", fg=colors["ok"], bold=True)
    elif result.exit_code == 0:
        typer.secho(
            "[WATER LEVEL IMPORT] COMPLETED WITH ISSUES",
            fg=colors["issue"],
            bold=True,
        )
    else:
        typer.secho(
            "[WATER LEVEL IMPORT] COMPLETED WITH ISSUES",
            fg=colors["issue"],
            bold=True,
        )
    typer.secho("=" * 72, fg=colors["accent"])

    parsed_validation: list[tuple[str | None, str, str]] = []
    for entry in validation_errors:
        if isinstance(entry, dict):
            row_value = entry.get("row")
            row = str(row_value) if row_value is not None else None
            field = str(entry.get("field") or "error").strip()
            message = str(
                entry.get("error") or entry.get("msg") or "validation error"
            ).strip()
            parsed_validation.append((row, field, message))
            continue

        text = str(entry).strip()
        m = re.match(r"^Row\s+(\d+):\s*(.+)$", text)
        if not m:
            parsed_validation.append((None, "error", text))
            continue

        row = m.group(1)
        detail = m.group(2).strip()
        if " - " in detail:
            field, message = detail.split(" - ", 1)
        elif req := re.match(r"^Missing required field '([^']+)'$", detail):
            field = req.group(1).strip()
            message = "Missing required field"
        else:
            field, message = "error", detail
        parsed_validation.append((row, field.strip(), message.strip()))

    if summary:
        processed = summary.get("total_rows_processed", 0)
        imported = summary.get("total_rows_imported", 0)
        typer.secho("SUMMARY", fg=colors["accent"], bold=True)
        label_width = 16
        value_width = 8
        typer.secho("  " + "-" * (label_width + 3 + value_width), fg=colors["muted"])
        typer.secho(
            f"  {'processed':<{label_width}} | {processed:>{value_width}}",
            fg=colors["accent"],
        )
        typer.secho(
            f"  {'imported':<{label_width}} | {imported:>{value_width}}",
            fg=colors["ok"],
        )
        issue_color = colors["issue"] if rows_with_issues else colors["ok"]
        typer.secho(
            f"  {'rows_with_issues':<{label_width}} | {rows_with_issues:>{value_width}}",
            fg=issue_color,
        )
        typer.echo()

    if parsed_validation:
        summary_counts: Counter[tuple[str, str]] = Counter(
            (field, message) for _row, field, message in parsed_validation
        )

        if summary_counts:
            typer.secho("VALIDATION SUMMARY", fg=colors["accent"], bold=True)
            field_width = 28
            count_width = 5
            error_width = 100
            typer.secho(
                f"  {'#':>2} | {'field':<{field_width}} | {'count':>{count_width}} | error",
                fg=colors["muted"],
                bold=True,
            )
            typer.secho(
                "  " + "-" * (2 + 3 + field_width + 3 + count_width + 3 + error_width),
                fg=colors["muted"],
            )
            for idx, ((field, message), count) in enumerate(
                summary_counts.most_common(5), start=1
            ):
                field_text = shorten(str(field), width=field_width, placeholder="...")
                error_one_line = shorten(
                    str(message).replace("\\n", " "),
                    width=error_width,
                    placeholder="...",
                )
                idx_part = typer.style(f"{idx:>2}", fg=colors["issue"])
                field_part = typer.style(
                    f"{field_text:<{field_width}}", fg=colors["field"], bold=True
                )
                count_part = f"{int(count):>{count_width}}"
                error_part = typer.style(error_one_line, fg=colors["issue"])
                typer.echo(f"  {idx_part} | {field_part} | {count_part} | {error_part}")
            typer.echo()

    if validation_errors:
        typer.secho("VALIDATION", fg=colors["accent"], bold=True)
        typer.secho(
            f"Validation errors: {len(validation_errors)}",
            fg=colors["issue"],
            bold=True,
        )

        row_grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        generic_errors: list[str] = []
        for row, field, message in parsed_validation:
            if row is None:
                if field and field != "error":
                    generic_errors.append(f"{field}: {message}")
                else:
                    generic_errors.append(message)
                continue
            row_grouped[row].append((field, message))

        max_errors_to_show = 10
        shown = 0
        first_group = True
        for row in sorted(
            row_grouped.keys(), key=lambda r: int(r) if str(r).isdigit() else 10**9
        ):
            if shown >= max_errors_to_show:
                break
            if not first_group:
                typer.secho("  " + "-" * 56, fg=colors["muted"])
            first_group = False
            errors = row_grouped[row]
            typer.secho(
                f"  Row {row} ({len(errors)} issue{'s' if len(errors) != 1 else ''})",
                fg=colors["accent"],
                bold=True,
            )
            for idx, (field, message) in enumerate(errors, start=1):
                if shown >= max_errors_to_show:
                    break
                prefix_raw = f"    {idx}. "
                field_raw = f"{field}:"
                msg_chunks = wrap(
                    str(message),
                    width=max(20, 200 - len(prefix_raw) - len(field_raw) - 1),
                ) or [""]
                prefix = typer.style(prefix_raw, fg=colors["issue"])
                field_part = typer.style(field_raw, fg=colors["field"], bold=True)
                first_msg_part = typer.style(msg_chunks[0], fg=colors["issue"])
                typer.echo(f"{prefix}{field_part} {first_msg_part}")
                msg_indent = " " * (len(prefix_raw) + len(field_raw) + 1)
                for chunk in msg_chunks[1:]:
                    typer.secho(f"{msg_indent}{chunk}", fg=colors["issue"])
                shown += 1
            typer.echo()

        for entry in generic_errors[: max(0, max_errors_to_show - shown)]:
            typer.secho(f"  - {entry}", fg=colors["issue"])
            shown += 1

        if len(validation_errors) > shown:
            typer.secho(
                f"... and {len(validation_errors) - shown} more validation errors",
                fg=colors["issue"],
            )

    typer.secho("=" * 72, fg=colors["accent"])
    raise typer.Exit(result.exit_code)


@data_migrations.command("list")
def data_migrations_list(
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from data_migrations.registry import list_migrations

    migrations = list_migrations()
    if not migrations:
        typer.echo("No data migrations registered.")
        return
    for migration in migrations:
        repeatable = " (repeatable)" if migration.is_repeatable else ""
        typer.echo(f"{migration.id}: {migration.name}{repeatable}")


@data_migrations.command("status")
def data_migrations_status(
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from db.engine import session_ctx
    from data_migrations.runner import get_status

    with session_ctx() as session:
        statuses = get_status(session)
    if not statuses:
        typer.echo("No data migrations registered.")
        return
    for status in statuses:
        last_applied = (
            status.last_applied_at.isoformat() if status.last_applied_at else "never"
        )
        typer.echo(
            f"{status.id}: applied {status.applied_count} time(s), last={last_applied}"
        )


@data_migrations.command("run")
def data_migrations_run(
    migration_id: str = typer.Argument(...),
    force: bool = typer.Option(
        False, "--force", help="Re-run even if already applied."
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from db.engine import session_ctx
    from data_migrations.runner import run_migration_by_id

    with session_ctx() as session:
        ran = run_migration_by_id(session, migration_id, force=force)
    typer.echo("applied" if ran else "skipped")


@data_migrations.command("run-all")
def data_migrations_run_all(
    include_repeatable: bool = typer.Option(
        False,
        "--include-repeatable/--exclude-repeatable",
        help="Whether to include repeatable migrations.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run non-repeatable migrations."
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from db.engine import session_ctx
    from data_migrations.runner import run_all

    with session_ctx() as session:
        ran = run_all(session, include_repeatable=include_repeatable, force=force)
    typer.echo(f"applied {len(ran)} migration(s)")


@cli.command("alembic-upgrade-and-data")
def alembic_upgrade_and_data(
    revision: str = typer.Argument("head"),
    include_repeatable: bool = typer.Option(
        False,
        "--include-repeatable/--exclude-repeatable",
        help="Whether to include repeatable migrations.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run non-repeatable migrations."
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from db.engine import engine, session_ctx
    from data_migrations.runner import run_all

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    command.upgrade(cfg, revision)

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        heads = context.get_current_heads()
        script = ScriptDirectory.from_config(cfg)
        applied_revisions: set[str] = set()
        for head in heads:
            for rev in script.iterate_revisions(head, "base"):
                applied_revisions.add(rev.revision)

    with session_ctx() as session:
        ran = run_all(
            session,
            include_repeatable=include_repeatable,
            force=force,
            allowed_alembic_revisions=applied_revisions,
        )
    typer.echo(f"applied {len(ran)} migration(s)")


@cli.command("refresh-pygeoapi-materialized-views")
def refresh_pygeoapi_materialized_views(
    view: list[str] = typer.Option(
        None,
        "--view",
        help=(
            "Materialized view name(s) to refresh. Repeat --view for multiple. "
            "Defaults to all pygeoapi materialized views."
        ),
    ),
    concurrently: bool = typer.Option(
        False,
        "--concurrently/--no-concurrently",
        help="Use REFRESH MATERIALIZED VIEW CONCURRENTLY.",
    ),
):
    from sqlalchemy import text

    from db.engine import engine, session_ctx

    target_views = tuple(view) if view else PYGEOAPI_MATERIALIZED_VIEWS
    # Validate all view names before opening any DB connections or sessions.
    safe_views = tuple(_validate_sql_identifier(v) for v in target_views)

    if concurrently:
        # PostgreSQL requires REFRESH MATERIALIZED VIEW CONCURRENTLY to run
        # outside of a transaction block, so we use an AUTOCOMMIT connection
        # instead of a Session (which would wrap the call in a transaction).
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for safe_view in safe_views:
                conn.execute(
                    text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {safe_view}")
                )
    else:
        # Non-concurrent refresh can safely run inside a transaction.
        with session_ctx() as session:
            for safe_view in safe_views:
                session.execute(text(f"REFRESH MATERIALIZED VIEW {safe_view}"))
            session.commit()

    typer.echo(f"Refreshed {len(target_views)} materialized view(s).")


@cli.command("import-project-area-boundaries")
def import_project_area_boundaries_command(
    layer_url: str = typer.Option(
        (
            "https://maps.nmt.edu/server/rest/services/Water/"
            "Water_Resources/MapServer/17"
        ),
        "--layer-url",
        help="ArcGIS Feature Layer URL for project area boundaries.",
    ),
):
    from cli.project_area_import import import_project_area_boundaries

    result = import_project_area_boundaries(layer_url=layer_url)
    typer.echo(f"Fetched {result.fetched} feature(s).")
    typer.echo(f"Matched {result.matched} group row(s).")
    typer.echo(f"Created {result.created} group(s).")
    typer.echo(f"Updated {result.updated} group project area(s).")
    typer.echo(f"Skipped {result.skipped} unchanged group(s).")
    if result.unmatched_locations:
        typer.echo(
            "Unmatched locations: " + ", ".join(result.unmatched_locations),
            err=True,
        )


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
