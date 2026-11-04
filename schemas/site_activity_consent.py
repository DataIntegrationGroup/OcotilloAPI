from pydantic import BaseModel, Field

from core.enums import SiteActivity
from schemas import PastOrTodayDate


# ------ RESPONSE ----------
class SiteActivityConsentResponse(BaseModel):
    """
    Even though allowed and start_date are not-nullable in the database, they
    are nullable here to accommodate cases where no consent record exists for
    a given activity.

    The columns were renamed from permission_type and permission_allowed, but
    the well response keeps those names on the wire through
    serialization_alias, because OcotilloUI reads them. Renaming the API
    fields is a separate, staged change.
    """

    activity: SiteActivity = Field(serialization_alias="permission_type")
    allowed: bool | None = Field(serialization_alias="permission_allowed")
    start_date: PastOrTodayDate | None
    end_date: PastOrTodayDate | None
