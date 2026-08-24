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
"""A thing with no current location must not take down the page it is on.

A thing is associated with a location over an effective period, and that period
can be closed or never opened. When `current_location` was a required field the
GeoJSON validator was handed None, reached for `__table__` on it, and the whole
listing came back 500 -- one unlocated well made every well unreadable.
"""

from db.engine import session_ctx
from db.thing import Thing
from main import app
from schemas.location import LocationGeoJSONResponse
from starlette.testclient import TestClient

client = TestClient(app)


def test_geojson_validator_passes_none_through():
    assert LocationGeoJSONResponse.populate_fields(None) is None


def test_listing_wells_survives_one_with_no_location(water_well_thing):
    unlocated = Thing(
        name="TEST-NOLOC-1",
        thing_type="water well",
        release_status="public",
    )
    with session_ctx() as session:
        session.add(unlocated)
        session.commit()
        unlocated_id = unlocated.id

    try:
        response = client.get("/thing/water-well", params={"size": 100})
        assert response.status_code == 200, response.text

        items = {item["id"]: item for item in response.json()["items"]}
        assert unlocated_id in items
        assert items[unlocated_id]["current_location"] is None
    finally:
        with session_ctx() as session:
            session.delete(session.get(Thing, unlocated_id))
            session.commit()


# ============= EOF =============================================
