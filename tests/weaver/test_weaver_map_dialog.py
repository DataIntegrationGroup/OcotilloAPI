import pytest

from tests import client

#get well info by id as geojson feature with properties
def test_weaver_well_by_id():
    response = client.get("/thing/well/1") #different endpoint for geojson feature?
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
    assert "usgs_id" in data["properties"]
    assert "api_id" in data["properties"]
    assert "ose_pod_id" in data["properties"]

#get spring info by id as geojson feature with properties
def test_weaver_spring_by_id():
    response = client.get("/thing/spring/1") #different endpoint for geojson feature?
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert isinstance(data["geometry"], dict)
    assert "coordinates" in data["geometry"]
    assert "properties" in data
    assert "id" in data["properties"] or "name" in data["properties"]

#get groundwater levels return for hydrograph on dialog
def test_weaver_groundwater_observations_by_thing_id():
    response = client.get("/observation/groundwater-level?thing_id=1") 
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)

#get water chemistry by well id
#skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_water_chemistry_by_well_id():
    response = client.get("/thing/well/1/water_chemistry") # again not sure this is the right endpoint
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict) # should be a dict of dicts (one for each analysis)