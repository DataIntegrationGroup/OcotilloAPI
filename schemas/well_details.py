from pydantic import BaseModel, ConfigDict, Field

from schemas.contact import ContactResponse
from schemas.deployment import DeploymentResponse
from schemas.observation import GroundwaterLevelObservationResponse
from schemas.sample import SampleResponse
from schemas.field import FieldEventParticipantResponse
from schemas.sensor import SensorResponse
from schemas.thing import WellResponse, WellScreenResponse


class WellDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    well: WellResponse
    contacts: list[ContactResponse] = Field(default_factory=list)
    sensors: list[SensorResponse] = Field(default_factory=list)
    deployments: list[DeploymentResponse] = Field(default_factory=list)
    well_screens: list[WellScreenResponse] = Field(default_factory=list)
    recent_groundwater_level_observations: list[GroundwaterLevelObservationResponse] = (
        Field(default_factory=list)
    )
    latest_field_event_sample: SampleResponse | None = None
    field_event_participants: list[FieldEventParticipantResponse] = Field(
        default_factory=list
    )
