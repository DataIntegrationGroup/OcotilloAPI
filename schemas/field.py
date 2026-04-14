from pydantic import AwareDatetime

from schemas import BaseResponseModel
from core.enums import ActivityType
from schemas.contact import ContactResponse

# RESPONSE ---------------------------------------------------------------------


class FieldActivityResponse(BaseResponseModel):
    field_event_id: int
    activity_type: ActivityType


class FieldEventResponse(BaseResponseModel):
    thing_id: int
    event_date: AwareDatetime
    notes: str | None


class FieldEventParticipantResponse(BaseResponseModel):
    field_event_id: int
    contact_id: int
    participant_role: str
    participant: ContactResponse
