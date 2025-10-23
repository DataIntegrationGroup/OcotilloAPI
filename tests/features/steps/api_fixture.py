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
from behave import given, when, then
from fastapi.testclient import TestClient
from fastapi_pagination import add_pagination
from starlette.middleware.cors import CORSMiddleware

from core.app import app
from core.dependencies import (
    amp_admin_function,
    admin_function,
    amp_editor_function,
    amp_viewer_function,
    viewer_function,
)
from core.initializers import register_routes, init_lexicon, init_parameter
from db import Location, Thing, LocationThingAssociation, Base, Sensor
from db.engine import session_ctx, engine

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

init_lexicon()
init_parameter()

register_routes(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust as needed for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_pagination(app)


def override_authentication(default=True):
    """
    Override the authentication dependency for testing purposes.
    This allows all users to be considered authenticated.
    """

    def closure():
        # print("Overriding authentication")
        return default

    return closure


app.dependency_overrides[amp_admin_function] = override_authentication(
    default={"name": "foobar", "sub": "1234567890"}
)
app.dependency_overrides[admin_function] = override_authentication(
    default={"name": "foobar", "sub": "1234567890"}
)
app.dependency_overrides[amp_editor_function] = override_authentication(
    default={"name": "foobar", "sub": "1234567890"}
)
app.dependency_overrides[amp_viewer_function] = override_authentication()
app.dependency_overrides[viewer_function] = override_authentication()


# need to figure out better way of doing this

with session_ctx() as session:
    loc = Location(
        # name="first location",
        notes="these are some test notes",
        point="POINT(-107.949533 33.809665)",
        elevation=2464.9,
        release_status="draft",
        elevation_accuracy=100,
        elevation_method="Survey-grade GPS",
        coordinate_accuracy=50,
        coordinate_method="GPS, uncorrected",
        # state="New Mexico",
        # county="Catron",
        # quad_name="Luera Mountains West",
    )
    session.add(loc)
    session.commit()
    session.refresh(loc)

    water_well = Thing(
        name="WL-0001",
        first_visit_date="2023-03-03",
        thing_type="water well",
        release_status="draft",
        well_depth=10,
        hole_depth=10,
        well_construction_notes="Test well construction notes",
        well_casing_diameter=5.0,
        well_casing_depth=10.0,
    )
    session.add(water_well)
    session.commit()
    session.refresh(water_well)

    assoc = LocationThingAssociation()
    assoc.location_id = loc.id
    assoc.thing_id = water_well.id
    assoc.effective_start = "2025-02-01T00:00:00Z"
    session.add(assoc)
    session.commit()

    sensor = Sensor(
        name="Test Sensor",
        sensor_type="Pressure Transducer",
        model="Model X",
        serial_no="123456",
        pcn_number="PCN123456",
        owner_agency="NMBGMR",
        sensor_status="In Service",
        notes="Test equipment",
        release_status="draft",
    )
    session.add(sensor)
    session.commit()


@given("a functioning api")
def step_given_api_is_running(context):
    """
    Ensures the API app is initialized and client is ready.
    Behave will keep 'context' across steps, allowing us to reuse response data.
    """

    client = TestClient(app)
    context.client = client
    assert context.client is not None, "TestClient failed to initialize"


@when("I call the testing API group endpoint")
def step_impl(context):
    context.response = context.client.get("/group")


@then("I should receive a successful response")
def step_impl(context):
    assert (
        context.response.status_code == 200
    ), f"Unexpected response: {context.response.text}"


# ============= EOF =============================================
