"""Pure validation rules for permission_grant.

Checks a value against core/enums.py (built from core/lexicon.json) and
raises ValueError early, before the database's own FK constraint would.
"""

from enum import Enum

from core.enums import Capability, PrincipalType, ScopeType


def _validate_against_enum(value: str, enum_cls: type[Enum], field_name: str) -> None:
    try:
        enum_cls(value)
    except ValueError:
        raise ValueError(f"Invalid {field_name}: {value!r}")


def validate_principal_type(principal_type: str) -> None:
    _validate_against_enum(principal_type, PrincipalType, "principal_type")


def validate_capability(capability: str) -> None:
    _validate_against_enum(capability, Capability, "capability")


def validate_scope_type(scope_type: str) -> None:
    _validate_against_enum(scope_type, ScopeType, "scope_type")


# ============= EOF =============================================
