import pytest

from tests import client


# get well info by id as geojson feature with properties
def test_weaver_well_by_id():
    response = client.get(
        "/thing/1?format=geojson"
    )  # TODO: Think about best way to do this query, do we need thing/well endpoint? If you need a list of wells could you do a ?filter like in the weaver_groundwater_map tests? Would table inheritance work to query the parent and get the proper child properties? Or have a thing_type field in the parent? Or do we want to go the sensor things route where the thing table has a type field and a properties field that stores json child properties? Type could go into json properties field too.
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert isinstance(data["geometry"], dict)
    assert "coordinates" in data["geometry"]
    assert "properties" in data
    assert isinstance(data["properties"], dict)
    assert "id" in data["properties"] or "name" in data["properties"]
    # example additional thing properties, but these would be for a well
    assert "usgs_id" in data["properties"]
    assert "api_id" in data["properties"]
    assert "ose_pod_id" in data["properties"]


# get spring info by id as geojson feature with properties
def test_weaver_spring_by_id():
    response = client.get(
        "/thing/1?format=geojson"
    )  # TODO: Same question as above, id would be a spring id
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert isinstance(data["properties"], dict)
    assert "geometry" in data
    assert isinstance(data["geometry"], dict)
    assert "coordinates" in data["geometry"]
    assert "properties" in data
    assert "id" in data["properties"] or "name" in data["properties"]


# get groundwater levels return for hydrograph on dialog
# This should pass right now
def test_weaver_groundwater_observations_by_thing_id():
    response = client.get("/observation/groundwater-level?thing_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)


# get water chemistry by well id
# skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_water_chemistry_by_well_id():
    response = client.get(
        "/observation/water-chemistry?thing_id=1"
    )  # TODO: Not sure this is how we would want to do this?
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)  # should be a dict of dicts (one for each analysis)
