import pytest

from tests import client


# get well info by id as geojson feature with properties
# Not geospatial, just a thing endpoint
def test_weaver_thing_by_id():
    response = client.get("/thing/1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


# get groundwater levels return for hydrograph on dialog
def test_weaver_groundwater_observations_by_thing_id():
    response = client.get("/observation/groundwater-level?thing_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)


# Another way to get groundwater levels is to use the observation with observed_property=groundwater-level
# TODO: Do we want this endpoint and the one above for groundwater levels? Choose one.
def test_weaver_groundwater_observations_by_thing_id_and_property():
    response = client.get("/observation?thing_id=1&observed_property=groundwater-level")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)


# get water chemistry using crosstab endpoint
# TODO: Implement a crosstab endpoing of some kind
def test_weaver_water_chemistry_crosstab_by_thing_id():
    response = client.get("/water-chemistry-crosstab?thing_id=1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)  # should be a dict of dicts (one for each analysis)


# get water chemistry by property using observed_property
def test_weaver_water_chemistry_by_property():
    response = client.get("/observation?thing_id=1&observed_property=pH")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)  # should be a dict of dicts (one for each analysis)
