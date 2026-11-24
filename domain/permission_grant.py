"""Pure validation rules for permission_grant.

Reads core/lexicon.json directly -- domain/ must stay database-free (ADR4).
"""

import json
from pathlib import Path

_LEXICON_PATH = Path(__file__).parent.parent / "core" / "lexicon.json"

_CACHE: dict[str, set[str]] | None = None


def _allowed_terms(category: str) -> set[str]:
    global _CACHE
    if _CACHE is None:
        raw = json.loads(_LEXICON_PATH.read_text(encoding="utf-8"))
        by_category: dict[str, set[str]] = {}
        for term in raw["terms"]:
            for name in term["categories"]:
                by_category.setdefault(name, set()).add(term["term"])
        _CACHE = by_category
    return _CACHE.get(category, set())


def _validate_against_lexicon(value: str, category: str, field_name: str) -> None:
    if value not in _allowed_terms(category):
        raise ValueError(f"Invalid {field_name}: {value!r}")


def validate_principal_type(principal_type: str) -> None:
    _validate_against_lexicon(principal_type, "principal_type", "principal_type")


def validate_capability(capability: str) -> None:
    _validate_against_lexicon(capability, "capability", "capability")


def validate_scope_type(scope_type: str) -> None:
    _validate_against_lexicon(scope_type, "scope_type", "scope_type")


# ============= EOF =============================================
