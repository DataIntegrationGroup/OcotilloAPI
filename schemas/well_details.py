from pydantic import BaseModel, ConfigDict, Field

from core.enums import ActivityType, SampleMatrix, SampleMethod, SampleQcType
from schemas import BaseResponseModel, UTCAwareDatetime
from schemas.contact import ContactResponse
from schemas.deployment import DeploymentResponse
from schemas.field import FieldEventParticipantResponse
from schemas.observation import ObservationResponse
from schemas.sensor import SensorResponse
from schemas.thing import WellResponse, WellScreenBaseResponse


class WellDetailsFieldEventSampleResponse(BaseResponseModel):
    contact: ContactResponse | None = None
    sample_date: UTCAwareDatetime
    sample_name: str
    sample_matrix: SampleMatrix
    sample_method: SampleMethod
    qc_type: SampleQcType
    notes: str | None = None
    depth_top: float | None = None
    depth_bottom: float | None = None
    observations: list[ObservationResponse] = Field(default_factory=list)


class WellDetailsFieldActivityResponse(BaseResponseModel):
    field_event_id: int
    activity_type: ActivityType
    notes: str | None = None
    samples: list[WellDetailsFieldEventSampleResponse] = Field(default_factory=list)


class WellDetailsFieldEventResponse(BaseResponseModel):
    thing_id: int
    event_date: UTCAwareDatetime
    notes: str | None = None
    field_event_participants: list[FieldEventParticipantResponse] = Field(
        default_factory=list
    )
    field_activities: list[WellDetailsFieldActivityResponse] = Field(
        default_factory=list
    )


class WellDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    well: WellResponse
    contacts: list[ContactResponse] = Field(default_factory=list)
    sensors: list[SensorResponse] = Field(default_factory=list)
    deployments: list[DeploymentResponse] = Field(default_factory=list)
    well_screens: list[WellScreenBaseResponse] = Field(default_factory=list)
    field_events: list[WellDetailsFieldEventResponse] = Field(default_factory=list)
    first_field_event: WellDetailsFieldEventResponse | None = None
