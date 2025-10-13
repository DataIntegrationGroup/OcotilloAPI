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

import phonenumbers
from email_validator import validate_email, EmailNotValidError
from phonenumbers import NumberParseException
from pydantic import field_validator, BaseModel, model_validator

from core.enums import Role, ContactType, PhoneType, EmailType, AddressType
from schemas import BaseResponseModel, BaseCreateModel, BaseUpdateModel
from schemas.thing import ThingResponse


# -------- VALIDATORS ----------


class ValidateContact(BaseModel):
    name: str | None = None
    organization: str | None = None

    @model_validator(mode="before")
    def check_empty(data: dict) -> dict:
        if (
            data.get("name", "unset") is None
            and data.get("organization", "unset") is None
        ):
            raise ValueError("Either name or organization must be provided.")
        return data


class ValidateEmail(BaseModel):

    email: str | None = None

    @field_validator("email", check_fields=False)
    @classmethod
    def validate_email(cls, email: str | None) -> str | None:
        if email is not None:
            try:
                emailinfo = validate_email(email, check_deliverability=False)
                return emailinfo.normalized
            except EmailNotValidError as e:
                raise ValueError(f"Invalid email format. {email}")


class ValidatePhone(BaseModel):

    phone_number: str | None = None

    @field_validator("phone_number", check_fields=False)
    @classmethod
    def validate_phone(cls, phone_number_str: str | None) -> str | None:
        if phone_number_str is not None:
            region = "US"
            try:
                phone_number_str = phone_number_str.strip()
                # this is a major hack to deal with the phone numbers entered into
                # NM_Aquifer without an area code
                for p in (phone_number_str, f"505{phone_number_str}"):
                    parsed_number = phonenumbers.parse(p, region)
                    if phonenumbers.is_valid_number(parsed_number):
                        formatted_number = phonenumbers.format_number(
                            parsed_number, phonenumbers.PhoneNumberFormat.E164
                        )
                        return formatted_number
                else:
                    raise ValueError(f"Invalid phone number. {phone_number_str}")
            except NumberParseException as e:
                raise ValueError(f"Invalid phone number. {phone_number_str}")


# -------- CREATE ----------
class CreateEmail(BaseCreateModel, ValidateEmail):
    """
    Schema for creating an email.
    """

    contact_id: int | None = None  # set to None for when made via POST /contact
    email: str
    email_type: EmailType = "Primary"  # Default to 'Primary'


class CreatePhone(BaseCreateModel, ValidatePhone):
    """
    Schema for creating a phone number.
    """

    contact_id: int | None = None  # set to None for when made via POST /contact
    phone_number: str
    phone_type: PhoneType = "Primary"  # Default to 'Primary'


class CreateAddress(BaseCreateModel):
    """
    Schema for creating an address.
    """

    contact_id: int | None = None  # set to None for when made via POST /contact
    # todo: use a postal API to validate address and suggest corrections
    address_line_1: str  # Required (e.g., "123 Main St")
    address_line_2: str | None = None  # Optional (e.g., "Apt 4B", "Suite 200")
    city: str
    # todo: add validation.  Should state be required? what about foreign addresses?
    state: str = "NM"  # Default to New Mexico
    postal_code: str
    country: str = "United States"  # Default to United States
    address_type: AddressType = "Primary"


# class CreateThingAssociation(BaseModel):
#     """
#     Schema for creating a ContactThingAssociation
#     """

#     contact_id: int
#     thing_id: int


class CreateContact(BaseCreateModel, ValidateContact):
    """
    Schema for creating a contact.
    """

    thing_id: int
    name: str | None = None
    organization: str | None = None
    role: Role
    contact_type: ContactType = "Primary"
    # description: str | None = None
    # email: str | None = None
    # phone: str | None = None

    emails: list[CreateEmail] | None = None
    phones: list[CreatePhone] | None = None
    addresses: list[CreateAddress] | None = None


# -------- RESPONSE ----------


class BaseItemResponse(BaseResponseModel):
    contact_id: int


class PhoneResponse(BaseItemResponse):
    """
    Response schema for phone details.
    """

    phone_number: str
    phone_type: PhoneType  # e.g., 'mobile', 'landline', etc.


class EmailResponse(BaseItemResponse):
    """
    Response schema for email details.
    """

    email: str
    email_type: EmailType  # e.g., 'personal', 'work', etc.


class AddressResponse(BaseItemResponse):
    """
    Response schema for address details.
    """

    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str
    address_type: AddressType


class ContactResponse(BaseResponseModel):
    """
    Response schema for contact details.
    """

    name: str | None
    organization: str | None
    role: Role
    contact_type: ContactType
    emails: List[EmailResponse] = []
    phones: List[PhoneResponse] = []
    addresses: List[AddressResponse] = []
    things: List[ThingResponse] = []  # List of related things


# class ThingContactAssociationResponse(BaseUpdateModel):
#     """
#     Response schema for thing-contact association details.
#     """

#     id: int
#     thing_id: int
#     contact_id: int


# -------- UPDATE ----------
class UpdateContact(BaseUpdateModel, ValidateContact):
    """
    Schema for updating contact information.
    """

    name: str | None = None
    role: Role | None = None
    contact_type: ContactType | None = None
    thing_id: int | None = None
    organization: str | None = None
    # email: str | None = None
    # phone: str | None = None
    # address: str | None = None


class UpdateEmail(BaseUpdateModel, ValidateEmail):
    """
    Schema for updating email information.
    """

    contact_id: int | None = None
    email: str | None = None
    email_type: EmailType | None = None


class UpdatePhone(BaseUpdateModel, ValidatePhone):
    """
    Schema for updating phone information.
    """

    contact_id: int | None = None
    phone_number: str | None = None
    phone_type: PhoneType | None = None


class UpdateAddress(BaseUpdateModel):
    """
    Schema for updating address information.
    """

    contact_id: int | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    address_type: AddressType | None = None


# class UpdateThingContactAssociation(BaseUpdateModel):
#     """
#     Schema for updating thing-contact association information.
#     """

#     thing_id: int | None = None
#     contact_id: int | None = None


# ============= EOF =============================================
