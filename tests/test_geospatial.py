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
from tests import client


def test_get_geojson():
    response = client.get("/base/location/feature_collection")
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) > 0  # Assuming there are features in the collection
    assert (
        data["features"][0]["geometry"] == '{"type":"Point","coordinates":[10.1,10.1]}'
    )  # Adjust based on your


def test_get_shapefile():
    response = client.get("/base/location/shapefile")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"
    assert "Content-Disposition" in response.headers
    assert (
        'attachment; filename="locations.zip"'
        == response.headers["Content-Disposition"]
    )


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


def test_get_within_locations():
    response = client.get(
        "/base/location",
        params={
            "within": "POLYGON((10.0 10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, 10.0 10.0))",
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert "items" in data
    # Uncomment the following assertions if you have a specific location to test against
    assert len(data["items"]) == 1
    assert "well" not in data["items"][0]
    # Assuming one location is within the polygon
    # assert len(data) == 1  # Assuming one location is within the distance
    # assert data[0]["name"] == "Test Location"  # Check if the correct location is returned


def test_get_nearby_locations():
    response = client.get(
        "/base/location",
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
