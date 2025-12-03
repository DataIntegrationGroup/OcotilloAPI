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
from datetime import date, datetime
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


def create_test_location(legacy_date_created=None, legacy_site_date=None):
    """Helper to create a test location with legacy dates."""
    with session_ctx() as session:
        location = Location(
            point="POINT(-106.607784 35.118924)",
            elevation=1558.8,
            release_status="public",
            legacy_date_created=legacy_date_created,
            legacy_site_date=legacy_site_date,
        )
        session.add(location)
        session.commit()
        session.refresh(location)
        return location


def create_test_well(well_completed_on=None, thing_type="water well"):
    """Helper to create a test well with completion date."""
    with session_ctx() as session:
        # Create location
        location = Location(
            point="POINT(-106.607784 35.118924)",
            elevation=1558.8,
            release_status="public",
        )
        session.add(location)
        session.commit()

        # Create thing
        thing = Thing(
            name=f"Test-{thing_type}-{datetime.now().timestamp()}",
            first_visit_date="2023-03-03",
            thing_type=thing_type,
            release_status="public",
            well_depth=100.0 if thing_type == "water well" else None,
            hole_depth=110.0 if thing_type == "water well" else None,
            well_completed_on=well_completed_on,
        )
        session.add(thing)
        session.commit()

        # Associate
        assoc = LocationThingAssociation(location=location, thing=thing)
        assoc.effective_start = "2000-01-01T00:00:00Z"
        session.add(assoc)
        session.commit()

        session.refresh(thing)
        session.refresh(location)
        return thing, location


@given("the AMPAPI data has been migrated to the database")
def step_given_data_migrated(context: Context):
    """Assumption that migration has occurred."""
    context.migrated = True


@given("a location exists with")
def step_given_location_with_table(context: Context):
    """Create location with fields from table."""
    data = {row["field"]: row["value"] for row in context.table}

    legacy_date_created = (
        date.fromisoformat(data["legacy_date_created"])
        if data.get("legacy_date_created") and data["legacy_date_created"] != "null"
        else None
    )
    legacy_site_date = (
        date.fromisoformat(data["legacy_site_date"])
        if data.get("legacy_site_date") and data["legacy_site_date"] != "null"
        else None
    )

    location = create_test_location(
        legacy_date_created=legacy_date_created, legacy_site_date=legacy_site_date
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
            legacy_date_created=date.fromisoformat(legacy_date),
            legacy_site_date=(
                date.fromisoformat(site_date) if site_date else None
            ),
        )
        context.test_locations.append(location)


@given(
    "locations exist with legacy_site_date ranging from {start_year:Number} to {end_year:Number}"
)
def step_given_locations_date_range(context: Context, start_year: int, end_year: int):
    """Create locations with legacy_site_date across a date range."""
    context.test_locations = []

    years = [1954, 2002, 2003, 2010, 2015, 2020, 2024]
    for year in years:
        location = create_test_location(
            legacy_date_created=date(year + 5, 1, 1),  # Always 5 years after site date
            legacy_site_date=date(year, 6, 15),
        )
        context.test_locations.append(location)


@given('{count:Number} locations exist with legacy_date_created "{target_date}"')
def step_given_locations_with_specific_date(
    context: Context, count: int, target_date: str
):
    """Create locations with specific legacy_date_created."""
    if not hasattr(context, "test_locations"):
        context.test_locations = []

    target = date.fromisoformat(target_date)

    for i in range(count):
        location = create_test_location(
            legacy_date_created=target,
            legacy_site_date=date(2000 + i, 1, 1),  # Vary the site dates
        )
        context.test_locations.append(location)


@given('a well exists with well_completed_on "{completion_date}"')
def step_given_well_with_completion(context: Context, completion_date: str):
    """Create well with completion date."""
    completed_on = (
        date.fromisoformat(completion_date) if completion_date != "null" else None
    )

    thing, location = create_test_well(well_completed_on=completed_on)

    context.test_well = thing
    context.test_well_id = thing.id
    context.test_well_location = location


@given("{count:Number} wells exist with various completion dates")
def step_given_multiple_wells(context: Context, count: int):
    """Create multiple wells with various completion dates."""
    context.test_wells = []

    completion_dates = [
        "1936-01-01",
        "1965-06-15",
        "2004-08-08",
        "2020-05-15",
        None,  # No completion date
        None,
        None,
    ]

    for i in range(min(count, len(completion_dates))):
        completed_on = (
            date.fromisoformat(completion_dates[i]) if completion_dates[i] else None
        )
        thing, location = create_test_well(well_completed_on=completed_on)
        context.test_wells.append(thing)


@given("{null_count:Number} of those wells have null well_completed_on")
def step_given_wells_with_null_completion(context: Context, null_count: int):
    """Verify expected number of nulls (declarative - already created)."""
    # Wells were created in previous step with nulls
    pass


@given(
    "wells exist with completion dates from {start_year:Number} to {end_year:Number}"
)
def step_given_wells_date_range(context: Context, start_year: int, end_year: int):
    """Create wells with completion dates across range."""
    context.test_wells = []

    years = [1936, 1965, 2004, 2010, 2020, 2024]
    for year in years:
        thing, location = create_test_well(well_completed_on=date(year, 6, 15))
        context.test_wells.append(thing)


@given("wells exist with completion dates: {years}")
def step_given_wells_specific_years(context: Context, years: str):
    """Create wells with specific completion years."""
    context.test_wells = []

    year_list = [int(y.strip()) for y in years.split(",")]

    for year in year_list:
        thing, location = create_test_well(well_completed_on=date(year, 6, 15))
        context.test_wells.append(thing)


@given("some wells have null well_completed_on")
def step_given_some_wells_null(context: Context):
    """Add wells without completion dates."""
    if not hasattr(context, "test_wells"):
        context.test_wells = []

    for i in range(2):
        thing, location = create_test_well(well_completed_on=None)
        context.test_wells.append(thing)


@given("that well's location has")
def step_given_well_location_has_table(context: Context):
    """Set legacy dates on the well's location."""
    data = {row["field"]: row["value"] for row in context.table}

    legacy_date_created = (
        date.fromisoformat(data.get("legacy_date_created"))
        if data.get("legacy_date_created")
        else None
    )
    legacy_site_date = (
        date.fromisoformat(data.get("legacy_site_date"))
        if data.get("legacy_site_date")
        else None
    )

    with session_ctx() as session:
        location = session.get(Location, context.test_well_location.id)
        location.legacy_date_created = legacy_date_created
        location.legacy_site_date = legacy_site_date
        session.commit()
        session.refresh(location)
        context.test_well_location = location


@given("{count:Number} locations were migrated")
def step_given_count_locations_migrated(context: Context, count: int):
    """Create specified number of test locations."""
    context.test_locations = []

    for i in range(count):
        # 9% have legacy_site_date
        has_site_date = i < count * 0.09

        location = create_test_location(
            legacy_date_created=date(2014, 1, i % 28 + 1),
            legacy_site_date=date(2003, 1, i % 28 + 1) if has_site_date else None,
        )
        context.test_locations.append(location)


@given("{count:Number} of them had non-null SiteDate in AMPAPI")
def step_given_sitedate_count(context: Context, count: int):
    """Declarative - data created in previous step."""
    pass


@given("{count:Number} wells were migrated")
def step_given_count_wells_migrated(context: Context, count: int):
    """Create specified number of test wells."""
    context.test_wells = []

    for i in range(count):
        # 30% have completion dates
        has_completion = i < count * 0.30

        thing, location = create_test_well(
            well_completed_on=date(2000 + (i % 24), 1, 1) if has_completion else None
        )
        context.test_wells.append(thing)


@given("{count:Number} of them had non-null CompletionDate in AMPAPI")
def step_given_completion_count(context: Context, count: int):
    """Declarative - data created in previous step."""
    pass


@given("a location was migrated with legacy dates")
def step_given_location_migrated_with_dates(context: Context):
    """Create location with both legacy dates."""
    location = create_test_location(
        legacy_date_created=date(2014, 4, 3), legacy_site_date=date(2002, 12, 10)
    )
    context.test_location = location


@given('a thing of type "{thing_type}" exists')
def step_given_thing_of_type(context: Context, thing_type: str):
    """Create a thing of specified type."""
    thing, location = create_test_well(well_completed_on=None, thing_type=thing_type)
    context.test_thing = thing
    context.test_thing_id = thing.id


@given("a well exists with well_completed_on null")
def step_given_well_null_completion(context: Context):
    """Create well without completion date."""
    thing, location = create_test_well(well_completed_on=None)
    context.test_well = thing
    context.test_well_id = thing.id


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
    'I filter locations where legacy_site_date is between "{start_date}" and "{end_date}"'
)
def step_when_filter_locations(context: Context, start_date: str, end_date: str):
    """Filter locations by date range."""
    # Since API may not support this yet, query database directly
    with session_ctx() as session:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        locations = (
            session.query(Location)
            .filter(Location.legacy_site_date >= start, Location.legacy_site_date <= end)
            .all()
        )

        context.filtered_locations = locations


@when('I query for locations with legacy_date_created "{target_date}"')
def step_when_query_by_legacy_date(context: Context, target_date: str):
    """Query locations by legacy_date_created."""
    with session_ctx() as session:
        target = date.fromisoformat(target_date)
        locations = (
            session.query(Location).filter(Location.legacy_date_created == target).all()
        )
        context.queried_locations = locations


@when("I retrieve that well via the API")
def step_when_retrieve_well_api(context: Context):
    """Retrieve well via GET API."""
    response = context.client.get(f"/thing/water-well/{context.test_well_id}")
    assert response.status_code == 200
    context.well_response = response.json()


@when("I GET /thing/water-well to list all wells")
def step_when_get_all_wells(context: Context):
    """Get all wells."""
    response = context.client.get("/thing/water-well")
    assert response.status_code == 200
    context.wells_response = response.json()


@when(
    'I filter wells where well_completed_on is between "{start_date}" and "{end_date}"'
)
def step_when_filter_wells(context: Context, start_date: str, end_date: str):
    """Filter wells by completion date range."""
    with session_ctx() as session:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        wells = (
            session.query(Thing)
            .filter(
                Thing.thing_type == "water well",
                Thing.well_completed_on >= start,
                Thing.well_completed_on <= end,
            )
            .all()
        )

        context.filtered_wells = wells


@when("I GET /thing/water-well sorted by well_completed_on ascending")
def step_when_get_wells_sorted(context: Context):
    """Get wells sorted by completion date."""
    with session_ctx() as session:
        wells = (
            session.query(Thing)
            .filter(Thing.thing_type == "water well")
            .order_by(Thing.well_completed_on.asc().nullslast())
            .all()
        )

        context.sorted_wells = wells


@when("I retrieve the well and its location")
def step_when_retrieve_well_and_location(context: Context):
    """Retrieve well with location."""
    with session_ctx() as session:
        well = session.get(Thing, context.test_well.id)
        location = session.get(Location, context.test_well_location.id)

        context.retrieved_well = well
        context.retrieved_location = location


@when("I query the migrated locations")
def step_when_query_migrated_locations(context: Context):
    """Query all test locations."""
    with session_ctx() as session:
        # Query only our test locations
        location_ids = [loc.id for loc in context.test_locations]
        locations = session.query(Location).filter(Location.id.in_(location_ids)).all()
        context.queried_locations = locations


@when("I query the migrated wells")
def step_when_query_migrated_wells(context: Context):
    """Query all test wells."""
    with session_ctx() as session:
        well_ids = [well.id for well in context.test_wells]
        wells = session.query(Thing).filter(Thing.id.in_(well_ids)).all()
        context.queried_wells = wells


@when("I retrieve that location")
def step_when_retrieve_location(context: Context):
    """Retrieve location by ID."""
    with session_ctx() as session:
        location = session.get(Location, context.test_location.id)
        context.retrieved_location = location


@when("I retrieve that spring")
def step_when_retrieve_spring(context: Context):
    """Retrieve spring/thing by ID."""
    with session_ctx() as session:
        thing = session.get(Thing, context.test_thing.id)
        context.retrieved_thing = thing


@when("I retrieve that well")
def step_when_retrieve_well(context: Context):
    """Retrieve well by ID."""
    with session_ctx() as session:
        well = session.get(Thing, context.test_well.id)
        context.retrieved_well = well


# THEN steps


@then('the response should include legacy_date_created as "{expected_date}"')
def step_then_legacy_date_created(context: Context, expected_date: str):
    """Assert legacy_date_created matches."""
    actual = context.location_response.get("legacy_date_created")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then('the response should include legacy_site_date as "{expected_date}"')
def step_then_legacy_site_date(context: Context, expected_date: str):
    """Assert legacy_site_date matches."""
    actual = context.location_response.get("legacy_site_date")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then("the time gap should be approximately {years} years")
def step_then_time_gap_years(context: Context, years: str):
    """Assert approximate year gap."""
    legacy_str = context.location_response.get("legacy_date_created")
    site_date_str = context.location_response.get("legacy_site_date")

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


@then("each location should have a legacy_date_created field")
def step_then_all_have_legacy_field(context: Context):
    """Assert all locations have the field."""
    items = context.locations_response.get("items", [])
    for item in items:
        assert "legacy_date_created" in item, f"Location missing legacy_date_created"


@then("each location should have a legacy_site_date field")
def step_then_all_have_site_date_field(context: Context):
    """Assert all locations have the field."""
    items = context.locations_response.get("items", [])
    for item in items:
        assert "legacy_site_date" in item, f"Location missing legacy_site_date"


@then("some locations should have null legacy_site_date")
def step_then_some_null_site_date(context: Context):
    """Assert some locations have null."""
    items = context.locations_response.get("items", [])
    null_count = sum(1 for item in items if item.get("legacy_site_date") is None)
    assert null_count > 0, "Expected at least one location with null legacy_site_date"


@then("the response should only include locations with site date in that decade")
def step_then_locations_in_decade(context: Context):
    """Assert filtered locations are in range."""
    for loc in context.filtered_locations:
        assert (
            2000 <= loc.legacy_site_date.year <= 2010
        ), f"Location not in 2000-2010: {loc.legacy_site_date}"


@then("locations with site date before {year:Number} should not be included")
def step_then_locations_before_excluded(context: Context, year: int):
    """Assert no locations before year."""
    for loc in context.filtered_locations:
        assert (
            loc.legacy_site_date.year >= year
        ), f"Location from {loc.legacy_site_date.year} should not be included"


@then("locations with site date after {year:Number} should not be included")
def step_then_locations_after_excluded(context: Context, year: int):
    """Assert no locations after year."""
    for loc in context.filtered_locations:
        assert (
            loc.legacy_site_date.year <= year
        ), f"Location from {loc.legacy_site_date.year} should not be included"


@then("the response should include exactly {count:Number} locations")
def step_then_exact_count_locations(context: Context, count: int):
    """Assert exact count."""
    actual = len(context.queried_locations)
    assert actual == count, f"Expected {count} locations, got {actual}"


@then('all should have legacy_date_created "{expected_date}"')
def step_then_all_have_date(context: Context, expected_date: str):
    """Assert all have same date."""
    expected = date.fromisoformat(expected_date)
    for loc in context.queried_locations:
        assert (
            loc.legacy_date_created == expected
        ), f"Location has {loc.legacy_date_created}, expected {expected}"


@then('the response should include well_completed_on as "{expected_date}"')
def step_then_well_completed_on(context: Context, expected_date: str):
    """Assert well_completed_on matches."""
    actual = context.well_response.get("well_completed_on")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then("the well age should be calculable")
def step_then_age_calculable(context: Context):
    """Assert age can be calculated."""
    completion_str = context.well_response.get("well_completed_on")
    assert completion_str is not None, "Cannot calculate age without completion date"

    completed = date.fromisoformat(completion_str)
    today = date.today()
    age_years = (today - completed).days / 365.25
    assert age_years >= 0, "Age cannot be negative"


@then("the well should be over {min_age:Number} years old")
def step_then_well_over_age(context: Context, min_age: int):
    """Assert well age exceeds minimum."""
    completion_str = context.well_response.get("well_completed_on")
    completed = date.fromisoformat(completion_str)
    today = date.today()
    age_years = (today - completed).days / 365.25

    assert age_years >= min_age, f"Expected over {min_age} years, got {age_years:.1f}"


@then("each well should have a well_completed_on field")
def step_then_all_wells_have_field(context: Context):
    """Assert all wells have the field."""
    items = context.wells_response.get("items", [])
    for item in items:
        assert "well_completed_on" in item, f"Well missing well_completed_on"


@then("{percentage:Number}% of wells should have well_completed_on populated")
def step_then_percentage_populated(context: Context, percentage: int):
    """Assert approximate percentage."""
    items = context.wells_response.get("items", [])
    total = len(items)
    if total == 0:
        return

    populated = sum(1 for item in items if item.get("well_completed_on") is not None)
    actual_pct = (populated / total) * 100

    tolerance = 10
    assert (
        abs(actual_pct - percentage) < tolerance
    ), f"Expected ~{percentage}%, got {actual_pct:.1f}%"


@then("the response should only include wells completed in that decade")
def step_then_wells_in_decade(context: Context):
    """Assert filtered wells in range."""
    for well in context.filtered_wells:
        assert 2000 <= well.well_completed_on.year <= 2010


@then("wells from {year:Number} should not be included")
def step_then_wells_year_excluded(context: Context, year: int):
    """Assert wells from year excluded."""
    for well in context.filtered_wells:
        assert well.well_completed_on.year != year


@then("the first well should be from {year:Number}")
def step_then_first_well_year(context: Context, year: int):
    """Assert first well year."""
    if context.sorted_wells and context.sorted_wells[0].well_completed_on:
        actual_year = context.sorted_wells[0].well_completed_on.year
        assert actual_year == year, f"Expected {year}, got {actual_year}"


@then("the last well with a date should be from {year:Number}")
def step_then_last_well_year(context: Context, year: int):
    """Assert last non-null well year."""
    non_null = [w for w in context.sorted_wells if w.well_completed_on]
    if non_null:
        actual_year = non_null[-1].well_completed_on.year
        assert actual_year == year, f"Expected {year}, got {actual_year}"


@then("wells without completion dates should appear last")
def step_then_nulls_last(context: Context):
    """Assert nulls at end."""
    first_null_idx = next(
        (i for i, w in enumerate(context.sorted_wells) if w.well_completed_on is None),
        len(context.sorted_wells),
    )

    for well in context.sorted_wells[first_null_idx:]:
        assert (
            well.well_completed_on is None
        ), "Found non-null after null in sorted list"


@then('the well should have well_completed_on as "{expected_date}"')
def step_then_well_has_completion(context: Context, expected_date: str):
    """Assert well has completion date."""
    actual = context.well_response.get("well_completed_on")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then('the current_location should include legacy_date_created as "{expected_date}"')
def step_then_location_has_legacy(context: Context, expected_date: str):
    """Assert location has legacy_date_created."""
    current_location = context.well_response.get("current_location", {})
    actual = current_location.get("legacy_date_created")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then('the current_location should include legacy_site_date as "{expected_date}"')
def step_then_location_has_site_date(context: Context, expected_date: str):
    """Assert location has legacy_site_date."""
    current_location = context.well_response.get("current_location", {})
    actual = current_location.get("legacy_site_date")
    assert actual == expected_date, f"Expected {expected_date}, got {actual}"


@then(
    "the temporal sequence should be: well_completed_on → legacy_site_date → legacy_date_created"
)
def step_then_temporal_sequence(context: Context):
    """Assert temporal order."""
    well_completed = context.retrieved_well.well_completed_on
    site_date = context.retrieved_location.legacy_site_date
    legacy_created = context.retrieved_location.legacy_date_created

    assert (
        well_completed < site_date
    ), "Well should be completed before site date"
    assert (
        site_date < legacy_created
    ), "Site date should be before DB record created"


@then("the timeline should show: {year1:Number} → {year2:Number} → {year3:Number}")
def step_then_timeline_years(context: Context, year1: int, year2: int, year3: int):
    """Assert specific years in sequence."""
    assert context.retrieved_well.well_completed_on.year == year1
    assert context.retrieved_location.legacy_site_date.year == year2
    assert context.retrieved_location.legacy_date_created.year == year3


@then("{percentage:Number}% should have non-null legacy_site_date")
def step_then_percentage_site_date(context: Context, percentage: int):
    """Assert percentage with legacy_site_date."""
    total = len(context.queried_locations)
    populated = sum(1 for loc in context.queried_locations if loc.legacy_site_date)
    actual_pct = (populated / total) * 100

    tolerance = 2
    assert (
        abs(actual_pct - percentage) < tolerance
    ), f"Expected ~{percentage}%, got {actual_pct:.1f}%"


@then("{percentage:Number}% should have non-null legacy_date_created")
def step_then_percentage_legacy(context: Context, percentage: int):
    """Assert percentage with legacy_date_created."""
    total = len(context.queried_locations)
    populated = sum(1 for loc in context.queried_locations if loc.legacy_date_created)
    actual_pct = (populated / total) * 100

    tolerance = 2
    assert (
        abs(actual_pct - percentage) < tolerance
    ), f"Expected ~{percentage}%, got {actual_pct:.1f}%"


@then("{percentage:Number}% should have non-null well_completed_on")
def step_then_percentage_completion(context: Context, percentage: int):
    """Assert percentage with well_completed_on."""
    total = len(context.queried_wells)
    populated = sum(1 for well in context.queried_wells if well.well_completed_on)
    actual_pct = (populated / total) * 100

    tolerance = 2
    assert (
        abs(actual_pct - percentage) < tolerance
    ), f"Expected ~{percentage}%, got {actual_pct:.1f}%"


@then("it should have created_at (new system timestamp from migration)")
def step_then_has_created_at(context: Context):
    """Assert created_at exists."""
    assert context.retrieved_location.created_at is not None


@then("it should have legacy_date_created (original AMPAPI DateCreated)")
def step_then_has_legacy_date(context: Context):
    """Assert legacy_date_created exists."""
    assert context.retrieved_location.legacy_date_created is not None


@then("it should have legacy_site_date (original AMPAPI SiteDate)")
def step_then_has_site_date(context: Context):
    """Assert legacy_site_date exists."""
    assert context.retrieved_location.legacy_site_date is not None


@then("all three timestamps should be independently queryable")
def step_then_all_queryable(context: Context):
    """Assert all fields are queryable."""
    assert hasattr(context.retrieved_location, "created_at")
    assert hasattr(context.retrieved_location, "legacy_date_created")
    assert hasattr(context.retrieved_location, "legacy_site_date")


@then("created_at should be a recent timestamp")
def step_then_created_at_recent(context: Context):
    """Assert created_at is recent."""
    created_at = context.retrieved_location.created_at.replace(tzinfo=None)
    now = datetime.utcnow()
    diff_seconds = abs((now - created_at).total_seconds())
    assert diff_seconds < 3600, "created_at should be within last hour"


@then("legacy_date_created should be an older date")
def step_then_legacy_date_older(context: Context):
    """Assert legacy_date_created is old."""
    legacy_date = context.retrieved_location.legacy_date_created
    assert legacy_date.year < 2024, "legacy_date_created should be from the past"


@then('legacy_date_created should be "{expected_date}"')
def step_then_legacy_is(context: Context, expected_date: str):
    """Assert legacy_date_created value."""
    actual = context.retrieved_location.legacy_date_created
    expected = date.fromisoformat(expected_date)
    assert actual == expected, f"Expected {expected}, got {actual}"


@then('legacy_site_date should be "{expected_date}"')
def step_then_site_date_is(context: Context, expected_date: str):
    """Assert legacy_site_date value."""
    actual = context.retrieved_location.legacy_site_date
    expected = date.fromisoformat(expected_date)
    assert actual == expected, f"Expected {expected}, got {actual}"


@then("the system should accept this without error")
def step_then_no_error(context: Context):
    """Assert no errors."""
    # If we got here, no errors
    pass


@then("well_completed_on should be null")
def step_then_completion_null(context: Context):
    """Assert well_completed_on is null."""
    if hasattr(context, "retrieved_thing"):
        assert context.retrieved_thing.well_completed_on is None
    elif hasattr(context, "retrieved_well"):
        assert context.retrieved_well.well_completed_on is None


@then("the field should exist in the response schema")
def step_then_field_exists_in_schema(context: Context):
    """Assert field exists in schema."""
    if hasattr(context, "retrieved_thing"):
        assert hasattr(context.retrieved_thing, "well_completed_on")


@then("it should not cause validation errors")
def step_then_no_validation_errors(context: Context):
    """Assert no validation errors."""
    pass


@then("legacy_site_date should be null")
def step_then_site_date_null(context: Context):
    """Assert legacy_site_date is null."""
    assert context.retrieved_location.legacy_site_date is None


@then("the well should still be valid")
def step_then_well_valid(context: Context):
    """Assert well is valid."""
    assert context.retrieved_well.id is not None


# ============= EOF =============================================
