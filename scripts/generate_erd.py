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
Generate a Graphviz DOT ERD from SQLAlchemy metadata.

Usage:
  python scripts/generate_erd.py --dot schema_erd.dot --png schema_erd.png
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sqlalchemy import Table

from db.base import Base
import db  # noqa: F401  # Ensure models are imported and registered.


def _column_label(column) -> str:
    prefix = ""
    if column.primary_key:
        prefix += "* "
    if column.foreign_keys:
        prefix += "+ "
    return f"{prefix}{column.name}\\l"


def _table_label(table: Table) -> str:
    columns = "".join(_column_label(col) for col in table.columns)
    return f"{{{table.name}|{columns}}}"


def _write_dot(path: Path) -> None:
    metadata = Base.metadata
    tables = sorted(metadata.tables.values(), key=lambda t: t.name)

    lines = [
        "digraph ERD {",
        "  graph [rankdir=LR];",
        '  node [shape=record, fontname="Helvetica"];',
        '  edge [fontname="Helvetica"];',
        "",
    ]

    for table in tables:
        label = _table_label(table)
        lines.append(f'  "{table.name}" [label="{label}"];')

    lines.append("")

    for table in tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                target_table = fk.column.table.name
                target_column = fk.column.name
                lines.append(
                    f'  "{table.name}" -> "{target_table}" '
                    f'[label="{column.name} -> {target_column}"];'
                )

    lines.append("}")
    path.write_text("\n".join(lines))


def _render_png(dot_path: Path, png_path: Path) -> None:
    dot = shutil.which("dot")
    if not dot:
        raise SystemExit("Graphviz 'dot' not found on PATH.")
    import subprocess

    subprocess.run(
        [dot, "-Tpng", str(dot_path), "-o", str(png_path)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ERD Graphviz files.")
    parser.add_argument(
        "--dot",
        type=Path,
        default=Path("schema_erd.dot"),
        help="Path to write DOT output.",
    )
    parser.add_argument(
        "--png",
        type=Path,
        default=None,
        help="Optional path to write PNG output (requires Graphviz).",
    )
    args = parser.parse_args()

    _write_dot(args.dot)
    if args.png:
        _render_png(args.dot, args.png)


if __name__ == "__main__":
    main()
