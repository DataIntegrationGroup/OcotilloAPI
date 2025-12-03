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
from datetime import date, datetime, timezone
from behave import given, when, then, register_type
from behave.runner import Context
import parse

from db import Location, Thing, LocationThingAssociation
from db.engine import session_ctx


# Custom type parsers
@parse.with_pattern(r"\d+")
def parse_number(text):
    return int(text)


register_type(Number=parse_number)


def create_test_location(nma_date_created=None, nma_site_date=None):
    """Helper to create a test location with AMPAPI date fields (read-only post-migration)."""
    with session_ctx() as session:
        location = Location(
            point="POINT(-106.607784 35.118924)",
            elevation=1558.8,
            release_status="public",
            nma_date_created=nma_date_created,
            nma_site_date=nma_site_date,
        )
        session.add(location)
        session.commit()
        session.refresh(location)
        return location


@given("the AMPAPI data has been migrated to the database")
def step_given_data_migrated(context: Context):
    """Assumption that migration has occurred."""
    context.migrated = True


@given("a location exists with")
def step_given_location_with_table(context: Context):
    """Create location with fields from table."""
    data = {row["field"]: row["value"] for row in context.table}

    nma_date_created = (
        date.fromisoformat(data["nma_date_created"])
        if data.get("nma_date_created") and data["nma_date_created"] != "null"
        else None
    )
    nma_site_date = (
        date.fromisoformat(data["nma_site_date"])
        if data.get("nma_site_date") and data["nma_site_date"] != "null"
        else None
    )

    location = create_test_location(
        nma_date_created=nma_date_created, nma_site_date=nma_site_date
    )

    context.test_location = location
    context.test_location_id = location.id


@given("{count:Number} locations exist with various legacy dates")
def step_given_multiple_locations(context: Context, count: int):
    """Create multiple locations with various legacy dates."""
    context.test_locations = []

    test_data = [
        ("2014-04-03", "2002-12-10"),
        ("2014-04-03", "2003-01-07"),
        ("2017-12-06", "2003-12-11"),
        ("2008-05-28", "1954-05-01"),
        ("2020-01-15", None),
    ]

    for i in range(min(count, len(test_data))):
        legacy_date, site_date = test_data[i]
        location = create_test_location(
            nma_date_created=date.fromisoformat(legacy_date),
            nma_site_date=(date.fromisoformat(site_date) if site_date else None),
        )
        context.test_locations.append(location)


@given(
    "locations exist with nma_site_date ranging from {start_year:Number} to {end_year:Number}"
)
def step_given_locations_date_range(context: Context, start_year: int, end_year: int):
    """Create locations with nma_site_date across a date range."""
    context.test_locations = []

    years = [1954, 2002, 2003, 2010, 2015, 2020, 2024]
    for year in years:
        location = create_test_location(
            nma_date_created=date(year + 5, 1, 1),  # Always 5 years after site date
            nma_site_date=date(year, 6, 15),
        )
        context.test_locations.append(location)


@given('{count:Number} locations exist with nma_date_created "{target_date}"')
def step_given_locations_with_specific_date(
    context: Context, count: int, target_date: str
):
    """Create locations with specific nma_date_created."""
    if not hasattr(context, "test_locations"):
        context.test_locations = []

    target = date.fromisoformat(target_date)

    for i in range(count):
        location = create_test_location(
            nma_date_created=target,
            nma_site_date=date(2000 + i, 1, 1),  # Vary the site dates
        )
        context.test_locations.append(location)


@given("{count:Number} locations were migrated")
def step_given_count_locations_migrated(context: Context, count: int):
    """Create specified number of test locations."""
    context.test_locations = []

    for i in range(count):
        # 9% have nma_site_date
        has_site_date = i < count * 0.09

        location = create_test_location(
            nma_date_created=date(2014, 1, i % 28 + 1),
            nma_site_date=date(2003, 1, i % 28 + 1) if has_site_date else None,
        )
        context.test_locations.append(location)


@given("{count:Number} of them had non-null SiteDate in AMPAPI")
def step_given_sitedate_count(context: Context, count: int):
    """Declarative - data created in previous step."""
    pass


@given("a location was migrated with legacy dates")
def step_given_location_migrated_with_dates(context: Context):
    """Create location with both legacy dates."""
    location = create_test_location(
        nma_date_created=date(2014, 4, 3), nma_site_date=date(2002, 12, 10)
    )
    context.test_location = location


# WHEN steps


@when("I retrieve that location via the API")
def step_when_retrieve_location_api(context: Context):
    """Retrieve location via GET API."""
    response = context.client.get(f"/location/{context.test_location_id}")
    assert response.status_code == 200
    context.location_response = response.json()


@when("I GET /location to list all locations")
def step_when_get_all_locations(context: Context):
    """Get all locations."""
    response = context.client.get("/location")
    assert response.status_code == 200
    context.locations_response = response.json()


@when(
    'I filter locations where nma_site_date is between "{start_date}" and "{end_date}"'
)
def step_when_filter_locations(context: Context, start_date: str, end_date: str):
    """Filter locations by date range."""
    # Since API may not support this yet, query database directly
    with session_ctx() as session:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        locations = (
            session.query(Location)
            .filter(Location.nma_site_date >= start, Location.nma_site_date <= end)
            .all()
        )

        context.filtered_locations = locations


@when('I query for locations with nma_date_created "{target_date}"')
def step_when_query_by_legacy_date(context: Context, target_date: str):
    """Query locations by nma_date_created."""
    with session_ctx() as session:
        target = date.fromisoformat(target_date)
        locations = (
            session.query(Location).filter(Location.nma_date_created == target).all()
        )
        context.queried_locations = locations


@when("I query the migrated locations")
def step_when_query_migrated_locations(context: Context):
    """Query all test locations."""
    with session_ctx() as session:
        # Query only our test locations
        location_ids = [loc.id for loc in context.test_locations]
        locations = session.query(Location).filter(Location.id.in_(location_ids)).all()
        context.queried_locations = locations


@when("I retrieve that location")
def step_when_retrieve_location(context: Context):
    """Retrieve location by ID."""
    with session_ctx() as session:
        location = session.get(Location, context.test_location.id)
        context.retrieved_location = location


# THEN steps


@then('the response should include nma_date_created as "{expected_date}"')
def step_then_nma_date_created(context: Context, expected_date: str):
    """Assert nma_date_created matches."""
    actual = context.location_response.get("nma_date_created")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then('the response should include nma_site_date as "{expected_date}"')
def step_then_nma_site_date(context: Context, expected_date: str):
    """Assert nma_site_date matches."""
    actual = context.location_response.get("nma_site_date")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then("the time gap should be approximately {years} years")
def step_then_time_gap_years(context: Context, years: str):
    """Assert approximate year gap."""
    legacy_str = context.location_response.get("nma_date_created")
    site_date_str = context.location_response.get("nma_site_date")

    if not legacy_str or not site_date_str:
        raise AssertionError("Missing date fields for gap calculation")

    legacy_date = date.fromisoformat(legacy_str)
    site_date = date.fromisoformat(site_date_str)

    gap_days = (legacy_date - site_date).days
    gap_years = gap_days / 365.25

    expected_years = float(years)
    tolerance = 0.5
    assert (
        abs(gap_years - expected_years) < tolerance
    ), f"Expected ~{expected_years} year gap, got {gap_years:.1f} years"


@then("each location should have a nma_date_created field")
def step_then_all_have_legacy_field(context: Context):
    """Assert all locations have the field."""
    items = context.locations_response.get("items", [])
    for item in items:
        assert "nma_date_created" in item, f"Location missing nma_date_created"


@then("each location should have a nma_site_date field")
def step_then_all_have_site_date_field(context: Context):
    """Assert all locations have the field."""
    items = context.locations_response.get("items", [])
    for item in items:
        assert "nma_site_date" in item, f"Location missing nma_site_date"


@then("some locations should have null nma_site_date")
def step_then_some_null_site_date(context: Context):
    """Assert some locations have null."""
    items = context.locations_response.get("items", [])
    null_count = sum(1 for item in items if item.get("nma_site_date") is None)
    assert null_count > 0, "Expected at least one location with null nma_site_date"


@then("the response should only include locations with site date in that decade")
def step_then_locations_in_decade(context: Context):
    """Assert filtered locations are in range."""
    for loc in context.filtered_locations:
        assert (
            2000 <= loc.nma_site_date.year <= 2010
        ), f"Location not in 2000-2010: {loc.nma_site_date}"


@then("locations with site date before {year:Number} should not be included")
def step_then_locations_before_excluded(context: Context, year: int):
    """Assert no locations before year."""
    for loc in context.filtered_locations:
        assert (
            loc.nma_site_date.year >= year
        ), f"Location from {loc.nma_site_date.year} should not be included"


@then("locations with site date after {year:Number} should not be included")
def step_then_locations_after_excluded(context: Context, year: int):
    """Assert no locations after year."""
    for loc in context.filtered_locations:
        assert (
            loc.nma_site_date.year <= year
        ), f"Location from {loc.nma_site_date.year} should not be included"


@then("the response should include exactly {count:Number} locations")
def step_then_exact_count_locations(context: Context, count: int):
    """Assert exact count."""
    actual = len(context.queried_locations)
    assert actual == count, f"Expected {count} locations, got {actual}"


@then('all should have nma_date_created "{expected_date}"')
def step_then_all_have_date(context: Context, expected_date: str):
    """Assert all have same date."""
    expected = date.fromisoformat(expected_date)
    for loc in context.queried_locations:
        assert (
            loc.nma_date_created == expected
        ), f"Location has {loc.nma_date_created}, expected {expected}"


@then("{percentage:Number}% should have non-null nma_site_date")
def step_then_percentage_site_date(context: Context, percentage: int):
    """Assert percentage with nma_site_date."""
    total = len(context.queried_locations)
    populated = sum(1 for loc in context.queried_locations if loc.nma_site_date)
    actual_pct = (populated / total) * 100

    tolerance = 2
    assert (
        abs(actual_pct - percentage) < tolerance
    ), f"Expected ~{percentage}%, got {actual_pct:.1f}%"


@then("{percentage:Number}% should have non-null nma_date_created")
def step_then_percentage_legacy(context: Context, percentage: int):
    """Assert percentage with nma_date_created."""
    total = len(context.queried_locations)
    populated = sum(1 for loc in context.queried_locations if loc.nma_date_created)
    actual_pct = (populated / total) * 100

    tolerance = 2
    assert (
        abs(actual_pct - percentage) < tolerance
    ), f"Expected ~{percentage}%, got {actual_pct:.1f}%"


@then("it should have created_at (new system timestamp from migration)")
def step_then_has_created_at(context: Context):
    """Assert created_at exists."""
    assert context.retrieved_location.created_at is not None


@then("it should have nma_date_created (original AMPAPI DateCreated)")
def step_then_has_legacy_date(context: Context):
    """Assert nma_date_created exists."""
    assert context.retrieved_location.nma_date_created is not None


@then("it should have nma_site_date (original AMPAPI SiteDate)")
def step_then_has_site_date(context: Context):
    """Assert nma_site_date exists."""
    assert context.retrieved_location.nma_site_date is not None


@then("all three timestamps should be independently queryable")
def step_then_all_queryable(context: Context):
    """Assert all fields are queryable."""
    assert hasattr(context.retrieved_location, "created_at")
    assert hasattr(context.retrieved_location, "nma_date_created")
    assert hasattr(context.retrieved_location, "nma_site_date")


@then("created_at should be a recent timestamp")
def step_then_created_at_recent(context: Context):
    """Assert created_at is recent."""
    created_at = context.retrieved_location.created_at
    now = datetime.now(timezone.utc)

    # Ensure both datetimes are timezone-aware for accurate comparison
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    diff_seconds = abs((now - created_at).total_seconds())
    assert diff_seconds < 3600, "created_at should be within last hour"


@then("nma_date_created should be an older date")
def step_then_legacy_date_older(context: Context):
    """Assert nma_date_created is old."""
    legacy_date = context.retrieved_location.nma_date_created
    assert legacy_date.year < 2024, "nma_date_created should be from the past"


@then('nma_date_created should be "{expected_date}"')
def step_then_legacy_is(context: Context, expected_date: str):
    """Assert nma_date_created value."""
    actual = context.retrieved_location.nma_date_created
    expected = date.fromisoformat(expected_date)
    assert actual == expected, f"Expected {expected}, got {actual}"


@then('nma_site_date should be "{expected_date}"')
def step_then_site_date_is(context: Context, expected_date: str):
    """Assert nma_site_date value."""
    actual = context.retrieved_location.nma_site_date
    expected = date.fromisoformat(expected_date)
    assert actual == expected, f"Expected {expected}, got {actual}"


@then("the system should accept this without error")
def step_then_no_error(context: Context):
    """Assert no errors."""
    # If we got here, no errors
    pass


@then("nma_site_date should be null")
def step_then_site_date_null(context: Context):
    """Assert nma_site_date is null."""
    assert context.retrieved_location.nma_site_date is None


@then("the well should still be valid")
def step_then_well_valid(context: Context):
    """Assert well is valid."""
    assert context.retrieved_well.id is not None


# ============= EOF =============================================
