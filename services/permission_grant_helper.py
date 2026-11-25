"""Principal-existence check for permission_grant.

Only api_key has a local table today -- we don't have one for user or
principal_group yet, so they pass through unchecked.
"""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.api_key import ApiKey
from domain.api_key import is_usable

# ApiKey.id is a Postgres `integer` column; larger values overflow it.
_API_KEY_ID_PATTERN = re.compile(r"^[0-9]+$")
_POSTGRES_INT_MAX = 2_147_483_647


def principal_exists(session: Session, principal_type: str, principal_id: str) -> bool:
    """Whether principal_id is real for its principal_type."""
    if principal_type == "api_key":
        if not _API_KEY_ID_PATTERN.match(principal_id):
            return False
        api_key_id = int(principal_id)
        if api_key_id > _POSTGRES_INT_MAX:
            return False
        key = session.get(ApiKey, api_key_id)
        return key is not None and is_usable(
            key.revoked_at, key.expires_at, datetime.now(timezone.utc)
        )

    if principal_type in ("user", "principal_group"):
        # No local table exists for either type.
        return True

    return False


# ============= EOF =============================================
