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
from datetime import datetime

from fastapi import APIRouter, Query, Request, UploadFile, File, HTTPException
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    amp_admin_dependency,
    amp_editor_dependency,
    amp_viewer_dependency,
)
from db import Observation, Parameter
from schemas.observation import (
    CreateGroundwaterLevelObservation,
    GroundwaterLevelObservationResponse,
    CreateWaterChemistryObservation,
    WaterChemistryObservationResponse,
    ObservationResponse,
    UpdateGroundwaterLevelObservation,
    UpdateWaterChemistryObservation,
)
from schemas.transducer import TransducerObservationWithBlockResponse
from schemas.water_level_csv import WaterLevelBulkUploadResponse
from services.crud_helper import model_deleter, model_adder
from services.observation_helper import (
    get_observations,
    observation_model_patcher,
    get_observation_of_an_activity_type_by_id,
    get_transducer_observations,
)
from services.query_helper import simple_get_by_id
from services.water_level_csv import bulk_upload_water_levels

router = APIRouter(prefix="/observation", tags=["observation"])

"""
TODO

- add validation that the sample_id exists in the database before creating observation
- add validation that the activity_type of the sample corresponds with the endpoint where the observation is posted/patched
"""


# ============= Post =============================================
@router.post("/groundwater-level", status_code=HTTP_201_CREATED)
def add_groundwater_level_observation(
    obs_data: CreateGroundwaterLevelObservation,
    session: session_dependency,
    user: amp_admin_dependency,
) -> GroundwaterLevelObservationResponse:
    """
    Add a new groundwater observation to the database.
    """
    return model_adder(session, Observation, obs_data, user=user)


@router.post("/water-chemistry", status_code=HTTP_201_CREATED)
def add_water_chemistry_observation(
    obs_data: CreateWaterChemistryObservation,
    session: session_dependency,
    user: amp_admin_dependency,
) -> WaterChemistryObservationResponse:
    """
    Add a new water chemistry observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    return model_adder(session, Observation, obs_data, user=user)


@router.post(
    "/groundwater-level/bulk-upload",
    response_model=WaterLevelBulkUploadResponse,
    status_code=HTTP_200_OK,
)
async def bulk_upload_groundwater_levels(
    user: amp_admin_dependency,
    file: UploadFile = File(...),
):
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    result = bulk_upload_water_levels(contents)

    if result.exit_code != 0:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=result.payload)

    return result.payload


# PATCH ========================================================================


@router.patch("/groundwater-level/{observation_id}", status_code=HTTP_200_OK)
def update_groundwater_level_observation(
    observation_id: int,
    obs_data: UpdateGroundwaterLevelObservation,
    session: session_dependency,
    user: amp_editor_dependency,
    request: Request,
) -> GroundwaterLevelObservationResponse:
    """
    Update an existing groundwater level observation in the database.
    """
    return observation_model_patcher(session, request, observation_id, obs_data, user)


@router.patch("/water-chemistry/{observation_id}", status_code=HTTP_200_OK)
def update_water_chemistry_observation(
    observation_id: int,
    obs_data: UpdateWaterChemistryObservation,
    session: session_dependency,
    user: amp_editor_dependency,
    request: Request,
) -> WaterChemistryObservationResponse:
    """
    Update an existing water chemistry observation in the database.
    """
    return observation_model_patcher(session, request, observation_id, obs_data, user)


# ============= Get ==============================================
@router.get(
    "/transducer-groundwater-level",
    summary="Get transducer groundwater level observations",
)
def get_transducer_groundwater_level_observations(
    request: Request,
    session: session_dependency,
    user: amp_viewer_dependency,
    thing_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> CustomPage[TransducerObservationWithBlockResponse]:

    groundwater_parameter_id = (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )

    return get_transducer_observations(
        session, thing_id, groundwater_parameter_id, start_time, end_time
    )


@router.get("/groundwater-level", summary="Get groundwater level observations")
def get_groundwater_level_observations(
    request: Request,
    session: session_dependency,
    user: amp_viewer_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[GroundwaterLevelObservationResponse]:
    """
    Retrieve all groundwater level observations from the database.
    """
    return get_observations(
        request=request,
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get(
    "/groundwater-level/{observation_id}",
    summary="Get groundwater level observation by ID",
)
def get_groundwater_level_observation_by_id(
    session: session_dependency,
    request: Request,
    user: amp_viewer_dependency,
    observation_id: int,
) -> GroundwaterLevelObservationResponse:
    return get_observation_of_an_activity_type_by_id(
        session=session,
        request=request,
        observation_id=observation_id,
    )


@router.get("/water-chemistry", summary="Get water chemistry observations")
def get_water_chemistry_observations(
    request: Request,
    session: session_dependency,
    user: amp_viewer_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[WaterChemistryObservationResponse]:
    """
    Retrieve all water chemistry observations from the database.
    """
    return get_observations(
        request=request,
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get(
    "/water-chemistry/{observation_id}", summary="Get water chemistry observation by ID"
)
def get_water_chemistry_observation_by_id(
    session: session_dependency,
    request: Request,
    user: amp_viewer_dependency,
    observation_id: int,
) -> WaterChemistryObservationResponse:
    return get_observation_of_an_activity_type_by_id(
        session=session,
        request=request,
        observation_id=observation_id,
    )


@router.get("", summary="Get all observations")
def get_all_observations(
    request: Request,
    session: session_dependency,
    user: amp_viewer_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[ObservationResponse]:
    return get_observations(
        request=request,
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get("/{observation_id}", summary="Get an observation by its ID")
def get_observation_by_id(
    session: session_dependency, user: amp_viewer_dependency, observation_id: int
) -> ObservationResponse:
    return simple_get_by_id(session, Observation, observation_id)


# DELETE =======================================================================


@router.delete(
    "/{observation_id}",
    summary="Delete an observation",
    status_code=HTTP_204_NO_CONTENT,
)
def delete_observation(
    session: session_dependency, user: amp_admin_dependency, observation_id: int
) -> None:
    return model_deleter(session, Observation, observation_id)


# ============= EOF =============================================
