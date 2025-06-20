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
from schemas import ORMBaseModel
from pydantic import field_validator
import re
import phonenumbers
from phonenumbers import NumberParseException
from email_validator import validate_email, EmailNotValidError


class CreateLocation(ORMBaseModel):
    """
    Schema for creating a sample location.
    """

    name: str
    description: str | None = None
    point: str = "POINT(0 0)"  # Default to a point at the origin
    visible: bool = False


class CreateGroup(ORMBaseModel):
    """
    Schema for creating a group.
    """

    name: str


class CreateGroupLocation(ORMBaseModel):
    """
    Schema for creating a group location.
    """

    group_id: int
    location_id: int


class CreateOwner(ORMBaseModel):
    """
    Schema for creating an owner.
    """

    name: str
    description: str | None = None


class CreateContact(ORMBaseModel):
    """
    Schema for creating a contact.
    """

    owner_id: int

    name: str | None = None
    description: str | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, phone_number_str):
        region = "US"
        try:
            parsed_number = phonenumbers.parse(phone_number_str, region)
            if phonenumbers.is_valid_number(parsed_number):
                # You can also format the number if needed
                formatted_number = phonenumbers.format_number(
                    parsed_number, phonenumbers.PhoneNumberFormat.E164
                )
                return formatted_number
            else:
                raise ValueError(f"Invalid phone number. {phone_number_str}")
        except NumberParseException as e:
            raise ValueError(f"Invalid phone number. {phone_number_str}")

    @field_validator("email")
    @classmethod
    def validate_email(cls, email):
        # try:
        # Check that the email address is valid. Turn on check_deliverability
        # for first-time validations like on account creation pages (but not
        # login pages).
        emailinfo = validate_email(email, check_deliverability=False)

        # After this point, use only the normalized form of the email address,
        # especially before going to a database query.
        email = emailinfo.normalized
        return email
        # except EmailNotValidError as e:
        # if v is not None:
        #     # Basic email validation
        #     if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", v):
        #         raise ValueError(f"Invalid email format. {v}")
        # return v


# ============= EOF =============================================
