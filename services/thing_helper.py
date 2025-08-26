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
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND

from db import LocationThingAssociation, Thing, Base, Location
from schemas.location import LocationResponse
from db.group import Group, GroupThingAssociation
from services.audit_helper import audit_add
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
    with_location: bool = False,
    within: str = None,
):

    if query:
        sql = select(Thing).where(make_query(Thing, query))
    else:
        sql = select(Thing)

    if with_location or within:
        sql = sql.join(
            LocationThingAssociation, Thing.id == LocationThingAssociation.thing_id
        )
        sql = sql.join(Location)

    if thing_type:
        sql = sql.where(Thing.thing_type == thing_type)

    sql = order_sort_filter(sql, Thing, sort, order, filter_)
    if within:

        sql = make_within_wkt(sql, within)

    def transformer(records):
        thing_ids = sorted([record.id for record in records])
        subq = (
            select(
                LocationThingAssociation.thing_id,
                func.max(LocationThingAssociation.effective_start).label("max_start"),
            )
            .where(LocationThingAssociation.thing_id.in_(thing_ids))
            .group_by(LocationThingAssociation.thing_id)
            .subquery()
        )
        stmt = (
            select(Location)
            .join(
                LocationThingAssociation,
                Location.id == LocationThingAssociation.location_id,
            )
            .join(Thing)
            .join(
                subq,
                and_(
                    LocationThingAssociation.thing_id == subq.c.thing_id,
                    LocationThingAssociation.effective_start == subq.c.max_start,
                ),
            )
            .order_by(Thing.id.asc())
        )
        locations = session.scalars(stmt).all()

        for r, l in zip(records, locations):

            r.location = LocationResponse.model_validate(l)
            r.geometry = wkb_to_geojson(l.point) if l.point else None

        return records

    return paginate(query=sql, conn=session, transformer=transformer)


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


# REFACTOR TODO: use enums (or enum-like object) for thing_type
def add_thing(
    session: Session, data: BaseModel | dict, thing_type: str = None, user: dict = None
) -> Base:

    if isinstance(data, BaseModel):
        data = data.model_dump()

    location_id = data.pop("location_id", None)

    group_id = data.pop("group_id", None)
    if not group_id:
        group_name = data.pop("group", None)
        if group_name is not None:
            sql = select(Group).where(Group.name == group_name)
            dbg = session.scalars(sql).one_or_none()
            if dbg:
                group_id = dbg.id
            else:
                raise ValueError(f"Group '{group_name}' not found.")

    if not thing_type:
        thing_type = data.get("thing_type", None)
        if not thing_type:
            raise ValueError("Thing type must be specified.")

    thing = Thing(**data)
    thing.thing_type = thing_type

    audit_add(user, thing)

    session.add(thing)
    session.commit()
    session.refresh(thing)

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
    return thing


# ============= EOF =============================================
