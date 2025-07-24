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
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import LocationThingAssociation, Thing, Base
from db.group import Group, GroupThingAssociation
from services.query_helper import make_query, order_sort_filter


def get_db_things(
    filter_, order, query, session, sort, thing_type: str | list[str] = None
):
    if query:
        sql = select(Thing).where(make_query(Thing, query))
    else:
        sql = select(Thing)

    if isinstance(thing_type, str):
        thing_type = thing_type.lower()
        thing_type = [thing_type]
    elif isinstance(thing_type, list):
        thing_type = [t.lower() for t in thing_type]

    sql = sql.where(Thing.thing_type.in_(thing_type)) if thing_type else sql
    sql = order_sort_filter(sql, Thing, sort, order, filter_)
    return paginate(query=sql, conn=session)


def add_thing(session: Session, data: BaseModel | dict, thing_type: str = None) -> Base:

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
    session.add(thing)
    session.commit()
    session.refresh(thing)

    if group_id:
        assoc = GroupThingAssociation()
        assoc.group_id = group_id
        assoc.thing_id = thing.id
        session.add(assoc)

    if location_id is not None:
        assoc = LocationThingAssociation()

        assoc.location_id = location_id
        assoc.thing_id = thing.id
        session.add(assoc)

    session.commit()
    return thing


# ============= EOF =============================================
