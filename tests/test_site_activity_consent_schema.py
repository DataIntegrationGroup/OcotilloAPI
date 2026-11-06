# ===============================================================================
# Copyright 2026 ross
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
The site_activity_consent columns are named activity and allowed, but the well
response still publishes permission_type and permission_allowed, because
OcotilloUI reads those keys. These tests fail if the serialization aliases in
schemas/site_activity_consent.py are lost.
"""

from fastapi.openapi.utils import get_openapi

from main import app
from schemas.site_activity_consent import SiteActivityConsentResponse

WIRE_KEYS = {"permission_type", "permission_allowed", "start_date", "end_date"}


def test_response_serializes_with_permission_keys():
    response = SiteActivityConsentResponse(
        activity="Water Level Sample",
        allowed=True,
        start_date=None,
        end_date=None,
    )

    dumped = response.model_dump(mode="json", by_alias=True)

    assert set(dumped) == WIRE_KEYS
    assert dumped["permission_type"] == "Water Level Sample"
    assert dumped["permission_allowed"] is True


def test_openapi_publishes_permission_keys():
    # The full schema, as /openapi-auth.json builds it: OcotilloUI generates
    # its types from that one. app.openapi() is the public subset, which has
    # no well routes.
    full = get_openapi(title="Ocotillo API (Full)", version="0", routes=app.routes)
    schemas = full["components"]["schemas"]

    # Follow every response's `permissions` field to the schema it points
    # at, rather than assume the component name FastAPI gives it.
    refs = {
        schema["properties"]["permissions"]["items"]["$ref"]
        for schema in schemas.values()
        if "permissions" in schema.get("properties", {})
    }

    assert refs
    for ref in refs:
        component = schemas[ref.rsplit("/", 1)[-1]]
        assert set(component["properties"]) == WIRE_KEYS, ref
