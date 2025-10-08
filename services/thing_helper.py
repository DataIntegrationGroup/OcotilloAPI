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
from fastapi import Request
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session, aliased
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from db import LocationThingAssociation, Thing, Base, Location, WellScreen
from db.group import GroupThingAssociation
from services.audit_helper import audit_add
from services.crud_helper import model_patcher
from services.exceptions_helper import PydanticStyleException
from services.geospatial_helper import make_within_wkt
from services.query_helper import make_query, order_sort_filter, simple_get_by_id
from shapely import wkb
from shapely.geometry import mapping


def wkb_to_geojson(wkb_element):
    if wkb_element is None:
        return None
    geom = wkb.loads(bytes(wkb_element.data))
    return mapping(geom)


def get_db_things(
    filter_,
    order,
    query,
    session,
    sort,
    thing_type: str = None,
    within: str = None,
) -> list:

    if query:
        sql = select(Thing).where(make_query(Thing, query))
    else:
        sql = select(Thing)

    if thing_type:
        sql = sql.where(Thing.thing_type == thing_type)

    if within:
        latest_assoc = (
            select(
                LocationThingAssociation.thing_id,
                func.max(LocationThingAssociation.effective_start).label("max_start"),
            )
            .group_by(LocationThingAssociation.thing_id)
            .subquery()
        )

        lta_alias = aliased(LocationThingAssociation)
        sql = (
            sql.join(lta_alias, Thing.id == lta_alias.thing_id)
            .join(Location, lta_alias.location_id == Location.id)
            .join(
                latest_assoc,
                (latest_assoc.c.thing_id == lta_alias.thing_id)
                & (latest_assoc.c.max_start == lta_alias.effective_start),
            )
        )
        sql = make_within_wkt(sql, within)

    sql = order_sort_filter(sql, Thing, sort, order, filter_)

    return paginate(query=sql, conn=session)


def get_thing_type_from_request(request: Request) -> str:
    path = request.url.path
    path_components = path.split("/")
    if len(path_components) == 2:
        # no thing type specified in path
        thing_type_in_path = path_components[1]
    if len(path_components) >= 3:
        # thing type specified in path
        thing_type_in_path = path_components[2]

    thing_type = thing_type_in_path.replace("-", " ")
    return thing_type


def verify_thing_type_correspondence(thing: Thing, request: Request):
    thing_type = get_thing_type_from_request(request)
    if thing.thing_type != thing_type:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "thing_id"],
                    "type": "value_error",
                    "input": {"thing_id": thing.id},
                    "msg": f"Thing with ID {thing.id} is not a {thing_type} Thing. It is a {thing.thing_type} Thing.",
                }
            ],
        )


def get_thing_of_a_thing_type_by_id(session: Session, request: Request, thing_id: int):
    thing = simple_get_by_id(session, Thing, thing_id)

    verify_thing_type_correspondence(thing, request)

    return thing


def add_thing(
    session: Session,
    data: BaseModel | dict,
    user: dict = None,
    request: Request | None = None,
    thing_type: str | None = None,  # to be used only for data transfers, not the API
) -> Base:
    if request is not None:
        thing_type = get_thing_type_from_request(request)

    if isinstance(data, BaseModel):
        data = data.model_dump()

    location_id = data.pop("location_id", None)
    group_id = data.pop("group_id", None)

    try:
        thing = Thing(**data)
        thing.thing_type = thing_type

        audit_add(user, thing)

        session.add(thing)
        session.flush()
        session.refresh(thing)

        # endpoint catches ProgrammingError if location_id or group_id do not exist
        if group_id:
            assoc = GroupThingAssociation()
            audit_add(user, assoc)
            assoc.group_id = group_id
            assoc.thing_id = thing.id
            session.add(assoc)

        if location_id is not None:
            assoc = LocationThingAssociation()
            audit_add(user, assoc)
            assoc.location_id = location_id
            assoc.thing_id = thing.id
            session.add(assoc)

        session.commit()
        session.refresh(thing)
    except Exception as e:
        session.rollback()
        raise e

    return thing


def add_well_screen(session, well_screen_data: BaseModel, user: dict = None):
    try:
        well_screen_data_dump = well_screen_data.model_dump()
        well_screen = WellScreen(**well_screen_data_dump)
        audit_add(user, well_screen)

        session.add(well_screen)
        session.flush()

        thing = session.get(Thing, well_screen_data.thing_id)
        if thing.thing_type != "water well":
            raise PydanticStyleException(
                status_code=HTTP_409_CONFLICT,
                detail=[
                    {
                        "loc": ["body", "thing_id"],
                        "type": "value_error",
                        "input": {"thing_id": thing.id},
                        "msg": f"Thing with ID {thing.id} is not a water well Thing. It is a {thing.thing_type} Thing.",
                    }
                ],
            )

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    return well_screen


def patch_thing(
    session: Session,
    request: Request,
    thing_id: int,
    payload: BaseModel,
    user: dict,
):
    thing = simple_get_by_id(session, Thing, thing_id)

    verify_thing_type_correspondence(thing, request)

    thing = model_patcher(session, Thing, thing_id, payload, user)
    return thing


# ============= EOF =============================================
