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
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import (
    Contact,
    Email,
    Phone,
    Address,
    Thing,
    Asset,
    AssetThingAssociation,
    search,
)
from db.engine import get_db_session

router = APIRouter(prefix="/search", tags=["search"])


def _get_contact_results(session: Session, q: str) -> list[dict]:
    vector = (
        Contact.search_vector
        | Email.search_vector
        | Phone.search_vector
        | Address.search_vector
    )

    query = search(
        select(Contact).join(Email).join(Phone).join(Address), q, vector=vector
    )
    contacts = session.scalars(query).all()
    results = [
        {
            "label": c.name,
            "group": "Contacts",
            "properties": {
                "email": [e.email for e in c.emails],
                "phone": [p.phone_number for p in c.phones],
                "address": [a.address_line_1 for a in c.addresses],
                # 'address': c.address,
                # 'location_id': c.location_id
            },
        }
        for c in contacts
    ]

    return results


def _get_thing_results(session: Session, q: str) -> list[dict]:
    vector = Thing.search_vector
    water_well_query = search(
        select(Thing).where(Thing.thing_type == "water well"), q, vector=vector
    )
    spring_well_query = search(
        select(Thing).where(Thing.thing_type == "spring"), q, vector=vector
    )

    wells = session.scalars(water_well_query).all()
    springs = session.scalars(spring_well_query).all()

    def _make_response(group: str, thing: Thing, properties: dict) -> dict:

        if properties is None:
            properties = {}

        properties["thing_type"] = thing.thing_type
        properties["id"] = thing.id
        return {
            "label": thing.name,
            "group": group,
            "properties": properties,
        }

    def make_well_response(thing: Thing) -> dict:
        return _make_response(
            "Wells",
            thing,
            {
                "well_type": thing.well_type,
                "well_depth": thing.well_depth,
                "hole_depth": thing.hole_depth,
            },
        )

    def make_spring_response(thing: Thing) -> dict:
        return _make_response(
            "Springs",
            thing,
            {
                "spring_type": thing.spring_type,
            },
        )

    return [
        func(item)
        for items, func in (
            (wells, make_well_response),
            (springs, make_spring_response),
        )
        for item in items
    ]


def _get_asset_results(session: Session, q: str) -> list[dict]:
    vector = Asset.search_vector
    query = search(
        select(Asset).join(AssetThingAssociation).join(Thing), q, vector=vector
    )

    assets = session.scalars(query).all()
    results = [
        {
            "label": a.name,
            "group": "Assets",
            "properties": {
                "things": [t.name for t in a.things],
                "storage_service": a.storage_service,
                "storage_path": a.storage_path,
                "mime_type": a.mime_type,
                "size": a.size,
            },
        }
        for a in assets
    ]

    return results


@router.get("")
def search_api(q: str, session: Session = Depends(get_db_session)):
    """
    Search endpoint for the collaborative network.
    """

    results = _get_contact_results(session, q)
    results.extend(_get_thing_results(session, q))
    results.extend(_get_asset_results(session, q))

    return {"items": results, "total": len(results)}


# ============= EOF =============================================
