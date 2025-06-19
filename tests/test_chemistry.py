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


# add ===================
def test_add_analysis_set():
    response = client.post(
        "/chemistry/analysis_set",
        json={
            "well_id": 1,
            "laboratory": "Test Lab",
            "collection_timestamp": "2025-01-01T12:00:00",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["well_id"] == 1
    assert data["laboratory"] == "Test Lab"

    response = client.post(
        "/chemistry/analysis_set",
        json={
            "well_id": 2,
            "laboratory": "Test Lab",
            "collection_timestamp": "2025-01-01T12:00:00",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["well_id"] == 2
    assert data["laboratory"] == "Test Lab"


def test_add_analysis():

    response = client.post(
        "/chemistry/analysis",
        json={
            "analysis_set_id": 1,
            "value": 7.0,
            "unit": "mg/L",
            "analyte": "TDS",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["analysis_set_id"] == 1
    assert data["value"] == 7.0
    assert data["unit"] == "mg/L"
    assert data["analyte"] == "TDS"

    response = client.post(
        "/chemistry/analysis",
        json={
            "analysis_set_id": 2,
            "value": 8.0,
            "unit": "mg/L",
            "analyte": "Na",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["analysis_set_id"] == 2
    assert data["value"] == 8.0
    assert data["unit"] == "mg/L"
    assert data["analyte"] == "Na"


# get ===================


def test_get_chemistry_analysis_set():
    response = client.get("/chemistry/analysis_set")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2
    item = data["items"][0]
    assert item["well_id"] == 1
    assert item["laboratory"] == "Test Lab"


def test_get_chemistry_analysis():
    response = client.get("/chemistry/analysis")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2
    item = data["items"][0]
    assert item["analysis_set_id"] == 1
    assert item["value"] == 7.0
    assert item["unit"] == "mg/L"


def test_geospatial_chemistry_analysis_set():
    response = client.get(
        "/chemistry/analysis_set",
        params={
            "within": "POLYGON((10.0 10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, 10.0 10.0))"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    # item = data['items'][0]
    # assert item['analysis_set_id'] == 1
    # assert item['value'] == 7.0
    # assert item['unit'] == 'mg/L'
    # assert 'geometry' in item  # Assuming geometry is part of the response


def test_geospatial_chemistry_analysis():
    response = client.get(
        "/chemistry/analysis",
        params={
            "within": "POLYGON((10.0 10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, 10.0 10.0))"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    # item = data['items'][0]
    # assert item['analysis_set_id'] == 1
    # assert item['value'] == 7.0
    # assert item['unit'] == 'mg/L'
    # assert 'geometry' in item  # Assuming geometry is part of the response


# ============= EOF =============================================
