from pydantic import AwareDatetime

from schemas import BaseResponseModel


# RESPONSE ---------------------------------------------------------------------


class FieldActivityResponse(BaseResponseModel):
    field_event_id: int
    activity_type: str


class FieldEventResponse(BaseResponseModel):
    thing_id: int
    event_date: AwareDatetime
    notes: str | None
