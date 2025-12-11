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
from fastapi import APIRouter
from fastapi_pagination import paginate
from fastapi_pagination.utils import disable_installed_extensions_check
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session, selectinload

from api.pagination import CustomPage
from core.dependencies import session_dependency, viewer_dependency
from db import (
    Contact,
    Email,
    Phone,
    Address,
    ThingContactAssociation,
    Thing,
    WellCasingMaterial,
    WellPurpose,
    Asset,
    AssetThingAssociation,
    search,
)

disable_installed_extensions_check()
router = APIRouter(prefix="/search", tags=["search"])


def _get_contact_results(session: Session, q: str, limit: int) -> list[dict]:
    vector = (
        func.coalesce(Contact.search_vector, text("''::tsvector"))
        .op("||")(func.coalesce(Email.search_vector, text("''::tsvector")))
        .op("||")(func.coalesce(Phone.search_vector, text("''::tsvector")))
        .op("||")(func.coalesce(Address.search_vector, text("''::tsvector")))
    )

    query = search(
        select(Contact)
        .outerjoin(Email)
        .outerjoin(Phone)
        .outerjoin(Address)
        .options(
            selectinload(Contact.emails),
            selectinload(Contact.phones),
            selectinload(Contact.addresses),
            selectinload(Contact.thing_associations).selectinload(
                ThingContactAssociation.thing
            ),
        ),
        q,
        vector=vector,
        limit=limit,
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
                "things": [
                    {"label": t.name, "id": t.id, "thing_type": t.thing_type}
                    for t in c.things
                ],
                "id": c.id,
            },
        }
        for c in contacts
    ]
    return results


def _get_thing_results(session: Session, q: str, limit: int) -> list[dict]:
    well_vector = (
        func.coalesce(Thing.search_vector, text("''::tsvector"))
        .op("||")(func.coalesce(WellCasingMaterial.search_vector, text("''::tsvector")))
        .op("||")(func.coalesce(WellPurpose.search_vector, text("''::tsvector")))
    )

    water_well_query = search(
        select(Thing)
        .outerjoin(WellCasingMaterial)
        .outerjoin(WellPurpose)
        .where(Thing.thing_type == "water well")
        .options(
            selectinload(Thing.well_casing_materials),
            selectinload(Thing.well_purposes),
        ),
        q,
        vector=well_vector,
        limit=limit,
    )

    spring_vector = Thing.search_vector
    spring_well_query = search(
        select(Thing).where(Thing.thing_type == "spring"),
        q,
        vector=spring_vector,
        limit=limit,
    )

    # unique needs to be called because of eager loads
    wells = session.scalars(water_well_query).unique().all()
    springs = session.scalars(spring_well_query).unique().all()

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
                "well_purposes": [wp.purpose for wp in thing.well_purposes],
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


def _get_asset_results(session: Session, q: str, limit: int) -> list[dict]:
    vector = Asset.search_vector
    query = search(
        select(Asset)
        .join(AssetThingAssociation)
        .join(Thing)
        .options(selectinload(Asset.things)),
        q,
        vector=vector,
        limit=limit,
    )

    assets = session.scalars(query).all()
    results = [
        {
            "label": a.name,
            "group": "Assets",
            "properties": {
                "id": a.id,
                "things": [
                    {"label": t.name, "id": t.id, "thing_type": t.thing_type}
                    for t in a.things
                ],
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
async def search_api(
    user: viewer_dependency,
    session: session_dependency,
    q: str,
    size: int = 100,
    limit: int = 25,
) -> CustomPage[dict]:
    """
    Search endpoint for the collaborative network.
    """

    results = _get_contact_results(session, q, limit)
    results.extend(_get_thing_results(session, q, limit))
    results.extend(_get_asset_results(session, q, limit))

    return paginate(results)
    # return {"items": results, "total": len(results)}


# ============= EOF =============================================
