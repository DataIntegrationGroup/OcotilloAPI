import pytest

from tests import client


# NOTE: I've been thinking about the locations details in the way Weaver dealt with the previous API, in that each location was a single thing. This is not the case anymore, so "thing" should be the center item displayed on the "thing" details page.
# get location details by id
def test_weaver_thing_details_by_id():
    response = client.get(
        "/thing/1?format=geojson"
    )  # TODO: same note as in the map thing dialog test, do we need a thing/well endpoint? Or can we just use the thing id and get all properties?
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "properties" in data
    assert "geometry" in data
    assert "coordinates" in data["geometry"]


# get well details by location id TODO: this is not needed if the above thing returns well details (or spring details etc)
# def test_weaver_location_well_details_by_id():
#     response = client.get("/location/1?expand=well")
#     assert response.status_code == 200
#     data = response.json()
#     assert "type" in data
#     assert "properties" in data
#     assert "geometry" in data
#     assert "coordinates" in data["geometry"]
#     assert "id" in data["properties"] or "name" in data["properties"]
#     assert "well" in data


# get groundwater observations by thing id
# This should pass right now
def test_weaver_groundwater_observations_by_thing_id():
    response = client.get("/observation/groundwater-level?thing_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        assert isinstance(data["items"][0], dict)


# get contact info by thing id
def test_weaver_thing_contact_info_by_id():
    response = client.get("/contact?thing_id=1")  # or something like this
    assert response.status_code == 200
    data = response.json()
    assert isinstance(
        data, dict
    )  # just assume data dictionary for now used by Weaver (previously Owner)


# get location equipment(sensor) by location id
def test_weaver_thing_equipment_by_id():
    response = client.get("/sensor?thing_id=1")  # or something like this
    assert response.status_code == 200
    data = response.json()
    assert isinstance(
        data, dict
    )  # just assume data dictionary for now used by Weaver (previously Equipment)


# get location photos
# skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_thing_photos_by_id():
    response = client.get("/photo?thing_id=1")  # or something like this
    assert response.status_code == 200
    data = response.json()
    # TODO: implement this


# skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_water_chemistry_by_well_id():
    response = client.get(
        "/observation/water-chemistry?thing_id=1"
    )  # again not sure this is the right endpoint
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)  # should be a dict of dicts (one for each analysis)
