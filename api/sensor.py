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
from sqlalchemy import select, and_
from starlette import status

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder, Observation
from db.sensor import Sensor
from schemas.sensor import SensorResponse, CreateSensor, UpdateSensor
from services.crud_helper import model_patcher, model_deleter
from services.error_helper import PydanticStyleException
from services.query_helper import order_sort_filter, simple_get_by_id

router = APIRouter(prefix="/sensor", tags=["sensor"])

# ====== POST ==================================================================


@router.post("", status_code=status.HTTP_201_CREATED)
def add_sensor(
    sensor_data: CreateSensor, session: session_dependency
) -> SensorResponse:
    """
    Add a sensor to the system.
    """
    return adder(session, Sensor, sensor_data)


# ====== PATCH =================================================================


@router.patch("/{sensor_id}", status_code=status.HTTP_200_OK)
def update_sensor(
    sensor_id: int, sensor_data: UpdateSensor, session: session_dependency
) -> SensorResponse:
    """
    Update a sensor in the system.
    """
    if (
        sensor_data.datetime_installed is not None
        and sensor_data.datetime_removed is None
    ):
        sensor = simple_get_by_id(session, Sensor, sensor_id)
        existing_datetime_removed = sensor.datetime_removed
        if (
            existing_datetime_removed is not None
            and sensor_data.datetime_installed >= existing_datetime_removed
        ):
            raise PydanticStyleException(
                status_code=status.HTTP_409_CONFLICT,
                loc=["body", "datetime_installed"],
                msg=f"new datetime installed must be before existing datetime removed of {existing_datetime_removed.isoformat().replace('+00:00', 'Z')}",
                type="value_error",
                input={
                    "datetime_installed": sensor_data.datetime_installed.isoformat().replace(
                        "+00:00", "Z"
                    )
                },
            )
    elif (
        sensor_data.datetime_installed is None
        and sensor_data.datetime_removed is not None
    ):
        sensor = simple_get_by_id(session, Sensor, sensor_id)
        existing_datetime_installed = sensor.datetime_installed
        if sensor_data.datetime_removed <= existing_datetime_installed:
            raise PydanticStyleException(
                status_code=status.HTTP_409_CONFLICT,
                loc=["body", "datetime_removed"],
                msg=f"new datetime removed must be after existing datetime installed of {existing_datetime_installed.isoformat().replace('+00:00', 'Z')}",
                type="value_error",
                input={
                    "datetime_removed": sensor_data.datetime_removed.isoformat().replace(
                        "+00:00", "Z"
                    )
                },
            )

    return model_patcher(session, Sensor, sensor_id, sensor_data)


# ====== DELETE ================================================================


@router.delete("/{sensor_id}")
def delete_sensor(sensor_id: int, session: session_dependency) -> Response:
    """
    Delete a sensor in the system
    """
    return model_deleter(session, Sensor, sensor_id)


# ====== GET ===================================================================


@router.get("", status_code=status.HTTP_200_OK)
def get_sensors(
    session: session_dependency,
    thing_id: int = None,  # Optional filter for thing_id
    observed_property: str = None,  # Optional filter for observed_property
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[SensorResponse]:
    """
    Retrieve all sensors from the system.
    This endpoint is a placeholder and should be implemented with actual logic.
    """
    sql = select(Sensor)
    # TODO: a sensor is not yet related to observation, so this won't work at the moment
    if thing_id is not None or observed_property is not None:
        conditions = []
        if observed_property is not None:
            conditions.append(Observation.observed_property == observed_property)
        if thing_id is not None:
            conditions.append(Observation.thing_id == thing_id)

        if conditions:
            sql = sql.join(Observation).where(and_(*conditions))

    sql = order_sort_filter(sql, Sensor, sort=sort, order=order, filter_=filter_)
    return paginate(conn=session, query=sql)


@router.get("/{sensor_id}", status_code=status.HTTP_200_OK)
def get_sensor(sensor_id: int, session: session_dependency) -> SensorResponse:
    """
    Retrieve a sensor by its ID.
    """
    return simple_get_by_id(session, Sensor, sensor_id)


# ============= EOF =============================================
