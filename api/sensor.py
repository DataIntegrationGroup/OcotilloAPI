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

from fastapi import APIRouter, Query, Response
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from starlette import status

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    admin_dependency,
    editor_dependency,
    viewer_dependency,
)
from db import Observation, Sensor, Deployment, Thing
from schemas.sensor import SensorResponse, CreateSensor, UpdateSensor
from services.crud_helper import model_deleter, model_adder, model_patcher

# from services.exceptions_helper import PydanticStyleException
from services.query_helper import order_sort_filter, simple_get_by_id

router = APIRouter(prefix="/sensor", tags=["sensor"])

# ====== POST ==================================================================


@router.post("", status_code=status.HTTP_201_CREATED)
def add_sensor(
    sensor_data: CreateSensor, session: session_dependency, user: admin_dependency
) -> SensorResponse:
    """
    Add a sensor to the system.
    """
    return model_adder(session, Sensor, sensor_data, user=user)


# ====== PATCH =================================================================


# TODO: datetime_installed and datetime_removed have been moved from the Sensor model to the Deployment model. Do we need to keep the validation for datetime_installed and datetime_removed?


@router.patch("/{sensor_id}", status_code=status.HTTP_200_OK)
def update_sensor(
    sensor_id: int,
    sensor_data: UpdateSensor,
    session: session_dependency,
    user: editor_dependency,
) -> SensorResponse:
    """
    Update a sensor in the system.
    """
    # if (
    #     sensor_data.datetime_installed is not None
    #     and sensor_data.datetime_removed is None
    # ):
    #     sensor = simple_get_by_id(session, Sensor, sensor_id)
    #     existing_datetime_removed = sensor.datetime_removed
    #     if (
    #         existing_datetime_removed is not None
    #         and sensor_data.datetime_installed >= existing_datetime_removed
    #     ):
    #         detail = {
    #             "loc": ["body", "datetime_installed"],
    #             "msg": f"new datetime installed must be before existing datetime removed of {existing_datetime_removed.isoformat().replace('+00:00', 'Z')}",
    #             "type": "value_error",
    #             "input": {
    #                 "datetime_installed": sensor_data.datetime_installed.isoformat().replace(
    #                     "+00:00", "Z"
    #                 )
    #             },
    #         }
    #         raise PydanticStyleException(
    #             status_code=status.HTTP_409_CONFLICT, detail=[detail]
    #         )
    # elif (
    #     sensor_data.datetime_installed is None
    #     and sensor_data.datetime_removed is not None
    # ):
    #     sensor = simple_get_by_id(session, Sensor, sensor_id)
    #     existing_datetime_installed = sensor.datetime_installed
    #     if sensor_data.datetime_removed <= existing_datetime_installed:
    #         detail = {
    #             "loc": ["body", "datetime_removed"],
    #             "msg": f"new datetime removed must be after existing datetime installed of {existing_datetime_installed.isoformat().replace('+00:00', 'Z')}",
    #             "type": "value_error",
    #             "input": {
    #                 "datetime_removed": sensor_data.datetime_removed.isoformat().replace(
    #                     "+00:00", "Z"
    #                 )
    #             },
    #         }
    #         raise PydanticStyleException(
    #             status_code=status.HTTP_409_CONFLICT, detail=[detail]
    #         )
    #
    return model_patcher(session, Sensor, sensor_id, sensor_data, user=user)


# ====== DELETE ================================================================


@router.delete("/{sensor_id}")
def delete_sensor(
    sensor_id: int, session: session_dependency, user: admin_dependency
) -> Response:
    """
    Delete a sensor in the system
    """
    return model_deleter(session, Sensor, sensor_id)


# ====== GET ===================================================================


@router.get("", status_code=status.HTTP_200_OK)
def get_sensors(
    session: session_dependency,
    user: viewer_dependency,
    thing_id: int = None,  # Optional filter for thing_id. Filter by the Thing where equipment is deployed
    parameter_id: int = None,  # Filter by the parameter the sensor/equipment measures
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[SensorResponse]:
    """
    Retrieve all sensors from the system.
    This endpoint is a placeholder and should be implemented with actual logic.
    """
    sql = select(Sensor)
    # --- Logic to filter by Thing ---
    # The path is now: Sensor <-> Deployment <-> Thing
    if thing_id is not None:
        sql = sql.join(Deployment).join(Thing).where(Thing.id == thing_id)

    # --- Logic to filter by Parameter ---
    # The path is now: Sensor <-> Observation <-> Parameter
    if parameter_id is not None:
        sql = sql.join(Observation).where(Observation.parameter_id == parameter_id)

    sql = order_sort_filter(sql, Sensor, sort=sort, order=order, filter_=filter_)
    return paginate(conn=session, query=sql)


@router.get("/{sensor_id}", status_code=status.HTTP_200_OK)
def get_sensor(
    sensor_id: int, session: session_dependency, user: viewer_dependency
) -> SensorResponse:
    """
    Retrieve a sensor by its ID.
    """
    return simple_get_by_id(session, Sensor, sensor_id)


# ============= EOF =============================================
