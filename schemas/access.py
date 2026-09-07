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
"""
schemas/access.py

Request and response shapes for the ADR5 access-control routes: destinations,
permission grants, publication consent.

These do not inherit ``BaseCreateModel`` / ``BaseResponseModel``. Those carry
``release_status`` and ``data_maturity``, which describe released *data*. A
grant is not data anybody releases -- it is the rule about who sees it.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from core.enums import (
    AccessDataType,
    Capability,
    DestinationKind,
    GrantScopeType,
    PrincipalType,
    UISurface,
)
from schemas import UTCAwareDatetime


# ------ DESTINATION ----------
class CreateDestination(BaseModel):
    slug: str = Field(max_length=50, examples=["ngwmn"])
    name: str = Field(
        max_length=255, examples=["National Ground-Water Monitoring Network"]
    )
    destination_kind: DestinationKind
    description: str | None = None


class DestinationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    destination_kind: DestinationKind
    description: str | None
    active: bool


# ------ PERMISSION GRANT ----------
class CreatePermissionGrant(BaseModel):
    """One grant. Every axis is named; there is no wildcard data type."""

    principal_type: PrincipalType
    principal_id: str = Field(max_length=255)
    capability: Capability
    scope_type: GrantScopeType
    # Null for a global grant, required for a group- or thing-scoped one. The
    # rule is enforced in domain/access.py rather than here, so it holds for
    # every writer, not only this route.
    scope_id: int | None = None
    # Exactly one of these. A grant reaches data, or it opens a screen; the
    # XOR and the global-only rule for surfaces live in domain/access.py, for
    # the same reason the scope rule does.
    data_type: AccessDataType | None = None
    ui_surface: UISurface | None = None
    starts_at: date
    ends_at: date | None = None
    reason: str | None = None


class PermissionGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    principal_type: PrincipalType
    principal_id: str
    capability: Capability
    scope_type: GrantScopeType
    scope_id: int | None
    data_type: AccessDataType | None
    ui_surface: UISurface | None
    starts_at: date
    ends_at: date | None
    granted_by: str
    reason: str | None
    revoked_at: UTCAwareDatetime | None
    revoked_by: str | None


class AccessDecision(BaseModel):
    """The visibility layer's answer, and what was asked."""

    allowed: bool
    capability: Capability
    data_type: AccessDataType | None = None
    ui_surface: UISurface | None = None
    thing_id: int | None
    principals: list[str]


# ------ PUBLICATION CONSENT ----------
class CreatePublicationConsent(BaseModel):
    thing_id: int
    destination_slug: str = Field(max_length=50)
    data_type: AccessDataType
    starts_at: date
    ends_at: date | None = None
    # Null when the Bureau owns the well: the decision was institutional, and
    # inventing a consenting contact would be a lie.
    contact_id: int | None = None
    notes: str | None = None


class PublicationConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thing_id: int
    destination_id: int
    data_type: AccessDataType
    contact_id: int | None
    recorded_by: str
    notes: str | None
    starts_at: date
    ends_at: date | None
    revoked_at: UTCAwareDatetime | None
    revoked_by: str | None


class PublishedThing(BaseModel):
    """One thing as a destination sees it.

    ``thing_id`` and ``data_types`` are the envelope for staff reading this
    route; ``properties`` and ``location`` are what the destination itself
    receives, already projected through the per-audience allowlist. A field
    nobody approved for this audience is absent rather than null, and a
    coordinate may arrive rounded.
    """

    thing_id: int
    data_types: list[AccessDataType]
    properties: dict
    location: dict


# ============= EOF =============================================
