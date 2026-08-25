from pydantic import BaseModel

from core.enums import PermissionType
from schemas import PastOrTodayDate


# ------ RESPONSE ----------
class FieldAccessConsentResponse(BaseModel):
    """
    Landowner field-access consent, as published on a Thing. Not an
    access-control grant (ADR5).

    Even though permission_allowed and start_date are not-nullable in the
    database, they are nullable here to accommodate cases where no permission
    record exists for a given permission type.
    """

    permission_type: PermissionType
    permission_allowed: bool | None
    start_date: PastOrTodayDate | None
    end_date: PastOrTodayDate | None
