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
"""Small value helpers shared by the domain rules."""

import re
from datetime import date, datetime
from typing import Any


def enum_value(value: Any, default: Any = None) -> Any:
    """
    Unwrap an ``Enum``-like value to its ``.value``.

    CSV rows reach the importers with fields that may be a validated enum member
    or a bare string, depending on which Pydantic schema produced them, so the
    ``x.value if hasattr(x, "value") else x`` idiom was repeated at roughly a
    dozen call sites.

    Non-enum values pass through unchanged. When ``default`` is supplied, a falsy
    non-enum value (``None``, ``""``) is replaced by it; when ``default`` is
    omitted, falsy values are returned as-is.
    """
    if hasattr(value, "value"):
        return value.value
    if default is not None and not value:
        return default
    return value


def build_notes(candidates) -> list[dict]:
    """
    Turn ``(content, note_type)`` pairs into note payloads, dropping empty content.

    ``candidates`` is any iterable of two-tuples. Order is preserved, and a pair
    whose content is ``None`` is skipped -- an empty string is *not* skipped,
    matching the importers' existing ``is not None`` check.
    """
    return [
        {"content": content, "note_type": note_type}
        for content, note_type in candidates
        if content is not None
    ]


def to_float(value: Any, *, lenient: bool = False) -> float | None:
    """
    Read a spreadsheet cell as a number, or ``None`` when it is not one.

    ``lenient`` also accepts what people type into cells that a strict ``float``
    rejects: thousands separators, and a comparison qualifier written into the
    value itself (``"<0.01"``). Callers that record the qualifier separately --
    a lab result, where ``<`` means a non-detect and must survive into the
    stored row -- leave it off, so a qualified value fails loudly instead of
    being silently promoted to a plain reading.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        # bool is an int subclass; a checkbox is not a measurement.
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if lenient:
        text = text.replace(",", "").lstrip("<>~=").strip()
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


# Non-ISO layouts seen in the importers' source spreadsheets.
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
)

# A hand-typed single-digit hour ("2025-06-06T2:15:00") is not ISO-8601 and
# plainly means 02:15.
_SINGLE_DIGIT_HOUR_RE = re.compile(r"([T ])(\d):(\d{2})")


def to_datetime(value: Any, *, pad_single_digit_hour: bool = False) -> datetime | None:
    """
    Read a spreadsheet cell as a datetime, or ``None`` when it is not one.

    A real date cell arrives as ``datetime``/``date`` and passes through; text
    is tried as ISO-8601 first, then against the layouts these spreadsheets
    actually use. A date with no time becomes midnight.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)

    text = str(value).strip()
    if not text:
        return None
    if pad_single_digit_hour:
        text = _SINGLE_DIGIT_HOUR_RE.sub(r"\g<1>0\g<2>:\g<3>", text)

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


# ============= EOF =============================================
