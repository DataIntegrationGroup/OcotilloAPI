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
import json

import pandas as pd
from pandas import DataFrame
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.enums import Organization
from db import (
    Contact,
    ThingContactAssociation,
    Email,
    Phone,
    Address,
    IncompleteNMAPhone,
    Base,
)
from transfers.logger import logger
from transfers.transferer import ThingBasedTransferer
from transfers.util import (
    get_transfers_data_path,
)
from transfers.util import read_csv, filter_to_valid_point_ids, replace_nans


class ContactTransfer(ThingBasedTransferer):
    source_table = "OwnersData"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        """
        Developer's note

        - company to organization mapping is stored in transfers/data/owners_organization_mapper.json
        - the key is the value in NM_Aquifer and the value is the standardized organization name used in the lexicon
        """
        co_to_org_mapper_path = get_transfers_data_path(
            "owners_organization_mapper.json"
        )
        with open(co_to_org_mapper_path, "r") as f:
            self._co_to_org_mapper = json.load(f)

        self._added = []

    def _get_dfs(self):
        input_df = read_csv(self.source_table)
        odf = input_df.drop(["OBJECTID", "GlobalID"], axis=1)
        ldf = read_csv("OwnerLink")
        ldf = ldf.drop(["OBJECTID", "GlobalID"], axis=1)
        locdf = read_csv("Location")
        ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

        odf = odf.join(ldf.set_index("OwnerKey"), on="OwnerKey")

        odf = replace_nans(odf)

        odf = filter_to_valid_point_ids(odf)
        return input_df, odf

    def _get_prepped_group(self, group) -> DataFrame:
        return group.sort_values(by=["PointID"])

    def _group_step(self, session: Session, row: pd.Series, db_item: Base):
        for adder, tag in (_add_first_contact, "first"), (
            _add_second_contact,
            "second",
        ):
            try:
                if adder(
                    session,
                    row,
                    db_item,
                    self._co_to_org_mapper,
                    self._added,
                ):
                    session.commit()
                    logger.info(f"added {tag} contact for PointID {row.PointID}")
            except ValidationError as e:
                logger.critical(
                    f"Skipping {tag} contact for PointID {row.PointID} due to validation error: {e.errors()}"
                )
                self._capture_error(row.PointID, str(e), "ValidationError")
            except Exception as e:
                logger.critical(
                    f"Skipping {tag} contact for PointID {row.PointID} due to error: {e}"
                )
                session.rollback()
                self._capture_error(row.PointID, str(e), "UnknownError")


def _add_first_contact(session, row, thing, co_to_org_mapper, added):
    # TODO: extract role from OwnerComment
    # role = extract_owner_role(row.OwnerComment)
    role = "Owner"
    release_status = "private"

    name = _make_name(row.FirstName, row.LastName)

    # check if organization is in lexicon
    organization = _get_organization(row, co_to_org_mapper)
    if (name, organization) in added:
        return None
    added.append((name, organization))

    contact_data = {
        "thing_id": thing.id,
        "release_status": release_status,
        "name": name,
        "role": role,
        "contact_type": "Primary",
        "organization": organization,
        "nma_pk_owners": row.OwnerKey,
        "addresses": [],
        "emails": [],
        "phones": [],
    }

    contact = _make_contact_and_assoc(session, contact_data, thing)

    if row.Email:
        email = _make_email(
            "first",
            row.OwnerKey,
            email=row.Email.strip(),
            email_type="Primary",
            release_status=release_status,
        )
        if email:
            contact.emails.append(email)

    if row.Phone:
        phone, complete = _make_phone(
            "first",
            row.OwnerKey,
            phone_number=row.Phone,
            phone_type="Primary",
            release_status=release_status,
        )
        if phone:
            if complete:
                contact.phones.append(phone)
            else:
                contact.incomplete_nma_phones.append(phone)

    if row.CellPhone:
        phone, complete = _make_phone(
            "first",
            row.OwnerKey,
            phone_number=row.CellPhone,
            phone_type="Mobile",
            release_status=release_status,
        )
        if phone:
            if complete:
                contact.phones.append(phone)
            else:
                contact.incomplete_nma_phones.append(phone)

    if row.MailingAddress:
        address = _make_address(
            "first",
            row.OwnerKey,
            "mailing",
            address_line_1=row.MailingAddress,
            city=row.MailCity,
            state=row.MailState,
            postal_code=row.MailZipCode,
            address_type="Mailing",
            release_status=release_status,
        )
        if address:
            contact.addresses.append(address)

    if row.PhysicalAddress:
        address = _make_address(
            "first",
            row.OwnerKey,
            "physical",
            address_line_1=row.PhysicalAddress,
            city=row.PhysicalCity,
            state=row.PhysicalState,
            postal_code=row.PhysicalZipCode,
            address_type="Physical",
            release_status=release_status,
        )
        if address:
            contact.addresses.append(address)
    return True


def _get_organization(row, co_to_org_mapper):
    organization = co_to_org_mapper.get(row.Company, row.Company)

    # use Organization enum to catch validation errors
    Organization(organization)

    return organization


def _add_second_contact(session, row, thing, co_to_org_mapper, added):
    if all(
        [
            getattr(row, f"Second{f}") is None
            for f in ["FirstName", "LastName", "CtctEmail", "CtctPhone"]
        ]
    ):
        logger.warning(f"No second contact info for PointID {row.PointID}, skipping.")
        return

    release_status = "private"
    name = _make_name(row.SecondFirstName, row.SecondLastName)

    organization = _get_organization(row, co_to_org_mapper)
    if (name, organization) in added:
        return

    added.append((name, organization))

    contact_data = {
        "thing_id": thing.id,
        "release_status": release_status,
        "name": name,
        "role": "Owner",
        "contact_type": "Secondary",
        "organization": organization,
        "nma_pk_owners": row.OwnerKey,
        "addresses": [],
        "emails": [],
        "phones": [],
    }

    contact = _make_contact_and_assoc(session, contact_data, thing)

    if row.SecondCtctEmail:
        email = _make_email(
            "second",
            row.OwnerKey,
            email=row.SecondCtctEmail,
            email_type="Primary",
            release_status=release_status,
        )
        if email:
            contact.emails.append(email)

    if row.SecondCtctPhone:
        phone, complete = _make_phone(
            "second",
            row.OwnerKey,
            phone_number=row.SecondCtctPhone,
            phone_type="Primary",
            release_status=release_status,
        )
        if phone:
            if complete:
                contact.phones.append(phone)
            else:
                contact.incomplete_nma_phones.append(phone)
    return True


# helpers
def _make_name(first, last):
    if first is None and last is None:
        return None
    elif first is not None and last is None:
        return first
    elif first is None and last is not None:
        return last
    else:
        return f"{first} {last}"


def _make_email(first_second, ownerkey, **kw):
    from schemas.contact import CreateEmail

    try:
        if "email" in kw:
            kw["email"] = kw["email"].strip()

        email = CreateEmail(**kw)
        return Email(**email.model_dump())
    except ValidationError as e:
        logger.critical(
            f"{first_second} '{ownerkey}' Skipping email. Validation error: {e.errors()}"
        )


def _make_phone(first_second, ownerkey, **kw):
    from schemas.contact import CreatePhone

    try:
        if "phone_number" in kw:
            kw["phone_number"] = kw["phone_number"].strip()

        phone = CreatePhone(**kw)
        return Phone(**phone.model_dump()), True
    except ValidationError as e:
        try:
            if "phone_number" in kw:
                incomplete_phone = IncompleteNMAPhone(phone_number=kw["phone_number"])
                logger.info(f"Salvaged incomplete phone number for OwnerKey {ownerkey}")
                return incomplete_phone, False
        except ValidationError:

            logger.critical(
                f"{first_second} '{ownerkey}' Skipping phone . Validation error: {e.errors()}"
            )


def _make_address(first_second, ownerkey, kind, **kw):
    from schemas.contact import CreateAddress

    try:
        address = CreateAddress(**kw)
        return Address(**address.model_dump())
    except ValidationError as e:
        logger.warning(
            f"{first_second} '{ownerkey}' Skipping {kind} address. Validation error: {e.errors()}"
        )


def _make_contact_and_assoc(session, data, thing):
    from schemas.contact import CreateContact

    contact = CreateContact(**data)
    contact_data = contact.model_dump()
    contact_data.pop("thing_id")
    contact = Contact(**contact_data)

    assoc = ThingContactAssociation()
    assoc.thing = thing
    assoc.contact = contact
    session.add(assoc)
    session.add(contact)
    return contact


# ============= EOF =============================================
