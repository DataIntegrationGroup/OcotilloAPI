import pytest

from tests import client


# get all nmbgmr wells for groundwater map as feature collection
def test_weaver_get_all_wells():
    response = client.get(
        "/thing?type=well"
    )  # TODO: QUESTION: use type filter instead of /well endpoint?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "properties" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]
        assert "thing_url" in feature["properties"]


# get all nmbgmr springs for the groundwater map as feature collection
def test_weaver_get_all_springs():
    response = client.get(
        "/thing?type=spring"
    )  # TODO: QUESTION: use type filter instead of /spring endpoint?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert "properties" in feature
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]


# get all collabnet wells for the groundwater map as feature collection
def test_weaver_get_all_collabnet_wells():
    response = client.get(
        "/thing?type=well&group=collabnet"
    )  # TODO: QUESTION: use type filter and a group filter instead of /collabnet endpoint?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert isinstance(feature["geometry"], dict)
        assert "properties" in feature
        assert isinstance(feature["properties"], dict)
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]


# get all well trends for the groundwater map as feature collection
# skip for now - not implemented yet
@pytest.mark.skip
def test_weaver_get_all_well_trends():
    response = client.get(
        "/thing?type=well&group=trend"
    )  # TODO: QUESTION: Group filter by trend or a trend endpoint?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert isinstance(feature["geometry"], dict)
        assert "properties" in feature
        assert isinstance(feature["properties"], dict)
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]
        # just an example of trend property
        if "manual_trend" in feature["properties"]:
            assert "trend" in feature["properties"]["manual_trend"]


# get all geothermal wells for the groundwater map as feature collection
# skip for now
@pytest.mark.skip
def test_weaver_get_all_geothermal_wells():
    response = client.get(
        "/thing?type=well&subtype=geothermal"
    )  # TODO: QUESTION: use type filter and a subtype filter instead of geothermal endpoint?
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    for feature in data["features"]:
        assert "geometry" in feature
        assert isinstance(feature["geometry"], dict)
        assert "properties" in feature
        assert isinstance(feature["properties"], dict)
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]
