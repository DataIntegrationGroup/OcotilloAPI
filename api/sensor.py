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

from fastapi import APIRouter, Depends, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder, Observation
from db.engine import get_db_session
from db.sensor import Sensor
from schemas.sensor import SensorResponse, CreateSensor
from services.query_helper import order_sort_filter, simple_get_by_id

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
def get_sensor(
    sensor_id: int, session: Session = Depends(get_db_session)
) -> SensorResponse:

    return simple_get_by_id(session, Sensor, sensor_id)


# ============= EOF =============================================
