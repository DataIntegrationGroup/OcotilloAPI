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
from typing import Any

from fastapi import Response
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Session
from starlette.status import HTTP_204_NO_CONTENT

from db.notes import NotesMixin
from services.edit_notification_helper import EditEvent, notify_edit_event
from services.query_helper import simple_get_by_id

TABLE_RESOURCE_TYPES: dict[str, str] = {
    "contact": "contact",
    "group": "group",
    "asset": "asset",
    "location": "location",
    "sensor": "sensor",
    "sample": "sample",
}


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

    if user:
        resource_type = _resource_type_for_item(table, obj)
        if resource_type:
            label = _resource_label(obj)
            notify_edit_event(
                user,
                EditEvent(
                    action="record_created",
                    resource_type=resource_type,
                    resource_id=obj.id,
                    resource_label=label,
                    summary=f"Created {resource_type} {label}",
                ),
            )

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
    updates = payload.model_dump(exclude_unset=True)
    before = _snapshot_field_values(item, updates.keys())

    for key, value in updates.items():
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

    if user:
        resource_type = _resource_type_for_item(model, item)
        if resource_type:
            label = _resource_label(item)
            field_changes = _compute_field_changes(
                before, item, updates.keys()
            )
            summary = f"Updated {resource_type} {label}"
            notify_edit_event(
                user,
                EditEvent(
                    action="record_updated",
                    resource_type=resource_type,
                    resource_id=item.id,
                    resource_label=label,
                    summary=summary,
                    field_changes=field_changes or None,
                ),
            )

    return item


def model_deleter(
    session: Session,
    model: DeclarativeBase,
    item_id: int,
    user: dict | None = None,
):
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    item = simple_get_by_id(session, model, item_id)
    resource_type = _resource_type_for_item(model, item)
    label = _resource_label(item)
    item_id_value = item.id

    session.delete(item)
    session.commit()

    if user and resource_type:
        notify_edit_event(
            user,
            EditEvent(
                action="record_deleted",
                resource_type=resource_type,
                resource_id=item_id_value,
                resource_label=label,
                summary=f"Deleted {resource_type} {label}",
            ),
        )

    return Response(status_code=HTTP_204_NO_CONTENT)


def _resource_type_for_item(model: type, item: Any) -> str | None:
    table = getattr(model, "__tablename__", None)
    if table == "thing":
        thing_type = getattr(item, "thing_type", None)
        if thing_type == "water well":
            return "well"
        if thing_type == "spring":
            return "spring"
        return "thing"
    return TABLE_RESOURCE_TYPES.get(table or "")


def _resource_label(item: Any) -> str:
    for attr in ("name", "label", "title", "site_name"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    item_id = getattr(item, "id", None)
    return f"ID {item_id}" if item_id is not None else "record"


def _snapshot_field_values(item: Any, keys: Any) -> dict[str, Any]:
    return {
        key: _serialize_field_value(getattr(item, key, None)) for key in keys
    }


def _compute_field_changes(
    before: dict[str, Any],
    item: Any,
    keys: Any,
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for key in keys:
        after_value = _serialize_field_value(getattr(item, key, None))
        if before.get(key) != after_value:
            changes[key] = {"before": before.get(key), "after": after_value}
    return changes


def _serialize_field_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "wkt"):
        return value.wkt
    if isinstance(value, (list, dict)):
        return value
    return value


# ============= EOF =============================================
