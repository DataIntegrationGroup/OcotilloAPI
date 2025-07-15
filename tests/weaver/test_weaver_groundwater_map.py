import pytest

from tests import client

#get all nmbgmr wells for groundwater map as feature collection
def test_weaver_get_all_wells():
    response = client.get("/thing/well/location_feature_collection") # do we want feature collection endpoints here?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]

#get all nmbgmr springs for the groundwater map as feature collection
def test_weaver_get_all_springs():
    response = client.get("/thing/spring/location_feature_collection") # do we want feature collection endpoints here?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]

#get all collabnet wells for the groundwater map as feature collection
def test_weaver_get_all_collabnet_wells():
    response = client.get("/collabnet/location_feature_collection")
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]

#get all well trends for the groundwater map as feature collection
#skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_get_all_well_trends():
    response = client.get("/thing/well_trend/location_feature_collection") # do we want feature collection endpoints here?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]
        if "manual_trend" in feature["properties"]:
            assert "trend" in feature["properties"]["manual_trend"]

#get all geothermal wells for the groundwater map as feature collection
#skip for now
@pytest.mark.skip
def test_weaver_get_all_geothermal_wells():
    response = client.get("/thing/well?geothermal=true") # or something like this
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]