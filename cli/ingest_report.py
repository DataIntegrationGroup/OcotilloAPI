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
"""
Shared rendering for the `oco` ingest commands.

Every ingest command -- well inventory, water levels, the two chemistry ingests
and the Drive/Sheet syncs -- reports the same way: a banner, a rule, a summary
of rows processed against rows loaded, then whatever went wrong. Each one used
to carry its own copy of that layout, so a column width or a heading fixed in
one command stayed wrong in the others, and a new command started by pasting a
hundred lines of `typer.secho`.

The pieces live here as primitives rather than as one render-everything
function, because the commands genuinely differ in what they have to say: the
CSV importers report per-row field errors, while the chemistry ingests report
whole-file aborts. Commands compose the pieces they need and print their own
section headings.

Colors arrive as the palette dict the CLI resolves from `--theme`, so nothing
here needs to know how a theme is chosen.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from textwrap import shorten, wrap
from typing import Any, Iterable, Sequence

import typer

RULE_WIDTH = 72
GROUP_RULE_WIDTH = 56

SUMMARY_LABEL_WIDTH = 16
SUMMARY_VALUE_WIDTH = 8

# How much of a long report is worth printing before it stops being read.
MAX_ROW_ERRORS_SHOWN = 10
MAX_LISTED = 25
TOP_COMMON_ERRORS = 5

_ROW_PREFIX_RE = re.compile(r"^Row\s+(\d+):\s*(.+)$")
_MISSING_FIELD_RE = re.compile(r"^Missing required field '([^']+)'$")


@dataclass(frozen=True)
class ValidationEntry:
    """One validation problem, however the service phrased it.

    Services report validation errors either as dicts (the well-inventory
    importer) or as already-formatted strings (the water-level and chemistry
    importers). Both become this, so the rendering below has one shape to
    handle.
    """

    row: str | None
    field: str
    message: str
    value: Any | None = None


def parse_validation_entries(
    entries: Iterable[Any],
    *,
    default_field: str = "unknown",
    default_row: str | None = None,
) -> list[ValidationEntry]:
    """Normalize a service's validation errors into :class:`ValidationEntry`.

    ``default_row`` is what a problem with no row number is filed under: a
    label (the well-inventory importer groups them under "?") or ``None`` to
    leave them ungrouped for the caller to list separately.
    """
    parsed: list[ValidationEntry] = []
    for entry in entries:
        if isinstance(entry, dict):
            row_value = entry.get("row", default_row)
            parsed.append(
                ValidationEntry(
                    row=str(row_value) if row_value is not None else None,
                    field=str(entry.get("field") or default_field).strip(),
                    message=str(
                        entry.get("error") or entry.get("msg") or "validation error"
                    ).strip(),
                    value=entry.get("value"),
                )
            )
            continue

        text = str(entry).strip()
        match = _ROW_PREFIX_RE.match(text)
        if not match:
            parsed.append(ValidationEntry(row=default_row, field="error", message=text))
            continue

        detail = match.group(2).strip()
        if " - " in detail:
            field, message = detail.split(" - ", 1)
        elif missing := _MISSING_FIELD_RE.match(detail):
            field, message = missing.group(1), "Missing required field"
        else:
            field, message = "error", detail
        parsed.append(
            ValidationEntry(
                row=match.group(1), field=field.strip(), message=message.strip()
            )
        )
    return parsed


# --- layout primitives ---------------------------------------------------------


def rule(colors: dict[str, str]) -> None:
    """The full-width rule that opens and closes every ingest report."""
    typer.secho("=" * RULE_WIDTH, fg=colors["accent"])


def banner(text: str, colors: dict[str, str], *, ok: bool = True) -> None:
    """Print the report's headline and the rule under it."""
    typer.secho(text, fg=colors["ok"] if ok else colors["issue"], bold=True)
    rule(colors)


def summary_section(
    rows: Sequence[tuple[str, Any, str]],
    colors: dict[str, str],
    *,
    label_width: int = SUMMARY_LABEL_WIDTH,
    value_width: int = SUMMARY_VALUE_WIDTH,
    divider: bool = True,
) -> None:
    """The SUMMARY block: ``(label, value, palette key)`` per line."""
    typer.secho("SUMMARY", fg=colors["accent"], bold=True)
    if divider:
        typer.secho("  " + "-" * (label_width + 3 + value_width), fg=colors["muted"])
    for label, value, color_key in rows:
        typer.secho(
            f"  {label:<{label_width}} | {value:>{value_width}}",
            fg=colors[color_key],
        )
    typer.echo()


def import_summary_rows(
    summary: dict, colors: dict[str, str]
) -> list[tuple[str, Any, str]]:
    """The three counts every row-oriented importer reports."""
    rows_with_issues = summary.get("validation_errors_or_warnings", 0)
    return [
        ("processed", summary.get("total_rows_processed", 0), "accent"),
        ("imported", summary.get("total_rows_imported", 0), "ok"),
        ("rows_with_issues", rows_with_issues, "issue" if rows_with_issues else "ok"),
    ]


def common_errors_table(
    entries: Sequence[ValidationEntry],
    colors: dict[str, str],
    *,
    top: int = TOP_COMMON_ERRORS,
    field_width: int = 28,
    count_width: int = 5,
    error_width: int = 100,
) -> None:
    """The "which field is failing most" table.

    One bad column produces one error per row, so the per-row detail below is
    the same message a hundred times over. This says which columns to fix
    first.
    """
    counts: Counter[tuple[str, str]] = Counter(
        (entry.field, entry.message) for entry in entries
    )
    if not counts:
        return

    typer.secho(
        f"  {'#':>2} | {'field':<{field_width}} | {'count':>{count_width}} | error",
        fg=colors["muted"],
        bold=True,
    )
    typer.secho(
        "  " + "-" * (2 + 3 + field_width + 3 + count_width + 3 + error_width),
        fg=colors["muted"],
    )
    for idx, ((field, message), count) in enumerate(counts.most_common(top), start=1):
        field_text = shorten(str(field), width=field_width, placeholder="...")
        error_one_line = shorten(
            str(message).replace("\n", " "), width=error_width, placeholder="..."
        )
        idx_part = typer.style(f"{idx:>2}", fg=colors["issue"])
        field_part = typer.style(
            f"{field_text:<{field_width}}", fg=colors["field"], bold=True
        )
        count_part = f"{int(count):>{count_width}}"
        error_part = typer.style(error_one_line, fg=colors["issue"])
        typer.echo(f"  {idx_part} | {field_part} | {count_part} | {error_part}")
    typer.echo()


def _row_sort_key(row: str) -> tuple[int, Any]:
    """Order rows numerically, keeping any non-numeric label last."""
    try:
        return (0, int(row))
    except (TypeError, ValueError):
        return (1, str(row))


def grouped_row_errors(
    entries: Sequence[ValidationEntry],
    colors: dict[str, str],
    *,
    show_input: bool = False,
    limit: int = MAX_ROW_ERRORS_SHOWN,
) -> int:
    """Print per-row detail, grouped by spreadsheet row. Returns lines shown.

    Stops at ``limit``, since the point is to show an operator what to fix
    first, not to reproduce the file.
    """
    grouped: dict[str, list[ValidationEntry]] = defaultdict(list)
    for entry in entries:
        if entry.row is not None:
            grouped[entry.row].append(entry)

    shown = 0
    first_group = True
    for row in sorted(grouped, key=_row_sort_key):
        if shown >= limit:
            break
        row_entries = grouped[row]
        if not first_group:
            typer.secho("  " + "-" * GROUP_RULE_WIDTH, fg=colors["muted"])
        first_group = False
        typer.secho(
            f"  Row {row} ({len(row_entries)} "
            f"issue{'s' if len(row_entries) != 1 else ''})",
            fg=colors["accent"],
            bold=True,
        )
        for idx, entry in enumerate(row_entries, start=1):
            if shown >= limit:
                break
            _print_entry(entry, idx, colors, show_input=show_input)
            shown += 1
        typer.echo()
    return shown


def _print_entry(
    entry: ValidationEntry, idx: int, colors: dict[str, str], *, show_input: bool
) -> None:
    """One numbered `field: message` line, wrapped, with its input value."""
    prefix_raw = f"    {idx}. "
    field_raw = f"{entry.field}:"
    msg_chunks = wrap(
        str(entry.message),
        width=max(20, 200 - len(prefix_raw) - len(field_raw) - 1),
    ) or [""]
    prefix = typer.style(prefix_raw, fg=colors["issue"])
    field_part = typer.style(field_raw, fg=colors["field"], bold=True)
    typer.echo(f"{prefix}{field_part} {typer.style(msg_chunks[0], fg=colors['issue'])}")
    msg_indent = " " * (len(prefix_raw) + len(field_raw) + 1)
    for chunk in msg_chunks[1:]:
        typer.secho(f"{msg_indent}{chunk}", fg=colors["issue"])

    if not show_input or entry.value is None:
        return
    input_prefix = "       input: "
    input_chunks = wrap(str(entry.value), width=max(20, 200 - len(input_prefix))) or [
        ""
    ]
    typer.echo(f"{input_prefix}{input_chunks[0]}")
    input_indent = " " * len(input_prefix)
    for chunk in input_chunks[1:]:
        typer.echo(f"{input_indent}{chunk}")


def truncation_note(total: int, shown: int, colors: dict[str, str]) -> None:
    """Say how much of a long error report was left unprinted."""
    if total > shown:
        typer.secho(
            f"... and {total - shown} more validation errors", fg=colors["issue"]
        )


def bullet_section(
    title: str,
    items: Sequence[Any],
    colors: dict[str, str],
    *,
    color_key: str = "issue",
    title_color_key: str | None = None,
    limit: int | None = MAX_LISTED,
    formatter=str,
    more_label: str = "more",
) -> None:
    """A titled bullet list, optionally capped with a "... and N more" tail.

    The whole-file ingests (chemistry, Drive sync) report at file and sample
    level rather than per row, so this is their unit of output. ``limit=None``
    prints everything, for the lists an operator is expected to act on in full.
    """
    if not items:
        return
    typer.secho(title, fg=colors[title_color_key or color_key], bold=True)
    shown = list(items) if limit is None else list(items[:limit])
    for item in shown:
        typer.secho(f"  - {formatter(item)}", fg=colors[color_key])
    if len(items) > len(shown):
        typer.secho(
            f"  ... and {len(items) - len(shown)} {more_label}", fg=colors[color_key]
        )
    typer.echo()


def validation_errors_section(
    validation_errors: Sequence[Any], colors: dict[str, str]
) -> None:
    """The flat VALIDATION section used by the whole-file ingests."""
    if not validation_errors:
        return
    typer.secho("VALIDATION", fg=colors["accent"], bold=True)
    typer.secho(
        f"Validation errors: {len(validation_errors)}", fg=colors["issue"], bold=True
    )
    for entry in validation_errors[:MAX_LISTED]:
        typer.secho(f"  - {entry}", fg=colors["issue"])
    truncation_note(len(validation_errors), MAX_LISTED, colors)


# ============= EOF =============================================
