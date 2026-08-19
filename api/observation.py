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
    amp_staging_dependency,
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
from schemas.transducer import (
    DeletedTransducerObservationsResponse,
    PublishedTransducerBlockResponse,
    PublishTransducerBlock,
    TransducerObservationWithBlockResponse,
)
from schemas.water_level_csv import WaterLevelBulkUploadResponse
from services.crud_helper import model_deleter, model_adder
from services.observation_helper import (
    get_observations,
    observation_model_patcher,
    get_observation_of_an_activity_type_by_id,
    get_transducer_observations,
)
from services.query_helper import simple_get_by_id
from services.transducer_helper import (
    delete_transducer_observations,
    publish_transducer_block,
)
from services.water_level_csv import bulk_upload_water_levels

router = APIRouter(prefix="/observation", tags=["observation"])


def _groundwater_level_parameter_id(session) -> int:
    """
    The lexicon id the transducer routes work in.

    Looked up rather than configured so the publish, read, and delete routes
    cannot drift onto different parameters.
    """
    return (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )


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
    "/transducer-groundwater-level/block",
    status_code=HTTP_201_CREATED,
    summary="Publish a corrected transducer series as one block",
)
def publish_transducer_groundwater_level_block(
    payload: PublishTransducerBlock,
    session: session_dependency,
    user: amp_staging_dependency,
    replace_overlapping: bool = False,
) -> PublishedTransducerBlockResponse:
    """
    Publish one corrected logger file as a single observation block.

    The block's time span is derived from the measurements; the client does not
    send it. Overlapping an existing block is a 409 listing the collisions --
    pass `replace_overlapping=true` to supersede them, which deletes those
    blocks and their readings in the same transaction.

    Written by the hydrograph corrector in OcotilloUI. See
    `docs/hydrograph-correction-publish.md`.
    """
    return publish_transducer_block(
        session, payload, user=user, replace_overlapping=replace_overlapping
    )


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
    sort: str | None = None,
    order: str | None = None,
) -> CustomPage[TransducerObservationWithBlockResponse]:
    """
    Retrieve transducer groundwater level observations paired with the block
    that covers them.

    `sort` accepts `observation_datetime`, `value`, or `id`; `order` accepts
    `asc` or `desc`. The default is newest first, so a client that wants the
    latest stored reading for a well can ask for size 1.
    """
    # Keyword arguments deliberately: the helper's fourth positional parameter
    # is `sensor_id`, so the previous positional call passed `start_time` as a
    # sensor id (unused, silently dropped), `end_time` as `start_time`, and
    # nothing as `end_time` -- an upper bound the caller asked for was ignored
    # and the lower bound came from the wrong argument.
    return get_transducer_observations(
        session,
        thing_id=thing_id,
        parameter_id=_groundwater_level_parameter_id(session),
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
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
    "/transducer-groundwater-level",
    status_code=HTTP_200_OK,
    summary="Delete transducer groundwater level observations in a time range",
)
def delete_transducer_groundwater_level_observations(
    session: session_dependency,
    user: amp_staging_dependency,
    thing_id: int,
    start_time: datetime,
    end_time: datetime,
) -> DeletedTransducerObservationsResponse:
    """
    Delete every transducer groundwater level reading for a well inside a
    closed time range, and reconcile the blocks that covered them: a block left
    with no readings is deleted, one left with some has its span narrowed to
    the survivors.

    All three parameters are required -- there is deliberately no form of this
    request that deletes everything for a well. Scoped exactly like the `GET`
    on this path, so the set previewed there is the set removed here.

    Irreversible, and it leaves the `transducer_daily_data` materialized view
    stale until its next refresh.
    """
    return delete_transducer_observations(
        session,
        thing_id=thing_id,
        parameter_id=_groundwater_level_parameter_id(session),
        start_time=start_time,
        end_time=end_time,
    )


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
