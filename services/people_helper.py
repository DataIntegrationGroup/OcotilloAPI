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
from db.base import Contact, Owner, OwnerContactAssociation
from schemas.create.location import CreateContact
from sqlalchemy.orm import Session


def add_contact(
    session: Session,
    contact_data: CreateContact | dict,
    owner: Owner = None,
    owner_id: int = None,
):
    """
    Add a new contact to the database.
    """

    if isinstance(contact_data, CreateContact):
        contact_data = contact_data.model_dump()

    if owner is None:
        if owner_id is None:
            owner_id = contact_data.pop("owner_id")

        owner = session.get(Owner, owner_id)

    if owner is None:
        raise ValueError(f"Owner with ID {owner_id} does not exist.")

    contact = Contact(**contact_data)

    session.add(contact)
    session.commit()
    session.refresh(contact)

    owner_contact_association = OwnerContactAssociation()
    owner_contact_association.owner_id = owner.id
    owner_contact_association.contact_id = contact.id
    session.add(owner_contact_association)
    session.commit()

    return contact


# ============= EOF =============================================
