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

from tests import client


def test_add_location():
    response = client.post(
        "/location",
        json={
            # "name": "Test Location 1",
            "point": "POINT(10.1 10.1)",
            # "visible": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 2

    response = client.post(
        "/location",
        json={
            # "name": "Test Location 2",
            "point": "POINT(50.0 50.0)",
            # "visible": False,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 2


@pytest.mark.skip
def test_get_locations_expand():
    response = client.get("/base/location?expand=well")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert "id" in item
        assert "point" in item
        assert "well" in item


@pytest.mark.skip
def test_get_location_expand():
    response = client.get("/base/location/1", params={"expand": "well"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["id"] == 1
    assert "point" in data
    assert data["point"] == "POINT (10.1 10.1)"
    assert "well" in data
    assert len(data["well"]) == 1


# ============= EOF =============================================
