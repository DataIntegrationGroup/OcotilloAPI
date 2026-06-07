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
"""Stream rows out of a SQL Server data-dump ``.sql`` file.

Parses ``INSERT [dbo].[<table>] (<cols>) VALUES (<vals>)[, (<vals>) ...]``
statements (the format produced by SSMS "Generate Scripts -> data" / ``bcp``
INSERT mode) for one target table at a time, yielding ``{column: value}``
dicts. Values are decoded to plain Python:

    NULL                -> None
    N'...' / '...'      -> str  (doubled '' unescaped)
    123 / -1.5          -> int / float
    CAST(expr AS type)  -> the inner expr, recursively
    0x....              -> None (binary / rowversion; not mirrored)

Type coercion to the target column type happens in nmw_mirror_transfer._coerce,
so this module keeps values loosely typed.

Streaming: the file is read line by line (constant memory), accumulating across
lines only when a statement's parentheses are unbalanced (strings containing
newlines). The file is scanned once per table.

Encoding is auto-detected from the BOM (SSMS writes UTF-16 LE); falls back to
utf-8.
"""

import re
from typing import Iterator, Optional


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


_CAST_RE = re.compile(r"(?is)^CAST\s*\((.*)\s+AS\s+[^)]+\)$")


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
    r"(?is)INSERT\s+(?:\[dbo\]\.)?\[?(?P<table>\w+)\]?\s*\((?P<cols>.*?)\)\s*VALUES\s*(?P<vals>.*)$"
)


def _balanced(stmt: str) -> bool:
    """True if parens are balanced outside single-quoted strings."""
    depth = 0
    in_quote = False
    i = 0
    n = len(stmt)
    while i < n:
        c = stmt[i]
        if in_quote:
            if c == "'":
                if i + 1 < n and stmt[i + 1] == "'":
                    i += 2
                    continue
                in_quote = False
        elif c == "'":
            in_quote = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return depth <= 0 and not in_quote


def iter_table_rows(path: str, table: str) -> Iterator[dict]:
    """Yield ``{column: value}`` dicts for every INSERT into ``table``."""
    enc = _detect_encoding(path)
    target = f"[{table}]".lower()
    target_plain = table.lower()
    pending: Optional[str] = None

    with open(path, encoding=enc, errors="ignore") as f:
        for line in f:
            if pending is None:
                low = line.lower()
                if "insert" not in low:
                    continue
                # cheap table filter before the heavier regex
                if (
                    target not in low
                    and f"].[{target_plain}]" not in low
                    and f" {target_plain} " not in low
                ):
                    if target_plain not in low:
                        continue
                pending = line
            else:
                pending += line

            if not _balanced(pending):
                continue  # statement spans more lines

            stmt = pending
            pending = None
            m = _INSERT_RE.search(stmt)
            if not m or m.group("table").lower() != target_plain:
                continue
            cols = [c.strip().strip("[]") for c in _split_top_level(m.group("cols"))]
            vals_part = m.group("vals").strip().rstrip(";")
            for group in _iter_value_groups(vals_part):
                vals = [_parse_value(v) for v in _split_top_level(group)]
                if len(vals) != len(cols):
                    continue  # malformed row; skip
                yield dict(zip(cols, vals))


# ============= EOF =============================================
