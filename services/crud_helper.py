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
from fastapi import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session, DeclarativeBase
from starlette.status import HTTP_204_NO_CONTENT

from db import NotesMixin
from services.query_helper import simple_get_by_id


def model_adder(session, table, model, user=None, **kwargs):
    """
    Helper function to add a new record to the database.
    """

    md = model.model_dump()
    if kwargs:
        md.update(kwargs)

    if user:
        # TODO: see note in "AuditMixin"
        md["created_by_id"] = user["sub"]
        md["created_by_name"] = user["name"]

    notes = None
    if issubclass(table, NotesMixin):
        notes = md.pop("notes", None)

    obj = table(**md)

    session.add(obj)
    session.commit()
    session.refresh(obj)

    if notes:
        for n in notes:
            note = obj.add_note(**n)
            session.add(note)

    session.commit()
    session.refresh(obj)
    return obj


def model_patcher(
    session: Session,
    model: DeclarativeBase,
    item_id: int,
    payload: BaseModel,
    user: dict = None,
):
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    item = simple_get_by_id(session, model, item_id)

    """
    Developer's notes

    exclude_unset ensures that fields that are not set in the payload do not
    update record fields to None
    """

    for key, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(item, NotesMixin) and key == "notes":
            # delete all notes and re-add
            for note in item.notes:
                session.delete(note)

            for note in value:
                note = item.add_note(**note)
                session.add(note)
        else:
            setattr(item, key, value)

    if user:
        item.updated_by_id = user["sub"]
        item.updated_by_name = user["name"]

    session.commit()
    session.refresh(item)
    return item


def model_deleter(session: Session, model: DeclarativeBase, item_id: int):
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    item = simple_get_by_id(session, model, item_id)
    session.delete(item)
    session.commit()
    return Response(status_code=HTTP_204_NO_CONTENT)


# ============= EOF =============================================
