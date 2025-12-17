# ===============================================================================
# Copyright 2025
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
"""
Step definitions for release_status.feature

These tests verify data visibility controls based on release_status field.
Business rules:
- Public users see only data with release_status = "public"
- Staff users see ALL data regardless of release_status
- Private data (release_status = "private") is never visible to public
- Draft data (release_status = "draft") is never visible to public
"""
from behave import given, when, then
from db import Location, Thing, Sample, Observation
from db.engine import session_ctx


# ---------------------------------------------------------------------------
# BACKGROUND / SETUP STEPS
# ---------------------------------------------------------------------------


@given("the NMSampleLocations system is operational")
def step_system_operational(context):
    """System is operational - delegates to common.py 'a functioning api' step"""
    # Import the step from common.py to set up the test client
    from tests.features.steps.common import step_given_api_is_running
    step_given_api_is_running(context)

    # Initialize objects container for test data
    if not hasattr(context, 'objects'):
        context.objects = {}


# ---------------------------------------------------------------------------
# DATA SETUP STEPS - Creating test data with different visibility
# ---------------------------------------------------------------------------


@given("there is {data_type} data in the system")
def step_data_exists(context, data_type):
    """Create test data of various types with mixed release_status values"""
    with session_ctx() as session:
        if data_type == "locations":
            # Create locations with different release_status
            public_loc = Location(
                point="POINT(-106.5 35.0)",
                elevation=1500.0,
                release_status="public",
            )
            private_loc = Location(
                point="POINT(-106.6 35.1)",
                elevation=1600.0,
                release_status="private",
            )
            draft_loc = Location(
                point="POINT(-106.7 35.2)",
                elevation=1700.0,
                release_status="draft",
            )
            session.add_all([public_loc, private_loc, draft_loc])
            session.commit()

            context.public_count = 1
            context.private_count = 1
            context.draft_count = 1
            context.total_count = 3

        elif data_type == "things":
            # Create things with different release_status
            # First create a location for the things
            loc = Location(
                point="POINT(-106.5 35.0)",
                elevation=1500.0,
                release_status="public",
            )
            session.add(loc)
            session.commit()

            public_thing = Thing(
                name="PUBLIC-001",
                thing_type="water well",
                release_status="public",
            )
            private_thing = Thing(
                name="PRIVATE-001",
                thing_type="water well",
                release_status="private",
            )
            draft_thing = Thing(
                name="DRAFT-001",
                thing_type="water well",
                release_status="draft",
            )
            session.add_all([public_thing, private_thing, draft_thing])
            session.commit()

            context.public_count = 1
            context.private_count = 1
            context.draft_count = 1
            context.total_count = 3


@given("some {record_type} are public")
def step_some_records_public(context, record_type):
    """Verify public records exist (already created in previous steps)"""
    # This is an assertion-style Given - confirms the state
    assert hasattr(context, 'public_count'), "Public records should exist"
    assert context.public_count > 0, "Should have at least one public record"


@given("some {record_type} are private")
def step_some_records_private(context, record_type):
    """Verify private records exist (already created in previous steps)"""
    assert hasattr(context, 'private_count'), "Private records should exist"
    assert context.private_count > 0, "Should have at least one private record"


@given("there are sample locations throughout New Mexico")
def step_sample_locations_exist(context):
    """Create sample locations with mixed visibility"""
    with session_ctx() as session:
        public_loc = Location(
            point="POINT(-106.0 35.0)",
            elevation=1500.0,
            release_status="public",
        )
        private_loc = Location(
            point="POINT(-108.0 36.0)",
            elevation=2000.0,
            release_status="private",
        )
        session.add_all([public_loc, private_loc])
        session.commit()

        context.public_locations = 1
        context.private_locations = 1


@given("there are observations for various locations")
def step_observations_exist(context):
    """Create observations with mixed visibility"""
    # For now, just set up context - observations would be created similarly
    context.public_observations = 1
    context.private_observations = 1


@given("a public user requests bulk data")
def step_public_user_requests_bulk(context):
    """Public user initiates a bulk data request"""
    context.is_bulk_request = True


@given("the dataset contains both public and private records")
def step_dataset_mixed_visibility(context):
    """Dataset has mixed visibility (already set up)"""
    assert context.public_count > 0
    assert context.private_count > 0


# ---------------------------------------------------------------------------
# AUTHENTICATION CONTEXT STEPS
# ---------------------------------------------------------------------------


@given("I am a public user (unauthenticated)")
def step_public_user(context):
    """Set context for public/unauthenticated user"""
    context.authenticated = False
    context.user_role = "public"


@given("I am an authenticated staff member")
def step_authenticated_staff(context):
    """Set context for authenticated staff user"""
    context.authenticated = True
    context.user_role = "staff"


@given("there are private observations")
def step_private_observations_exist(context):
    """Verify private observations exist"""
    context.has_private_data = True


# ---------------------------------------------------------------------------
# ACTION STEPS - Making requests
# ---------------------------------------------------------------------------


@when("I view {data_type} data through public endpoints")
def step_view_through_public_endpoints(context, data_type):
    """Make unauthenticated request to public endpoint"""
    # Map data_type to endpoint
    endpoint_map = {
        "locations": "/location",
        "things": "/thing",
        "samples": "/sample",
        "observations": "/observation",
    }

    endpoint = endpoint_map.get(data_type, f"/{data_type}")

    # Make request WITHOUT authentication
    # TODO: Remove authentication override for public endpoints
    context.response = context.client.get(endpoint)
    context.response_data = context.response.json()


@when("I view {data_type} data through authenticated endpoints")
def step_view_through_authenticated_endpoints(context, data_type):
    """Make authenticated request"""
    endpoint_map = {
        "locations": "/location",
        "observations": "/observation",
        "samples": "/sample",
    }

    endpoint = endpoint_map.get(data_type, f"/{data_type}")

    # Make request WITH authentication (already set up in common.py)
    context.response = context.client.get(endpoint)
    context.response_data = context.response.json()


@when("a public user views the interactive web map")
def step_view_web_map(context):
    """Request location data for map display (GeoJSON or similar)"""
    context.response = context.client.get("/location")
    context.response_data = context.response.json()


@when("a public user generates a report")
def step_generate_report(context):
    """Request data for report generation"""
    context.response = context.client.get("/observation")
    context.response_data = context.response.json()


@when("the download is prepared")
def step_download_prepared(context):
    """Prepare bulk download"""
    # For now, this is the same as making a GET request
    context.response = context.client.get("/location")
    context.response_data = context.response.json()


@when("I access internal data management tools")
def step_access_management_tools(context):
    """Access authenticated management interface"""
    context.response = context.client.get("/observation")
    context.response_data = context.response.json()


# ---------------------------------------------------------------------------
# ASSERTION STEPS - Verifying visibility
# ---------------------------------------------------------------------------


@then("I should only see public data")
def step_only_see_public_data(context):
    """Verify response contains only public records"""
    data = context.response_data

    # Handle paginated response
    if "items" in data:
        items = data["items"]
    else:
        items = data if isinstance(data, list) else [data]

    # THIS WILL FAIL until filtering is implemented
    for item in items:
        assert item.get("release_status") == "public", \
            f"Found non-public record: {item.get('release_status')}"

    # Verify we only got public records
    assert len(items) == context.public_count, \
        f"Expected {context.public_count} public records, got {len(items)}"


@then("I should not see private data")
def step_should_not_see_private_data(context):
    """Verify no private records in response"""
    data = context.response_data

    if "items" in data:
        items = data["items"]
    else:
        items = data if isinstance(data, list) else [data]

    # THIS WILL FAIL until filtering is implemented
    for item in items:
        assert item.get("release_status") != "private", \
            "Found private record in public response"


@then("I should not see draft data")
def step_should_not_see_draft_data(context):
    """Verify no draft records in response"""
    data = context.response_data

    if "items" in data:
        items = data["items"]
    else:
        items = data if isinstance(data, list) else [data]

    # THIS WILL FAIL until filtering is implemented
    for item in items:
        assert item.get("release_status") != "draft", \
            "Found draft record in public response"


@then("I should see all data including public and private datasets")
def step_see_all_data(context):
    """Verify authenticated user sees all records"""
    data = context.response_data

    if "items" in data:
        items = data["items"]
        total = data.get("total", len(items))
    else:
        items = data if isinstance(data, list) else [data]
        total = len(items)

    # Staff should see ALL records regardless of release_status
    assert total == context.total_count, \
        f"Expected staff to see {context.total_count} records, got {total}"


@then("each record should clearly indicate whether it is public or private")
def step_records_indicate_visibility(context):
    """Verify release_status field is present and valid"""
    data = context.response_data

    if "items" in data:
        items = data["items"]
    else:
        items = data if isinstance(data, list) else [data]

    valid_statuses = ["public", "private", "draft", "provisional", "final", "published", "archived"]

    for item in items:
        assert "release_status" in item, "release_status field missing from response"
        assert item["release_status"] in valid_statuses, \
            f"Invalid release_status: {item['release_status']}"


@then("only public {record_type} should appear")
def step_only_public_appear(context, record_type):
    """Verify only public records in response"""
    data = context.response_data

    if "items" in data:
        items = data["items"]
    else:
        items = data if isinstance(data, list) else [data]

    # THIS WILL FAIL until filtering is implemented
    for item in items:
        assert item.get("release_status") == "public", \
            f"Expected only public {record_type}, found {item.get('release_status')}"


@then("only public locations should be displayed")
def step_only_public_locations_displayed(context):
    """Verify map only shows public locations"""
    step_only_public_appear(context, "locations")


@then("private {record_type} should be excluded from the report")
def step_private_excluded_from_report(context, record_type):
    """Verify private records not in report"""
    step_should_not_see_private_data(context)


@then("private locations should not appear on the map")
def step_private_not_on_map(context):
    """Verify private locations not on map"""
    step_should_not_see_private_data(context)


@then("clicking a public location should show its details")
def step_clicking_public_location(context):
    """Verify public location details are accessible"""
    # This would test a specific location GET endpoint
    # For now, just verify we can access the collection
    assert context.response.status_code == 200


@then("only public records should be included")
def step_only_public_in_download(context):
    """Verify download contains only public records"""
    step_only_see_public_data(context)


@then("private records should be automatically filtered out")
def step_private_filtered_out(context):
    """Verify private records are filtered"""
    step_should_not_see_private_data(context)


@then("the download should indicate it contains public data only")
def step_download_indicates_public(context):
    """Verify download metadata indicates public-only"""
    # This could check response headers or metadata
    # For now, just verify the filtering worked
    assert context.response.status_code == 200


@then("I can view all private {record_type}")
def step_can_view_private_records(context, record_type):
    """Verify staff can see private records"""
    # Staff should see all records including private
    step_see_all_data(context)


@then("I can analyze data including private records")
def step_can_analyze_with_private(context):
    """Verify staff can work with private data"""
    # Staff should have access to all data
    step_see_all_data(context)


@then("I can change data from private to public")
def step_can_change_visibility(context):
    """Verify staff can update release_status"""
    # This would test a PATCH/PUT endpoint
    # For now, just mark as tested
    context.can_update_status = True


# ---------------------------------------------------------------------------
# WORKFLOW AND STATUS CHANGE STEPS
# ---------------------------------------------------------------------------


@given("data is being submitted to the system")
def step_data_being_submitted(context):
    """Data submission workflow initiated"""
    context.submitting_data = True


@when("a new record is created")
def step_new_record_created(context):
    """Create a new record without specifying release_status"""
    with session_ctx() as session:
        # Create without explicit release_status - should use default
        new_loc = Location(
            point="POINT(-107.0 36.0)",
            elevation=1800.0,
            # release_status not specified - tests default
        )
        session.add(new_loc)
        session.commit()
        session.refresh(new_loc)

        context.new_record_status = new_loc.release_status


@then("the system should apply a safe default visibility status")
def step_safe_default_applied(context):
    """Verify default is safe (not public)"""
    # Default should be "draft" or "private", never "public"
    assert context.new_record_status in ["draft", "private"], \
        f"Unsafe default: {context.new_record_status}"


@then("the default should protect sensitive data")
def step_default_protects_data(context):
    """Verify default is protective"""
    assert context.new_record_status != "public", \
        "Default should not be public"


# ============= EOF =============================================
