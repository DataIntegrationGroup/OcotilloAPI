"""Principal-existence check for permission_grant.

Only api_key has a local table today -- we don't have one for user or
principal_group yet, so they pass through unchecked.
"""

from sqlalchemy.orm import Session

from db.api_key import ApiKey


def principal_exists(session: Session, principal_type: str, principal_id: str) -> bool:
    """Whether principal_id is real for its principal_type."""
    if principal_type == "api_key":
        try:
            api_key_id = int(principal_id)
        except ValueError:
            return False
        return session.query(ApiKey).filter(ApiKey.id == api_key_id).first() is not None

    return True


# ============= EOF =============================================
