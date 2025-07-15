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

from db import Contact, Email, Phone, Address, Thing, LocationThingAssociation, WellThing, Location, Asset, \
    AssetThingAssociation, search
from db.engine import get_db_session

router = APIRouter(
    prefix="/search",
    tags=["search"])

@router.get("/")
def search_api(q: str, session: Session=Depends(get_db_session)):
    """
    Search endpoint for the collaborative network.
    This endpoint can be used to search for wells, springs, and other entities in the collaborative network.
    """
    vector = (Contact.search_vector |
              Email.search_vector |
              Phone.search_vector |
              Address.search_vector)

    query = search(select(Contact)
                   .join(Email)
                   .join(Phone)
                   .join(Address), q, vector=vector)
    contacts = session.scalars(query).all()
    results = [{'label': c.name,
                        'group': 'Contacts',
                        'properties': {
                            'email': [e.email for e in c.emails],
                            'phone': [p.phone_number for p in c.phones],
                            'address': [a.address_line_1 for a in c.addresses]
                            # 'address': c.address,
                            # 'location_id': c.location_id
                        }} for c in contacts]

    # vector = Thing.search_vector | WellThing.search_vector | Asset.search_vector
    # query = search(select(WellThing).join(Thing)
    #                .join(Asset)
    #                .join(AssetThingAssociation)
    #                .join(LocationThingAssociation)
    #                .join(Location), q, vector=vector)
    # things = session.scalars(query).all()
    # thing_results = [{'label': t.name,
    #             'group': 'Wells',
    #             'properties': {
    #                 'well_depth': t.well_depth,
    #                 'hole_depth': t.hole_depth,
    #             }} for t in things]
    # results.extend(thing_results)

    return results


# ============= EOF =============================================
