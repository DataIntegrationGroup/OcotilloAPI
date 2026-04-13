from pydantic import BaseModel, ConfigDict, Field

from schemas.contact import ContactResponse
from schemas.deployment import DeploymentResponse
from schemas.sensor import SensorResponse
from schemas.thing import WellResponse


class WellExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    well: WellResponse
    contacts: list[ContactResponse] = Field(default_factory=list)
    sensors: list[SensorResponse] = Field(default_factory=list)
    deployments: list[DeploymentResponse] = Field(default_factory=list)
