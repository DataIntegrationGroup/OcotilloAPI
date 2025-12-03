from pydantic import BaseModel
from schemas import PastOrTodayDate

from core.enums import PermissionType


# ------ RESPONSE ----------
class PermissionHistoryResponse(BaseModel):
    """
    Even though permission_allowed and start_date are not-nullable in the
    database, they are nullable here to accommodate cases where no permission
    record exists for a given permission type.
    """

    permission_type: PermissionType
    permission_allowed: bool | None
    start_date: PastOrTodayDate | None
    end_date: PastOrTodayDate | None
