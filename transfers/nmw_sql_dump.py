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
"""DEPRECATED: parse a SQL Server data-dump ``.sql`` file into per-table CSVs.

Part of the frozen NM_Wells migration path; see the deprecation note in
``transfers/transfer_geothermal.py``. Kept runnable for re-runs of the NM_Wells
dump load, but it gets no new features and its tests no longer gate CI.

``INSERT [dbo].[<table>] (<cols>) VALUES (<vals>)[, (<vals>) ...]`` statements
(SSMS "Generate Scripts -> data" / bcp INSERT mode) are split with ``sqlparse``
and decoded to plain Python values:

    NULL                -> None
    N'...' / '...'      -> str  (doubled '' unescaped)
    123 / -1.5          -> int / float
    CAST(expr AS type)  -> the inner expr, recursively
    0x....              -> None (binary / rowversion; not mirrored)

``iter_table_rows`` yields ``{column: value}`` dicts; ``write_table_csv`` writes
one table to a CSV suitable for a Postgres ``COPY ... FROM`` bulk load (NULL ->
empty field, so load with ``NULL ''``).

Encoding is auto-detected from the BOM (SSMS writes UTF-16 LE); falls back to
utf-8.
"""

import csv
import itertools
import re
from typing import Iterator, Optional

import sqlparse


def _detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return "utf-8"


def _split_top_level(s: str) -> list[str]:
    """Split a comma list at paren-depth 0, respecting single-quoted strings."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_quote = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if in_quote:
            buf.append(c)
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":  # escaped ''
                    buf.append("'")
                    i += 2
                    continue
                in_quote = False
            i += 1
            continue
        if c == "'":
            in_quote = True
            buf.append(c)
        elif c == "(":
            depth += 1
            buf.append(c)
        elif c == ")":
            depth -= 1
            buf.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    if buf:
        parts.append("".join(buf).strip())
    return parts


def _iter_value_groups(s: str) -> Iterator[str]:
    """Yield the inside of each top-level ``( ... )`` group in a VALUES list."""
    depth = 0
    in_quote = False
    start = -1
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if in_quote:
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    i += 2
                    continue
                in_quote = False
            i += 1
            continue
        if c == "'":
            in_quote = True
        elif c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                yield s[start:i]
                start = -1
        i += 1


# The AS-target type may itself be parameterised, e.g. CAST(1.50 AS Decimal(18, 2))
# or CAST(N'x' AS nvarchar(10)); allow one level of parens in the type name.
_CAST_RE = re.compile(r"(?is)^CAST\s*\((.*)\s+AS\s+[^()]+(?:\([^)]*\))?\s*\)$")


def _parse_value(tok: str):
    t = tok.strip()
    if not t or t.upper() == "NULL":
        return None
    m = _CAST_RE.match(t)
    if m:
        return _parse_value(m.group(1).strip())
    # N'...' or '...'
    if t[:1] == "'" or t[:2].upper() == "N'":
        q = t.find("'")
        inner = t[q + 1 :]
        if inner.endswith("'"):
            inner = inner[:-1]
        return inner.replace("''", "'")
    if t[:2].lower() == "0x":  # binary / rowversion
        return None
    if re.fullmatch(r"[-+]?\d+", t):
        return int(t)
    try:
        return float(t)
    except ValueError:
        return t


_INSERT_RE = re.compile(
    r"(?is)INSERT\s+(?:\[dbo\]\.)?\[?(?P<table>\w+)\]?\s*"
    r"\((?P<cols>.*?)\)\s*VALUES\s*(?P<vals>.*)$"
)


def _iter_insert_statements(path: str, table: str) -> Iterator[str]:
    """Yield raw INSERT statement strings for ``table`` using sqlparse."""
    enc = _detect_encoding(path)
    target = table.lower()
    with open(path, encoding=enc, errors="ignore") as f:
        # parsestream splits the dump into statements lazily.
        for statement in sqlparse.parsestream(f):
            s = str(statement).strip()
            if not s:
                continue
            low = s.lower()
            if "insert" not in low or target not in low:
                continue
            yield s


def iter_table_rows(path: str, table: str) -> Iterator[dict]:
    """Yield ``{column: value}`` dicts for every INSERT into ``table``."""
    for stmt in _iter_insert_statements(path, table):
        m = _INSERT_RE.search(stmt)
        if not m or m.group("table").lower() != table.lower():
            continue
        cols = [c.strip().strip("[]") for c in _split_top_level(m.group("cols"))]
        vals_part = m.group("vals").strip().rstrip(";")
        for group in _iter_value_groups(vals_part):
            vals = [_parse_value(v) for v in _split_top_level(group)]
            if len(vals) != len(cols):
                continue  # malformed row; skip
            yield dict(zip(cols, vals))


def _csv_cell(value) -> str:
    """Render a parsed value for a COPY-friendly CSV (None -> empty field)."""
    return "" if value is None else str(value)


def write_table_csv(
    path: str,
    table: str,
    out_csv: str,
    columns: Optional[list[str]] = None,
    limit: int = 0,
) -> tuple[int, list[str]]:
    """Write one source table's rows to ``out_csv``. Returns (n_rows, header).

    ``columns`` restricts/orders the output columns (e.g. the target model's
    columns); missing source values become empty fields. If omitted, the first
    row's keys define the header. None -> empty so Postgres COPY ``NULL ''``
    treats it as NULL.
    """
    rows = iter_table_rows(path, table)
    if limit and limit > 0:
        rows = itertools.islice(rows, limit)

    header: Optional[list[str]] = None
    writer = None
    n = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as fo:
        for rec in rows:
            if header is None:
                header = list(columns) if columns else list(rec.keys())
                writer = csv.writer(fo)
                writer.writerow(header)
            writer.writerow([_csv_cell(rec.get(c)) for c in header])
            n += 1
    return n, (header or list(columns or []))


# ============= EOF =============================================
