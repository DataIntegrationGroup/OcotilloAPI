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

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from db import get_db_session
from db.base import SampleLocation, Owner, Contact, Well, Group, GroupLocation
from services.query_helper import simple_get_by_name, simple_get_by_id
from schemas.form import (
    WellForm,
    WellFormResponse,
    GroundwaterLevelFormResponse,
    GroundwaterLevelForm,
)
from services.people_helper import add_contact

router = APIRouter(prefix="/form")


@router.post(
    "/well", response_model=WellFormResponse, status_code=status.HTTP_201_CREATED
)
async def well_form(form_data: WellForm, session=Depends(get_db_session)):
    """
    Endpoint to handle well form submissions.
    """
    # add location to the database
    data = form_data.model_dump()
    location_data = data.get("location", None)
    owner_data = data.get("owner", None)

    location = SampleLocation(**location_data)
    session.add(location)

    groups = data.get("groups", None)
    for group_data in groups:
        if group_data:
            group = Group(**group_data)
            session.add(group)

            group.locations.append(location)

    contact_data = owner_data.pop("contact", None)

    # add owner to the database
    owner = Owner(**owner_data)
    existing_owner = simple_get_by_name(session, Owner, owner.name)
    if existing_owner is None:
        session.add(owner)
        session.commit()
        session.refresh(owner)
    else:
        owner = existing_owner
    #
    # cs = [Contact(**contact) for contact in contact_data if contact is not None]
    # owner.contacts.extend(cs)
    for ci in contact_data:
        add_contact(session, ci, owner=owner)

    # add well to the database
    well_data = data.get("well", None)
    well = Well(**well_data)
    well.location = location
    session.add(well)

    session.commit()

    response_data = {"location": location, "owner": owner, "well": well}
    return response_data


@router.post(
    "/groundwaterlevel",
    response_model=GroundwaterLevelFormResponse,
    status_code=status.HTTP_201_CREATED,
)
async def groundwater_level_form(
    gwl_data: GroundwaterLevelForm, session=Depends(get_db_session)
):
    """
    Endpoint to handle groundwater level form submissions.
    """
    data = gwl_data.model_dump()


# ============= EOF =============================================
