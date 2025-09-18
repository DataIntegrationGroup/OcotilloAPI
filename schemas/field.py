from pydantic import AwareDatetime

from schemas import BaseResponseModel


# RESPONSE ---------------------------------------------------------------------


class FieldEventResponse(BaseResponseModel):
    thing_id: int
    event_date: AwareDatetime
    event_lead_name: str
    collecting_organization: str | None
    notes: str | None
