from datetime import date

from schemas import BaseResponseModel
from schemas.sensor import SensorResponse


class DeploymentResponse(BaseResponseModel):
    thing_id: int
    sensor: SensorResponse
    installation_date: date
    removal_date: date | None
    recording_interval: int | None
    recording_interval_units: str | None
    hanging_cable_length: float | None
    hanging_point_height: float | None
    hanging_point_description: str | None
    notes: str | None
