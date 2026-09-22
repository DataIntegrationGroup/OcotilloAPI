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
from enum import Enum
from pathlib import Path

import pandas as pd
import typer
from dotenv import load_dotenv

from cli import ingest_report as report

# Anything reaching db/engine.py must be imported lazily, inside the command
# that needs it: the engine reads its connection settings at import time, and
# load_dotenv() below has not run yet. (This module is safe -- it imports no
# engine.)
from services.materialized_views import MATERIALIZED_VIEWS

# CLI should load `.env` defaults without clobbering an explicitly prepared environment.
load_dotenv()
os.environ.setdefault("OCO_LOG_CONTEXT", "cli")

cli = typer.Typer(help="Command line interface for managing the application.")
water_levels = typer.Typer(help="Water-level utilities")
water_chemistry = typer.Typer(help="Water-chemistry utilities")
data_migrations = typer.Typer(help="Data migration utilities")
cli.add_typer(water_levels, name="water-levels")
cli.add_typer(water_chemistry, name="water-chemistry")
cli.add_typer(data_migrations, name="data-migrations")


class OutputFormat(str, Enum):
    json = "json"


class ThemeMode(str, Enum):
    auto = "auto"
    light = "light"
    dark = "dark"


class SmokePopulation(str, Enum):
    all = "all"
    agreed = "agreed"


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

    report.banner(
        (
            "[WELL INVENTORY IMPORT] SUCCESS"
            if result.exit_code == 0
            else "[WELL INVENTORY IMPORT] COMPLETED WITH ISSUES"
        ),
        colors,
        ok=result.exit_code == 0,
    )

    if summary:
        report.summary_section(report.import_summary_rows(summary, colors), colors)

    if validation_errors:
        # The importer reports a row number with every error, so anything
        # without one is still filed under a row -- an unlabeled one.
        entries = report.parse_validation_entries(validation_errors, default_row="?")
        typer.secho("VALIDATION", fg=colors["accent"], bold=True)
        typer.secho(
            f"Validation errors: {len(validation_errors)}",
            fg=colors["issue"],
            bold=True,
        )
        typer.secho("Most common validation errors:", fg=colors["accent"], bold=True)
        report.common_errors_table(entries, colors)
        shown = report.grouped_row_errors(entries, colors, show_input=True)
        report.truncation_note(len(validation_errors), shown, colors)

    if detail:
        typer.secho("ERRORS", fg=colors["accent"], bold=True)
        typer.secho(f"Error: {detail}", fg=colors["issue"], bold=True)

    report.rule(colors)

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

    # Rows can load while others fail, so a zero exit with issues is still
    # "completed with issues" rather than a clean success.
    report.banner(
        (
            "[WATER LEVEL IMPORT] SUCCESS"
            if result.exit_code == 0 and not rows_with_issues
            else "[WATER LEVEL IMPORT] COMPLETED WITH ISSUES"
        ),
        colors,
        ok=result.exit_code == 0 and not rows_with_issues,
    )

    # This importer reports most errors as preformatted strings; anything with
    # no row number is listed on its own below rather than grouped.
    entries = report.parse_validation_entries(validation_errors, default_field="error")

    if summary:
        report.summary_section(report.import_summary_rows(summary, colors), colors)

    if entries:
        typer.secho("VALIDATION SUMMARY", fg=colors["accent"], bold=True)
        report.common_errors_table(entries, colors)

    if validation_errors:
        typer.secho("VALIDATION", fg=colors["accent"], bold=True)
        typer.secho(
            f"Validation errors: {len(validation_errors)}",
            fg=colors["issue"],
            bold=True,
        )
        shown = report.grouped_row_errors(entries, colors)

        rowless = [
            f"{e.field}: {e.message}" if e.field and e.field != "error" else e.message
            for e in entries
            if e.row is None
        ]
        for entry in rowless[: max(0, report.MAX_ROW_ERRORS_SHOWN - shown)]:
            typer.secho(f"  - {entry}", fg=colors["issue"])
            shown += 1

        report.truncation_note(len(validation_errors), shown, colors)

    report.rule(colors)
    raise typer.Exit(result.exit_code)


@water_chemistry.command("bulk-upload")
def water_chemistry_bulk_upload(
    file_path: str = typer.Option(
        ...,
        "--file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to LIMS .xlsx workbook containing chemistry results.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    parse a LIMS chemistry workbook and load it into the NMA Major/Minor
    chemistry tables. Each distinct lab sample (WCLab_ID) is appended as a new
    lettered sample point; a lab sample already recorded for the well is
    skipped. A row that fails to map or references an unknown well aborts the
    whole file.
    """
    from cli.service_adapter import chemistry_lims_xlsx

    colors = _palette(theme)
    result = chemistry_lims_xlsx(file_path)

    payload = result.payload if isinstance(result.payload, dict) else {}
    summary = payload.get("summary", {})

    report.banner(
        (
            "[WATER CHEMISTRY IMPORT] SUCCESS"
            if result.exit_code == 0
            else "[WATER CHEMISTRY IMPORT] COMPLETED WITH ISSUES"
        ),
        colors,
        ok=result.exit_code == 0,
    )

    if summary:
        report.summary_section(report.import_summary_rows(summary, colors), colors)

    # These lists are what the engineer acts on, so they print in full.
    report.bullet_section(
        "CREATED SAMPLES",
        payload.get("created_samples", []),
        colors,
        color_key="ok",
        limit=None,
        formatter=lambda sample: (
            f"{sample['sample_point_id']} (WCLab_ID {sample.get('wclab_id')}): "
            f"{sample.get('rows', 0)} row(s)"
        ),
    )
    report.bullet_section(
        "SKIPPED (already ingested)",
        payload.get("skipped_duplicates", []),
        colors,
        color_key="field",
        title_color_key="muted",
        limit=None,
        formatter=lambda dupe: f"{dupe['pointid']} (WCLab_ID {dupe.get('wclab_id')})",
    )
    report.bullet_section(
        "WARNINGS (loaded, but check these)",
        payload.get("warnings", []),
        colors,
        color_key="field",
        limit=None,
    )

    report.validation_errors_section(payload.get("validation_errors", []), colors)

    report.rule(colors)
    raise typer.Exit(result.exit_code)


def _describe_failed_file(record: dict) -> str:
    """Why a Drive workbook failed, however the ingest reported it.

    A hard failure carries an ``error``; a data-quality abort carries only the
    validation errors, and the first of those is the useful headline.
    """
    detail = record.get("error")
    if not detail:
        errors = record.get("payload", {}).get("validation_errors") or []
        if errors:
            detail = errors[0]
            if len(errors) > 1:
                detail += f" (+{len(errors) - 1} more)"
        else:
            detail = "ingestion aborted"
    return f"{record['name']}: {detail}"


@water_chemistry.command("sync-drive")
def water_chemistry_sync_drive(
    folder_id: str = typer.Option(
        None,
        "--folder-id",
        help="Google Drive folder id to scan. Defaults to $CHEMISTRY_DRIVE_FOLDER_ID.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="List new files without downloading, ingesting, or updating the manifest.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    ingest LIMS chemistry workbooks from a Google Drive folder. Run on demand
    by an engineer -- this does no polling or scheduling. New or changed files
    are ingested; a manifest of ingested files is kept in GCS so
    already-processed files are skipped.
    """
    from services.chemistry_drive import ChemistryDriveConfigError, sync_and_ingest

    colors = _palette(theme)
    try:
        result = sync_and_ingest(folder_id=folder_id, dry_run=dry_run)
    except ChemistryDriveConfigError as exc:
        typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
        raise typer.Exit(1) from exc

    summary = result.to_payload()["summary"]
    report.banner(
        (
            "[CHEMISTRY DRIVE SYNC] DRY RUN"
            if result.dry_run
            else "[CHEMISTRY DRIVE SYNC]"
        ),
        colors,
        ok=result.exit_code == 0,
    )
    typer.secho(f"Folder: {result.folder_id}", fg=colors["accent"])
    typer.echo()

    report.summary_section(
        [
            ("files_seen", summary["files_seen"], "accent"),
            ("new_files", summary["new_files"], "accent"),
            ("ingested", summary["ingested"], "ok"),
            ("skipped", summary["skipped"], "muted"),
            ("failed", summary["failed"], "issue" if summary["failed"] else "ok"),
        ],
        colors,
        label_width=12,
        value_width=6,
        divider=False,
    )

    if result.dry_run:
        report.bullet_section(
            "NEW FILES (not ingested)",
            result.new_files,
            colors,
            color_key="field",
            title_color_key="accent",
            limit=None,
        )

    report.bullet_section(
        "INGESTED",
        result.ingested,
        colors,
        color_key="ok",
        limit=None,
        formatter=lambda record: (
            f"{record['name']}: {record.get('rows_imported', 0)} row(s)"
        ),
    )
    report.bullet_section(
        "FAILED",
        result.failed,
        colors,
        color_key="issue",
        limit=None,
        formatter=_describe_failed_file,
    )

    report.rule(colors)
    raise typer.Exit(result.exit_code)


@water_chemistry.command("manifest-status")
def water_chemistry_manifest_status(
    name: str = typer.Option(
        None,
        "--name",
        help="Only show workbooks whose file name contains this text.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    show which databases each chemistry workbook has been ingested into. Reads
    every per-database manifest in GCS and merges them for display; writes
    nothing, so it is safe to run against any environment.
    """
    from services.chemistry_drive import ChemistryDriveConfigError, manifest_overview

    colors = _palette(theme)
    try:
        overview = manifest_overview()
    except ChemistryDriveConfigError as exc:
        typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
        raise typer.Exit(1) from exc

    databases = overview.databases
    if not databases and not overview.unreadable:
        typer.secho("No chemistry ingest manifests found.", fg=colors["muted"])
        return

    records = sorted(overview.files.items(), key=lambda kv: kv[1]["name"].lower())
    if name:
        needle = name.lower()
        records = [r for r in records if needle in r[1]["name"].lower()]

    typer.secho("[CHEMISTRY MANIFEST STATUS]", fg=colors["accent"], bold=True)
    typer.secho("=" * 72, fg=colors["accent"])
    typer.secho(f"Databases: {', '.join(databases) or 'none'}", fg=colors["accent"])
    if overview.unreadable:
        typer.secho(
            f"Unreadable manifests (not shown below): "
            f"{', '.join(overview.unreadable)}",
            fg=colors["issue"],
        )
    typer.echo()

    if not records:
        typer.secho("No workbooks match.", fg=colors["muted"])
        return

    for _file_id, record in records:
        typer.secho(record["name"], fg=colors["field"], bold=True)
        for db in databases:
            entry = record["databases"].get(db)
            if entry is None:
                typer.secho(f"  {db:<28} | not ingested", fg=colors["muted"])
                continue
            status = entry.get("status", "unknown")
            color = colors["ok"] if status == "success" else colors["issue"]
            detail = f"{entry.get('rows_imported', 0)} row(s)"
            if status != "success":
                detail = entry.get("error") or "ingestion failed"
            when = (entry.get("ingested_at") or "")[:19]
            typer.secho(
                f"  {db:<28} | {status:<8} | {detail} | {when}",
                fg=color,
            )
        typer.echo()

    typer.secho("=" * 72, fg=colors["accent"])


def _render_field_sheet_result(result, colors: dict[str, str], source: str) -> None:
    """Print the outcome of a chemistry field-sheet import."""
    payload = result.payload if isinstance(result.payload, dict) else {}
    summary = payload.get("summary", {})

    if summary.get("dry_run"):
        headline = "[CHEMISTRY FIELD SHEET] DRY RUN (nothing written)"
    elif result.exit_code == 0:
        headline = "[CHEMISTRY FIELD SHEET] SUCCESS"
    else:
        headline = "[CHEMISTRY FIELD SHEET] ABORTED -- nothing written"
    report.banner(headline, colors, ok=result.exit_code == 0)
    typer.secho(f"Source: {source}", fg=colors["accent"])
    raw = payload.get("raw") or {}
    if raw.get("load_id"):
        verb = "Replayed" if raw.get("replayed") else "Archived"
        typer.secho(
            f"{verb}: {raw['dataset']}/{raw['load_id']} at {raw['url']}",
            fg=colors["accent"],
        )
    typer.echo()

    if summary:
        rows_with_issues = summary.get("validation_errors_or_warnings", 0)
        report.summary_section(
            [
                ("rows read", summary.get("total_rows_processed", 0), "accent"),
                ("readings loaded", summary.get("total_rows_imported", 0), "ok"),
                ("samples created", summary.get("samples_created", 0), "ok"),
                ("samples matched", summary.get("samples_matched", 0), "accent"),
                ("readings skipped", summary.get("parameters_skipped", 0), "muted"),
                (
                    "rows_with_issues",
                    rows_with_issues,
                    "issue" if rows_with_issues else "ok",
                ),
            ],
            colors,
            label_width=17,
            value_width=6,
            divider=False,
        )

    def _describe_sample(sample: dict) -> str:
        return (
            f"{sample['sample_point_id']} "
            f"({sample['pointid']} @ {sample['collection_date']})"
        )

    report.bullet_section(
        "SAMPLES CREATED",
        payload.get("samples_created", []),
        colors,
        color_key="ok",
        limit=None,
        formatter=_describe_sample,
    )
    report.bullet_section(
        "SAMPLES MATCHED (already recorded for that well and date)",
        payload.get("samples_matched", []),
        colors,
        color_key="field",
        title_color_key="accent",
        limit=None,
        formatter=_describe_sample,
    )
    report.bullet_section(
        "SKIPPED (already recorded)",
        payload.get("skipped_parameters", []),
        colors,
        color_key="field",
        title_color_key="muted",
        formatter=lambda entry: (
            f"{entry['sample_point_id']}: {entry['field_parameter']}"
        ),
    )
    report.bullet_section(
        "WARNINGS (loaded, but check these)",
        payload.get("warnings", []),
        colors,
        color_key="field",
    )

    report.validation_errors_section(payload.get("validation_errors", []), colors)

    report.rule(colors)


@water_chemistry.command("sync-sheet")
def water_chemistry_sync_sheet(
    sheet: str = typer.Option(
        None,
        "--sheet-id",
        "--url",
        help=(
            "Google spreadsheet id or URL holding the ChemistrySampleInfo and "
            "FieldParameters tabs. Defaults to $CHEMISTRY_FIELD_SHEET_ID."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Read, validate and report without writing anything -- no database "
            "rows and no raw-zone snapshot."
        ),
    ),
    replay: str = typer.Option(
        None,
        "--replay",
        help=(
            "Load an archived snapshot again instead of reading the sheet. "
            "Pass a load id, or 'latest'."
        ),
    ),
    no_raw: bool = typer.Option(
        False,
        "--no-raw",
        help="Skip the raw-zone archive and map straight from the sheet.",
    ),
    raw_url: str = typer.Option(
        None,
        "--raw-url",
        help=(
            "Raw zone to archive into (gs://bucket/prefix or file:///path). "
            "Defaults to $INGESTION_GCS_BUCKET, then $OCO_RAW_ZONE_DIR."
        ),
    ),
    list_snapshots: bool = typer.Option(
        False,
        "--list-snapshots",
        help="List the archived snapshots and exit.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    ingest the AMP chemistry field spreadsheet from Google Drive: the
    ChemistrySampleInfo and FieldParameters tabs, into NMA_Chemistry_SampleInfo
    and NMA_FieldParameters. Lab result tabs in the same workbook are left to
    the LIMS ingest.

    Samples are matched to what is already recorded on well PointID plus
    collection date, so a field visit and its lab batch share one sample and
    re-running loads nothing twice. Any data-quality problem aborts the whole
    import.
    """
    from services.chemistry_drive import ChemistryDriveConfigError
    from services.chemistry_field_params import (
        FIELD_SHEET_DATASET,
        replay_field_sheet,
        sync_field_sheet,
    )
    from services.chemistry_field_sheet import FieldSheetError
    from services.ingest_raw_zone import RawZoneError, list_snapshots as _snapshots

    colors = _palette(theme)

    if list_snapshots:
        try:
            snapshots = _snapshots(FIELD_SHEET_DATASET, raw_url=raw_url)
        except RawZoneError as exc:
            typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
            raise typer.Exit(1) from exc
        report.banner("[CHEMISTRY FIELD SHEET] SNAPSHOTS", colors)
        report.bullet_section(
            "ARCHIVED SNAPSHOTS (newest last)",
            snapshots,
            colors,
            color_key="field",
            title_color_key="accent",
            limit=None,
        )
        if not snapshots:
            typer.secho("  none archived yet", fg=colors["muted"])
        report.rule(colors)
        raise typer.Exit(0)

    try:
        if replay:
            result = replay_field_sheet(
                None if replay == "latest" else replay,
                dry_run=dry_run,
                raw_url=raw_url,
            )
            source = f"raw zone snapshot {replay}"
        else:
            result = sync_field_sheet(
                sheet, dry_run=dry_run, archive=not no_raw, raw_url=raw_url
            )
            source = sheet or os.environ.get("CHEMISTRY_FIELD_SHEET_ID", "")
    except (ChemistryDriveConfigError, FieldSheetError, RawZoneError) as exc:
        typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
        raise typer.Exit(1) from exc

    _render_field_sheet_result(result, colors, source)
    raise typer.Exit(result.exit_code)


@water_chemistry.command("field-upload")
def water_chemistry_field_upload(
    file_paths: list[str] = typer.Option(
        ...,
        "--file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help=(
            "Downloaded copy of the field spreadsheet (.xlsx with both tabs, or "
            ".csv). Repeat --file to pass one CSV per tab."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Read, validate and report without writing anything.",
    ),
    no_raw: bool = typer.Option(
        False,
        "--no-raw",
        help="Skip the raw-zone archive and map straight from the file.",
    ),
    raw_url: str = typer.Option(
        None,
        "--raw-url",
        help=(
            "Raw zone to archive into (gs://bucket/prefix or file:///path). "
            "Defaults to $INGESTION_GCS_BUCKET, then $OCO_RAW_ZONE_DIR."
        ),
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    """
    ingest a downloaded copy of the AMP chemistry field spreadsheet. Same rules
    as `sync-sheet`, for an engineer who has the file but not Drive access to
    the sheet.
    """
    from services.chemistry_field_params import upload_field_export
    from services.chemistry_field_sheet import FieldSheetError
    from services.ingest_raw_zone import RawZoneError

    colors = _palette(theme)
    try:
        result = upload_field_export(
            file_paths, dry_run=dry_run, archive=not no_raw, raw_url=raw_url
        )
    except (FieldSheetError, RawZoneError) as exc:
        typer.secho(str(exc), fg=colors["issue"], bold=True, err=True)
        raise typer.Exit(1) from exc

    _render_field_sheet_result(result, colors, ", ".join(file_paths))
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report the planned changes without writing anything.",
    ),
    theme: ThemeMode = typer.Option(
        ThemeMode.auto, "--theme", help="Color theme: auto, light, dark."
    ),
):
    from db.engine import session_ctx
    from data_migrations.runner import dry_run_migration_by_id, run_migration_by_id

    if dry_run:
        with session_ctx() as session:
            dry_run_migration_by_id(session, migration_id)
        typer.echo("dry run complete; nothing written")
        return

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


@cli.command("refresh-materialized-views")
def refresh_materialized_views(
    view: list[str] = typer.Option(
        None,
        "--view",
        help=(
            "Materialized view name(s) to refresh. Repeat --view for multiple. "
            "Defaults to all materialized views."
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

    target_views = tuple(view) if view else MATERIALIZED_VIEWS
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
        None,
        "--layer-url",
        help=(
            "ArcGIS Feature Layer URL for project area boundaries. "
            "Defaults to PROJECT_AREA_LAYER_URL."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report what would change and write nothing.",
    ),
):
    from cli.project_area_import import (
        PROJECT_AREA_LAYER_URL,
        import_project_area_boundaries,
    )

    result = import_project_area_boundaries(
        layer_url=layer_url or PROJECT_AREA_LAYER_URL,
        dry_run=dry_run,
    )
    if dry_run:
        typer.echo("DRY RUN -- nothing written.")
    typer.echo(f"Fetched {result.fetched} feature(s).")
    typer.echo(f"Created {result.created} group(s).")
    typer.echo(f"Updated {result.updated} group(s).")
    typer.echo(f"Published {result.published} group(s).")
    typer.echo(f"Unchanged {result.unchanged} group(s).")
    typer.echo(f"Skipped {result.skipped} feature(s).")
    for action in result.skips:
        typer.echo(
            f"  skipped OBJECTID {action.object_id} "
            f"({action.location!r}): {action.reason}",
            err=True,
        )


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
