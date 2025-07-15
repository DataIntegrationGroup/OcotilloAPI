import pytest

from tests import client

#get location details by id
def test_weaver_location_details_by_id():
    response = client.get("/location/1")
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert "coordinates" in data["geometry"]

#get well details by location id
def test_weaver_location_well_details_by_id():
    response = client.get("/location/1?expand=well")
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert "coordinates" in data["geometry"]
    assert "id" in data["properties"] or "name" in data["properties"]
    assert "well" in data

#get groundwater observations by thing id
#do I need to get a list of things from the location first?
def test_weaver_groundwater_observations_by_thing_id():
    response = client.get("/observation/groundwater-level?thing_id=1") 
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)

#get contact info by location id
def test_weaver_location_contact_info_by_id():
    response = client.get("/location/1?expand=contact") #or something like this
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert "coordinates" in data["geometry"]
    assert "id" in data["properties"] or "name" in data["properties"]
    assert "contact" in data

#get location equipment(sensor) by location id
def test_weaver_location_equipment_by_id():
    response = client.get("/location/1?expand=sensor") #or something like this
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert "coordinates" in data["geometry"]
    assert "id" in data["properties"] or "name" in data["properties"]
    assert "sensor" in data
    
#get location photos
#skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_location_photos_by_id():
    response = client.get("/location/1?expand=photo") #or something like this
    assert response.status_code == 200
    data = response.json()
    #TODO: implement this

#skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_water_chemistry_by_well_id():
    response = client.get("/thing/well/1/water_chemistry") # again not sure this is the right endpoint
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict) # should be a dict of dicts (one for each analysis)