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

import typer
from dotenv import load_dotenv

load_dotenv()

cli = typer.Typer(help="Command line interface for managing the application.")
water_levels = typer.Typer(help="Water-level utilities")
data_migrations = typer.Typer(help="Data migration utilities")
cli.add_typer(water_levels, name="water-levels")
cli.add_typer(data_migrations, name="data-migrations")


class OutputFormat(str, Enum):
    json = "json"


class ThemeMode(str, Enum):
    auto = "auto"
    light = "light"
    dark = "dark"


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

    if result.exit_code == 0:
        typer.secho("[WATER LEVEL IMPORT] SUCCESS", fg=colors["ok"], bold=True)
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


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
