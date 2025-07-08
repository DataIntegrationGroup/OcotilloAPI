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


class SpringResponse(ORMBaseModel):
    """
    Response schema for spring details.
    """

    id: int
    location_id: int
    description: str | None = None


class EquipmentResponse(ORMBaseModel):
    """
    Response schema for equipment details.
    """

    id: int
    location_id: int
    equipment_type: str | None = None
    model: str | None = None
    serial_no: str | None = None
    date_installed: str | None = None  # ISO format date string
    date_removed: str | None = None  # ISO format date string
    recording_interval: int | None = None
    equipment_notes: str | None = None


class PhoneResponse(ORMBaseModel):
    """
    Response schema for phone details.
    """

    id: int
    phone_number: str
    phone_type: str  # e.g., 'mobile', 'landline', etc.


class EmailResponse(ORMBaseModel):
    """
    Response schema for email details.
    """

    id: int
    email: str
    email_type: str  # e.g., 'personal', 'work', etc.


class AddressResponse(ORMBaseModel):
    """
    Response schema for address details.
    """

    id: int
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str


class ContactResponse(ORMBaseModel):
    """
    Response schema for contact details.
    """

    id: int
    name: str
    role: str
    emails: list[EmailResponse] = []
    phones: list[PhoneResponse] = []
    addresses: list[AddressResponse] = []


# ============= EOF =============================================
