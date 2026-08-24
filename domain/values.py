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


# ============= EOF =============================================
