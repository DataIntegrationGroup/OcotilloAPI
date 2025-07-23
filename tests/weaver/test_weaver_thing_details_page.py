import pytest

from tests import client


# get location details by id
# TODO: Can we use the thing_id filter on the geospatial endpoint?
def test_weaver_well_thing_by_id():
    response = client.get(
        "/geospatial/feature-collection?thing_id=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert "coordinates" in data["geometry"]

#TODO: will the feature collection above return the thing-specific details?

# get groundwater observations by thing id
def test_weaver_groundwater_observations_by_thing_id():
    response = client.get("/observation/groundwater-level?thing_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)

#Another way to get groundwater levels is to use the observation with observed_property=groundwater-level
#TODO: Do we want this endpoint and the one above for groundwater levels?
def test_weaver_groundwater_observations_by_thing_id_and_property():
    response = client.get("/observation?thing_id=1&observed_property=groundwater-level")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)


# get contact info by thing id
def test_weaver_thing_contact_info_by_id():
    response = client.get("/contact?thing_id=1")  
    assert response.status_code == 200
    data = response.json()
    assert isinstance(
        data, dict
    )  # just assume data dictionary for now used by Weaver (previously Owner)


# get location equipment(sensor) by location id
def test_weaver_thing_sensors_by_id():
    response = client.get("/sensor?thing_id=1")  # or something like this
    assert response.status_code == 200
    data = response.json()
    assert isinstance(
        data, dict
    )  # just assume data dictionary for now used by Weaver (previously Equipment)


# get location photos
def test_weaver_thing_assets_by_id():
    response = client.get("/asset?thing_id=1")  # or something like this
    assert response.status_code == 200
    data = response.json()
    # TODO: implement this


# get water chemistry using crosstab endpoint
#TODO: Implement a crosstab endpoing of some kind
def test_weaver_water_chemistry_crosstab_by_thing_id():
    response = client.get(
        "/water-chemistry-crosstab?thing_id=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)  # should be a dict of dicts (one for each analysis)
