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


def test_query_nested_string_search():
    response = client.get(
        "/base/location",
        params={
            "query": "well.construction_notes like '%test%'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1  # Assuming there are two locations starting with 'Test'
    # assert all(item["name"].startswith("Test") for item in items)


def test_query_string_search():
    response = client.get(
        "/base/well",
        params={
            "query": "construction_notes like '%test%'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1  # Assuming there are two locations starting with 'Test'
    # assert all(item["name"].startswith("Test") for item in items)


def test_query_eq_true():
    response = client.get(
        "/base/location",
        params={
            "query": "visible eq true",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1


def test_query_eq_false():
    response = client.get(
        "/base/location",
        params={
            "query": "visible eq false",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2


def test_query_like():
    response = client.get(
        "/base/location",
        params={
            "query": "name like 'Test%'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2  # Assuming there are three locations starting with 'Test'
    assert all(item["name"].startswith("Test") for item in items)


def test_query_nested_eq():
    response = client.get(
        "/base/location",
        params={
            "query": "well.api_id eq '1001-0001'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Test Location 1"  # Assuming this is the expected name


def test_query_nested_ne():
    response = client.get(
        "/base/location",
        params={
            "query": "well.api_id ne '1001-0001'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2  # Assuming there are two locations not matching the API ID
    assert all(
        item["name"] != "Test Location 1" for item in items
    )  # Ensure none match the excluded ID


def test_query_nested_like():
    response = client.get(
        "/base/location",
        params={
            "query": "well.api_id like '1001-%'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    assert items[0]["name"] == "Test Location 1"
    assert items[1]["name"] == "Test Location 2"


def test_query_nested_well_ose_pod_id_like():
    response = client.get(
        "/base/location",
        params={
            "query": "well.ose_pod_id like 'RA%'",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2  # Assuming two wells match this pattern
    assert items[0]["name"] == "Test Location 1"
    assert items[1]["name"] == "Test Location 2"


def test_query_nested_well_depth_between():
    response = client.get(
        "/base/location",
        params={
            "query": "well.well_depth between [50,1000]",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1  # Assuming two wells fall within this depth range
    # assert all(500 <= item["well"]["depth"] <= 1500 for item in items)


def test_query_nested_well_depth_gt():
    response = client.get(
        "/base/location",
        params={
            "query": "well.well_depth gt 1000",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1  # Assuming one well exceeds this depth
    assert items[0]["name"] == "Test Location 2"  # Assuming this is the expected name
    # assert all(item["well"]["depth"] > 500 for item in items)


def test_query_nested_well_depth_lt():
    response = client.get(
        "/base/location",
        params={
            "query": "well.well_depth lt 200",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1  # Assuming one well is below this depth
    assert items[0]["name"] == "Test Location 1"
    # assert all(item["well"]["depth"] < 1500 for item in items)


def test_query_nested_well_depth_eq():
    response = client.get(
        "/base/location",
        params={
            "query": "well.well_depth eq 100",
        },
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1  # Assuming one well is at or above this depth
    assert items[0]["name"] == "Test Location 1"
    # assert all(item["well"]["depth"] >= 500 for item in items)


# ============= EOF =============================================
