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
    LocationThingAssociation,
    WellThing,
    Location,
    Asset,
    AssetThingAssociation,
    search,
)
from db.engine import get_db_session

router = APIRouter(prefix="/search", tags=["search"])


def _get_contact_results(session: Session, q: str)-> list[dict]:
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
    vector = Thing.search_vector | WellThing.search_vector
    query = search(select(WellThing).join(Thing), q, vector=vector)

    wells = session.scalars(query).all()
    results = [
        {
            "label": w.thing.name,
            "group": "Things",
            "properties": {
                "type": w.well_type,
            },
        }
        for w in wells
    ]

    return results


def _get_asset_results(session: Session, q: str) -> list[dict]:
    vector = Asset.search_vector
    query = search(select(Asset)
                   .join(AssetThingAssociation)
                   .join(Thing), q, vector=vector)

    assets = session.scalars(query).all()
    results = [
        {
            "label": a.filename,
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


@router.get("/")
def search_api(q: str, session: Session = Depends(get_db_session)):
    """
    Search endpoint for the collaborative network.
    """

    results = _get_contact_results(session, q)
    results.extend(_get_thing_results(session, q))
    results.extend(_get_asset_results(session, q))

    return results


# ============= EOF =============================================
