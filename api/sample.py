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
from sqlalchemy.exc import IntegrityError, ProgrammingError
from starlette.status import HTTP_201_CREATED, HTTP_409_CONFLICT

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    admin_dependency,
    editor_dependency,
    viewer_dependency,
)
from db.sample import Sample
from schemas import ResourceNotFoundResponse
from schemas.sample import SampleResponse, CreateSample, UpdateSample
from services.query_helper import simple_get_by_id
from services.crud_helper import model_patcher, model_deleter, model_adder
from services.exceptions_helper import PydanticStyleException
from services.sample_helper import get_db_samples

router = APIRouter(
    prefix="/sample",
    tags=["sample"],
)


# TODO: add the following database validation handlers
# invalid sample_id
# invalid lexicon terms
# sample_date of the Sample model cannot be before the event_date of the FieldEvent model


def database_error_handler(
    payload: CreateSample | UpdateSample, error: IntegrityError | ProgrammingError
) -> None:
    """
    Handle errors raised by the database when adding or updating a sample.
    """
    error_message = error.orig.args[0]["M"]
    if (
        error_message
        == 'duplicate key value violates unique constraint "sample_sample_name_key"'
    ):
        detail = {
            "loc": ["body", "sample_name"],
            "msg": f"Sample with sample_name {payload.sample_name} already exists.",
            "type": "value_error",
            "input": {"sample_name": payload.sample_name},
        }
    elif (
        error_message
        == 'insert or update on table "sample" violates foreign key constraint "sample_field_activity_id_fkey"'
    ):
        detail = {
            "loc": ["body", "field_activity_id"],
            "msg": f"FieldActivity with ID {payload.field_activity_id} does not exist.",
            "type": "value_error",
            "input": {"field_activity_id": payload.field_activity_id},
        }

    raise PydanticStyleException(status_code=HTTP_409_CONFLICT, detail=[detail])


# ============= Post =============================================
@router.post("", status_code=HTTP_201_CREATED)
async def add_sample(
    sample_data: CreateSample, session: session_dependency, user: admin_dependency
) -> SampleResponse:
    """
    Endpoint to add a sample.
    """
    try:
        # since this is only one instance N+1 is not a concern for
        # FieldActivity, FieldEvent, and Thing
        return model_adder(session, Sample, sample_data, user=user)
    except (IntegrityError, ProgrammingError) as e:
        database_error_handler(sample_data, e)


# ============= Update =============================================
@router.patch("/{sample_id}", summary="Update Sample")
async def update_sample(
    sample_id: int,
    sample_data: UpdateSample,
    session: session_dependency,
    user: editor_dependency,
) -> SampleResponse | ResourceNotFoundResponse:
    """
    Endpoint to update a sample.
    """
    try:
        # since this is only one instance N+1 is not a concern for
        # FieldActivity, FieldEvent, and Thing
        return model_patcher(session, Sample, sample_id, sample_data, user=user)
    except (IntegrityError, ProgrammingError) as e:
        database_error_handler(sample_data, e)


# ============= Get =============================================
@router.get("", summary="Get Samples")
async def get_samples(
    session: session_dependency,
    user: viewer_dependency,
    thing_id: int | None = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[SampleResponse]:
    """
    Endpoint to retrieve samples.
    """
    return get_db_samples(session, thing_id, sort=sort, order=order, filter_=filter_)


@router.get("/{sample_id}", summary="Get Sample by ID")
async def get_sample_by_id(
    sample_id: int, session: session_dependency, user: viewer_dependency
) -> SampleResponse | ResourceNotFoundResponse:
    """
    Endpoint to retrieve a sample by its ID.
    """
    # since this is only one instance N+1 is not a concern
    # FieldActivity, FieldEvent, and Thing
    return simple_get_by_id(session, Sample, sample_id)


# ======= DELETE ===============================================================


@router.delete("/{sample_id}", summary="Delete Sample by ID")
async def delete_sample_by_id(
    sample_id: int, session: session_dependency, user: admin_dependency
) -> Response:
    return model_deleter(session, Sample, sample_id)


# # ============= EOF =============================================
