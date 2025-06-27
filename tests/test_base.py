# from fastapi.testclient import TestClient
# from main import app
# from models import Base, engine

# Base.metadata.drop_all(engine)
# Base.metadata.create_all(engine)

# client = TestClient(app)

from tests import client


#  ADD tests ======================================================
def test_add_location():
    response = client.post(
        "/base/location",
        json={
            "name": "Test Location 1",
            "point": "POINT(10.1 10.1)",
            "visible": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1

    response = client.post(
        "/base/location",
        json={
            "name": "Test Location 2",
            "point": "POINT(50.0 50.0)",
            "visible": False,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 2


def test_add_well():
    # response = client.post(
    #     "/lexicon/add", json={"term": "Monitoring", "definition": "Monitoring Well"}
    # )
    # assert response.status_code == 200
    # response = client.post(
    #     "/lexicon/add", json={"term": "Production", "definition": "Production Well"}
    # )
    # assert response.status_code == 200

    response = client.post(
        "/base/well",
        json={
            "location_id": 1,
            "api_id": "1001-0001",
            "ose_pod_id": "RA-0001",
            "well_type": "Monitoring",
            "well_depth": 100.0,
            "construction_notes": "this is a test of notes",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data

    response = client.post(
        "/base/well",
        json={
            "location_id": 2,
            "api_id": "1001-0002",
            "ose_pod_id": "RA-0002",
            "well_type": "Production",
            "well_depth": 1200.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


def test_add_equipment():
    response = client.post(
        "/base/equipment",
        json={
            "equipment_type": "Pump",
            "model": "Model X",
            "serial_no": "123456",
            "date_installed": "2023-01-01T00:00:00",
            "date_removed": None,
            "recording_interval": 60,
            "equipment_notes": "Test equipment",
            "location_id": 2,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["location_id"] == 2


def test_add_spring():
    response = client.post("/base/spring", json={"location_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


def test_add_well_screen():
    # response = client.post(
    #     "/lexicon/add",
    #     json={"term": "PVC", "definition": "PVC Well Screen"},
    # )
    # assert response.status_code == 200
    response = client.post(
        "/base/wellscreen",
        json={
            "well_id": 1,
            "screen_depth_top": 10.0,
            "screen_depth_bottom": 20.0,
            "screen_type": "PVC",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["well_id"] == 1


def test_add_group():
    response = client.post("/base/group", json={"name": "Test Group"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Group"


def test_add_group_location():
    response = client.post(
        "/base/group_location", json={"group_id": 1, "location_id": 1}
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["group_id"] == 1
    assert data["location_id"] == 1


def test_add_owner():

    response = client.post("/base/owner", json={"name": "Test Owner"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Owner"

    for i in range(1, 4):
        response = client.post(
            "/base/owner",
            json={"name": f"Test Owner {i}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == f"Test Owner {i}"



def test_add_contact():
    response = client.post(
        "/base/contact",
        json={
            "owner_id": 1,
            "name": "Test Contact",
            "email": "fasdfasdf@gmail.com",
            "phone": "+12345678901",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Contact"
    assert data["email"] == "fasdfasdf@gmail.com"

    for i in range(2, 5):
        response = client.post(
            "/base/contact",
            json={
                "owner_id": i,
                "name": f"Test Contact {i}",
                "email": f"foo{i}@gmail.com",
                "phone": f"+1234567890{i}",
            })
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == f"Test Contact {i}"
        assert data["email"] == f"foo{i}@gmail.com"
        assert data["phone"] == f"+1234567890{i}"


# GET tests ======================================================
def test_get_locations_expand():
    response = client.get("/base/location?expand=well")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert "id" in item
        assert "point" in item
        assert "well" in item


def test_get_location_expand():
    response = client.get("/base/location/1", params={"expand": "well"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["id"] == 1
    assert "point" in data
    assert data["point"] == "POINT (10.1 10.1)"
    assert "well" in data
    assert len(data["well"]) == 1


def test_get_springs():
    response = client.get("/base/spring")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_wells():
    response = client.get("/base/well")
    assert response.status_code == 200
    assert len(response.json()) > 0


# def test_get_locations():
#     response = client.get("/base/location")
#     assert response.status_code == 200
#     assert len(response.json()) > 0


def test_get_groups():
    response = client.get("/base/group")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_owners():
    response = client.get("/base/owner")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_contacts():
    response = client.get("/base/contact")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_well_screens():
    response = client.get("/base/wellscreen")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_group_locations():
    response = client.get("/base/group_location")
    assert response.status_code == 200
    assert len(response.json()) > 0


# test item retrieval via filter ===========================================
def test_item_get_well_filter():
    response = client.get("/base/well", params={"api_id": "1001-0002"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert "api_id" in data["items"][0]
    assert data["items"][0]["api_id"] == "1001-0002"


def test_item_get_well_filter_nonexistent():
    response = client.get("/base/well", params={"api_id": "9999-9999"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 0


def test_item_get_well_filter_pod_id():
    response = client.get("/base/well", params={"ose_pod_id": "RA-0001"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert "ose_pod_id" in item
    assert item["ose_pod_id"] == "RA-0001"


# Test item retrieval ======================================================
def test_item_get_spring():
    response = client.get("/base/spring/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["location_id"] == 1


def test_item_get_owner():
    response = client.get("/base/owner/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Owner"


def test_item_get_location():
    response = client.get("/base/location/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Location 1"
    assert "well" not in data


def test_item_get_group():
    response = client.get("/base/group/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Group"


def test_item_get_wells():
    response = client.get("/base/well/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["location_id"] == 1


def test_item_get_well_screens():
    response = client.get("/base/wellscreen/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["well_id"] == 1
    assert data["screen_depth_top"] == 10.0
    assert data["screen_depth_bottom"] == 20.0


def test_item_get_group_locations():
    response = client.get("/base/group_location/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["group_id"] == 1
    assert data["location_id"] == 1


def test_item_get_contact():
    response = client.get("/base/contact/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Contact"
    assert data["email"] == "fasdfasdf@gmail.com"
    assert data["phone"] == "+12345678901"
