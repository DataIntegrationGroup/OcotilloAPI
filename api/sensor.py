# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder
from db.sensor import Sensor
from db.engine import get_db_session
from schemas_v2.sensor import SensorResponse, CreateSensor
from services.query_helper import paginated_all_getter

router = APIRouter(prefix="/sensor", tags=["sensor"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_sensor(
    sensor_data: CreateSensor, session: Session = Depends(get_db_session)
) -> SensorResponse:
    """
    Add a sensor to the system.
    This endpoint is a placeholder and should be implemented with actual logic.
    """
    return adder(session, Sensor, sensor_data)


@router.get("", status_code=status.HTTP_200_OK)
def get_sensors(session: session_dependency) -> CustomPage[SensorResponse]:
    """
    Retrieve all sensors from the system.
    This endpoint is a placeholder and should be implemented with actual logic.
    """
    return paginated_all_getter(session, Sensor)


@router.get("/{sensor_id}", status_code=status.HTTP_200_OK)
def get_sensor(
    sensor_id: int, session: Session = Depends(get_db_session)
) -> SensorResponse:

    sensor = session.get(Sensor, sensor_id)
    return sensor


# ============= EOF =============================================
