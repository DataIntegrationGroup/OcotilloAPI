import os


def to_bool(value: str) -> bool | str:
    """Convert common string environment values to booleans."""
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    return value


def get_bool_env(key, default=False):
    return to_bool(os.getenv(key, default))
