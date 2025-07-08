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
from typing import List

from fastapi import APIRouter, Depends, status

from db import adder
from db.contact import Contact
from db.group import Group, GroupThingAssociation
from services.people_helper import add_contact
from services.query_helper import (
    simple_get_by_id,
    simple_all_getter,
)
from sqlalchemy.orm import Session

from db.engine import get_db_session
from db.thing import SpringThing

from schemas.base_create import (
    CreateSpring,
)
from schemas.create.location import (
    CreateGroup,
    CreateGroupThing,
)
from schemas.create.contact import CreateContact
from schemas.base_responses import (
    ContactResponse,
)
from schemas.response.well import (
    GroupResponse,
)

router = APIRouter(
    prefix="/base",
)


# ============= Create ============================================


@router.post(
    "/group", summary="Create a new group", status_code=status.HTTP_201_CREATED
)
def create_group(group_data: CreateGroup, session: Session = Depends(get_db_session)):
    """
    Create a new group in the database.
    """
    return adder(session, Group, group_data)


@router.post(
    "/group_thing",
    summary="Create a new group thing",
    status_code=status.HTTP_201_CREATED,
)
def create_group_thing(
    group_location_data: CreateGroupThing, session: Session = Depends(get_db_session)
):
    """
    Create a new group location association in the database.
    """
    return adder(session, GroupThingAssociation, group_location_data)


@router.post(
    "/contact",
    summary="Create a new contact",
    status_code=status.HTTP_201_CREATED,
    response_model=ContactResponse,
)
def create_contact(
    contact_data: CreateContact, session: Session = Depends(get_db_session)
):

    return add_contact(session, contact_data)

    # return adder(session, Contact, contact_data)



# @router.post(
#     "/equipment", summary="Create a new equipment", status_code=status.HTTP_201_CREATED
# )
# def create_equipment(
#     equipment_data: CreateEquipment, session: Session = Depends(get_db_session)
# ):
#     """
#     Create a new equipment in the database.
#     """
#     # Placeholder for actual equipment creation logic
#     # return {"message": "This endpoint will create a new equipment."}
#     return adder(session, Equipment, equipment_data)
#

# ==== Get ============================================


@router.get("/group", response_model=List[GroupResponse], summary="Get groups")
async def get_groups(session: Session = Depends(get_db_session)):
    """
    Retrieve all groups from the database.
    """
    # sql = select(Group)
    # result = db.execute(sql)
    # return result.all()
    return simple_all_getter(session, Group)


@router.get("/contact", response_model=List[ContactResponse], summary="Get contacts")
async def get_contacts(session: Session = Depends(get_db_session)):
    """
    Retrieve all contacts from the database.
    :param session:
    :return:
    """
    return simple_all_getter(session, Contact)





# @router.get(
#     "/group_location",
#     response_model=List[GroupLocationResponse],
#     summary="Get group locations",
# )
# async def get_group_locations(session: Session = Depends(get_db_session)):
#     """
#     Retrieve all group locations from the database.
#     """
#     return simple_all_getter(session, GroupLocationAssociation)
#

# @router.get(
#     "/spring",
#     response_model=List[SpringResponse],
# )
# async def get_springs(session: Session = Depends(get_db_session)):
#     """
#     Retrieve all springs from the database.
#     """
#     return simple_all_getter(session, SpringThing)


# @router.get(
#     "/equipment", response_model=List[EquipmentResponse], summary="Get equipment"
# )
# async def get_equipment(session: Session = Depends(get_db_session)):
#     """
#     Retrieve all equipment from the database.
#     """
#     return simple_all_getter(session, Equipment)


# ============= Get by ID ============================================
# @router.get(
#     "/equipment/{equipment_id}",
#     response_model=EquipmentResponse,
#     summary="Get equipment by ID",
# )
# async def get_equipment_by_id(
#     equipment_id: int, session: Session = Depends(get_db_session)
# ):
#     """
#     Retrieve an equipment by ID from the database.
#     """
#     equipment = simple_get_by_id(session, Equipment, equipment_id)
#     if not equipment:
#         return {"message": "Equipment not found"}
#     return equipment


@router.get(
    "/group/{group_id}", response_model=GroupResponse, summary="Get group by ID"
)
async def get_group_by_id(group_id: int, session: Session = Depends(get_db_session)):
    """
    Retrieve a group by ID from the database.
    """
    group = simple_get_by_id(session, Group, group_id)
    if not group:
        return {"message": "Group not found"}
    return group


# @router.get(
#     "/group_location/{group_location_id}",
#     response_model=GroupLocationResponse,
#     summary="Get group location by ID",
# )
# async def get_group_location_by_id(
#     group_location_id: int, session: Session = Depends(get_db_session)
# ):
#     """
#     Retrieve a group location by ID from the database.
#     """
#     group_location = simple_get_by_id(
#         session, GroupLocationAssociation, group_location_id
#     )
#     if not group_location:
#         return {"message": "Group location not found"}
#     return group_location


@router.get(
    "/contact/{contact_id}", response_model=ContactResponse, summary="Get contact by ID"
)
async def get_contact_by_id(
    contact_id: int, session: Session = Depends(get_db_session)
):
    """
    Retrieve a contact by ID from the database.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    if not contact:
        return {"message": "Contact not found"}
    return contact


# ============= EOF =============================================
