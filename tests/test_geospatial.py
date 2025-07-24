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
import pytest

from db import Thing, Location, LocationThingAssociation
from db.engine import session_ctx
from tests import client
from geoalchemy2 import functions as geofunc

# @pytest.fixture(scope="module", autouse=True)
# def location_fixture():
#     client.post(
#         "/location",
#         json={
#             "point": "POINT(10.1 10.1)",
#         },
#     )


@pytest.fixture(autouse=True, scope="module")
def populate():
    with session_ctx() as session:
        # Create some sample data
        thing1 = Thing(name="Thing 1", thing_type="water well")
        thing2 = Thing(name="Thing 2", thing_type="water well")
        session.add(thing1)
        session.add(thing2)

        session.commit()

        loc1 = Location(
            name="Test Location 1",
            point=geofunc.ST_GeomFromText("POINT(10.1 10.1)", srid=4326),
        )
        loc2 = Location(
            name="Test Location 2",
            point=geofunc.ST_GeomFromText("POINT(20 20)", srid=4326),
        )
        session.add(loc1)
        session.add(loc2)

        session.add(LocationThingAssociation(location=loc1, thing=thing1))
        session.add(LocationThingAssociation(location=loc2, thing=thing2))
        session.commit()


def test_get_geojson():
    response = client.get("/geospatial", params={"format": "geojson"})
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) > 0  # Assuming there are features in the collection


def test_get_shapefile():
    response = client.get("/geospatial", params={"format": "shapefile"})
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"
    assert "Content-Disposition" in response.headers
    assert (
        'attachment; filename="things.zip"' == response.headers["Content-Disposition"]
    )


@pytest.mark.skip
def test_get_locations_expand():
    response = client.get(
        "/base/location",
        params={
            "expand": "well",
            "within": "POLYGON((10.0 10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, 10.0 10.0))",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert "well" in item


# @pytest.mark.skip("Needs fixture to ensure a location exists in this polygon")
def test_get_within_locations():
    response = client.get(
        "/location",
        params={
            "within": "POLYGON((10.0 10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, 10.0 10.0))",
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert "items" in data
    # Uncomment the following assertions if you have a specific location to test against
    assert len(data["items"]) == 1
    # assert "well" not in data["items"][0]
    # Assuming one location is within the polygon
    # assert len(data) == 1  # Assuming one location is within the distance
    # assert data[0]["name"] == "Test Location"  # Check if the correct location is returned


@pytest.mark.skip("Needs fixture to ensure a location exists nearby the point")
def test_get_nearby_locations():
    response = client.get(
        "/location",
        params={
            "nearby_point": "POINT(50.0 50.0)",  # Example coordinates
            "nearby_distance_km": 10,  # 10 km
        },
    )
    data = response.json()
    assert response.status_code == 200
    # assert len(data) == 1
    # assert data[0]["name"] == "Test Location 2"  # Check if the correct location is returned
    assert "items" in data
    assert len(data["items"]) == 1


# ============= EOF =============================================
