# ===============================================================================
# Copyright 2026
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
Request and response shapes for /api_key.

These do not inherit BaseCreateModel/BaseResponseModel: those carry
`release_status`, and a credential is not draft-or-published content.

Field names are snake_case like every other route here. OcotilloUI#360's
`ApiKey` type is camelCase because it was written against local component state
with no server behind it; mapping it there is a smaller change than making one
router disagree with the rest of the API.
"""

from pydantic import BaseModel, ConfigDict, Field

from domain.api_key import MAX_LIFETIME, MAX_NAME_LENGTH
from schemas import UTCAwareDatetime

MAX_LIFETIME_DAYS = MAX_LIFETIME.days


# -------- CREATE ----------
class CreateApiKey(BaseModel):
    name: str = Field(
        ...,
        max_length=MAX_NAME_LENGTH,
        description="A name you will recognize later, so you know what to revoke.",
    )
    lifetime_days: int | None = Field(
        default=None,
        gt=0,
        description=(
            f"How long the key should live, in days. Defaults to "
            f"{MAX_LIFETIME_DAYS}, which is also the maximum -- a longer "
            f"request is clamped rather than rejected."
        ),
    )


# -------- UPDATE ----------
class UpdateApiKey(BaseModel):
    """The name is the only mutable field. A credential's scope, owner, and
    expiry are fixed at creation; changing any of them is issuing a new key."""

    name: str = Field(..., max_length=MAX_NAME_LENGTH)


# -------- RESPONSE --------
class ApiKeyResponse(BaseModel):
    id: int
    name: str
    token_preview: str
    scope: str
    created_at: UTCAwareDatetime
    expires_at: UTCAwareDatetime
    last_used_at: UTCAwareDatetime | None = None
    revoked_at: UTCAwareDatetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NewApiKeyResponse(ApiKeyResponse):
    """The create response, and the only one that ever carries `token`.

    Nothing re-reads it: the digest is all that is stored, so a client that
    loses this response has to issue a new key.
    """

    token: str


# ============= EOF =============================================
