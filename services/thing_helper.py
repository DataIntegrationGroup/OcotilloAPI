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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import LocationThingAssociation, Thing, WellThing, SpringThing, Base
from db.group import Group, GroupThingAssociation


def add_well(session: Session, data: BaseModel | dict) -> WellThing:
    return _add_child_thing(session, WellThing, data)


def add_spring(session: Session, data: BaseModel | dict) -> SpringThing:
    return _add_child_thing(session, SpringThing, data)


def _add_child_thing(session: Session, table, data: BaseModel | dict) -> Base:

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

    thing = Thing()
    thing.name = data.pop("name")
    session.add(thing)
    session.commit()
    session.refresh(thing)

    if group_id:
        assoc = GroupThingAssociation()
        assoc.group_id = group_id
        assoc.thing_id = thing.id
        session.add(assoc)

    obj = table(**data)
    obj.thing_id = thing.id
    session.add(obj)
    session.commit()
    session.refresh(obj)

    if location_id is not None:
        assoc = LocationThingAssociation()

        assoc.location_id = location_id
        assoc.thing_id = thing.id
        session.add(assoc)

    session.commit()
    return obj


# ============= EOF =============================================
