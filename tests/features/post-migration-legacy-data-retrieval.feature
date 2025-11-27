Feature: Post-Migration Legacy Data Retrieval
  As a data manager
  After migrating data from AMPAPI to NMSampleLocations
  I want to verify that all legacy temporal information is preserved and queryable
  So that no historical context is lost

  Background:
    Given a functioning api
    And the AMPAPI data has been migrated to the database

  # Location Legacy Date Lookups

  Scenario: Retrieve location with both legacy dates via API
    Given a location exists with:
      | field                | value      |
      | legacy_date_created  | 2014-04-03 |
      | legacy_site_date     | 2002-12-10 |
    When I retrieve that location via the API
    Then the response should include legacy_date_created as "2014-04-03"
    And the response should include legacy_site_date as "2002-12-10"
    And the time gap should be approximately 11.3 years

  Scenario: Retrieve location with large time gap (54 years)
    Given a location exists with:
      | field                | value      |
      | legacy_date_created  | 2008-05-28 |
      | legacy_site_date     | 1954-05-01 |
    When I retrieve that location via the API
    Then the response should include legacy_date_created as "2008-05-28"
    And the response should include legacy_site_date as "1954-05-01"
    And the time gap should be approximately 54 years

  Scenario: List all locations includes legacy date fields
    Given 5 locations exist with various legacy dates
    When I GET /location to list all locations
    Then each location should have a legacy_date_created field
    And each location should have a legacy_site_date field
    And some locations should have null legacy_site_date

  Scenario: Filter locations by legacy site date range
    Given locations exist with legacy_site_date ranging from 1950 to 2024
    When I filter locations where legacy_site_date is between "2000-01-01" and "2010-12-31"
    Then the response should only include locations with legacy_site_date in that decade
    And locations with legacy_site_date before 2000 should not be included
    And locations with legacy_site_date after 2010 should not be included

  Scenario: Query location by legacy_date_created
    Given 3 locations exist with legacy_date_created "2014-04-03"
    And 2 locations exist with legacy_date_created "2017-12-06"
    When I query for locations with legacy_date_created "2014-04-03"
    Then the response should include exactly 3 locations
    And all should have legacy_date_created "2014-04-03"

  # Well Completion Date Lookups

  Scenario: Retrieve well with completion date via API
    Given a well exists with well_completed_on "2004-08-08"
    When I retrieve that well via the API
    Then the response should include well_completed_on as "2004-08-08"
    And the well age should be calculable

  Scenario: Retrieve old well from early 1900s
    Given a well exists with well_completed_on "1936-01-01"
    When I retrieve that well via the API
    Then the response should include well_completed_on as "1936-01-01"
    And the well should be over 88 years old

  Scenario: List all wells includes completion date field
    Given 10 wells exist with various completion dates
    And 3 of those wells have null well_completed_on
    When I GET /thing/water-well to list all wells
    Then each well should have a well_completed_on field
    And 70% of wells should have well_completed_on populated

  Scenario: Filter wells by completion date range
    Given wells exist with completion dates from 1936 to 2024
    When I filter wells where well_completed_on is between "2000-01-01" and "2010-12-31"
    Then the response should only include wells completed in that decade
    And wells from 1936 should not be included
    And wells from 2020 should not be included

  Scenario: Sort wells by completion date (oldest first)
    Given wells exist with completion dates: 1936, 1965, 2004, 2020
    And some wells have null well_completed_on
    When I GET /thing/water-well sorted by well_completed_on ascending
    Then the first well should be from 1936
    And the last well with a date should be from 2020
    And wells without completion dates should appear last

  # Combined Queries - Location + Well Legacy Dates

  Scenario: Retrieve well with location showing all legacy dates
    Given a well exists with well_completed_on "2004-08-08"
    And that well's location has:
      | field                | value      |
      | legacy_date_created  | 2014-04-03 |
      | legacy_site_date     | 2002-12-10 |
    When I retrieve the well via the API
    Then the well should have well_completed_on as "2004-08-08"
    And the current_location should include legacy_date_created as "2014-04-03"
    And the current_location should include legacy_site_date as "2002-12-10"

  Scenario: Timeline reconstruction - well completed before site inventoried
    Given a well exists with well_completed_on "1995-06-15"
    And that well's location has:
      | field                | value      |
      | legacy_site_date     | 2003-12-10 |
      | legacy_date_created  | 2014-04-03 |
    When I retrieve the well and its location
    Then the temporal sequence should be: well_completed_on → legacy_site_date → legacy_date_created
    And the timeline should show: 1995 → 2003 → 2014

  # Data Quality Validation

  Scenario: Verify migration preserved expected percentage of legacy dates
    Given 100 locations were migrated
    And 9 of them had non-null SiteDate in AMPAPI
    When I query the migrated locations
    Then 9% should have non-null legacy_site_date
    And 100% should have non-null legacy_date_created

  Scenario: Verify well completion date coverage matches expectation
    Given 100 wells were migrated
    And 30 of them had non-null CompletionDate in AMPAPI
    When I query the migrated wells
    Then 30% should have non-null well_completed_on

  # Audit Trail Verification

  Scenario: Legacy dates preserved alongside audit timestamps
    Given a location was migrated with legacy dates
    When I retrieve that location
    Then it should have created_at (new system timestamp from migration)
    And it should have legacy_date_created (original AMPAPI DateCreated)
    And it should have legacy_site_date (original AMPAPI SiteDate)
    And all three timestamps should be independently queryable
    And created_at should be a recent timestamp
    And legacy_date_created should be an older date

  # Edge Cases

  Scenario: Location where SiteDate is later than DateCreated (data anomaly)
    Given a location exists with:
      | field                | value      |
      | legacy_date_created  | 2010-01-15 |
      | legacy_site_date     | 2015-06-20 |
    When I retrieve that location
    Then legacy_date_created should be "2010-01-15"
    And legacy_site_date should be "2015-06-20"
    And the system should accept this without error

  Scenario: Spring does not use well_completed_on field
    Given a thing of type "spring" exists
    When I retrieve that spring
    Then well_completed_on should be null
    And the field should exist in the response schema
    And it should not cause validation errors

  Scenario: Location with only legacy_date_created (no legacy_site_date)
    Given a location exists with:
      | field                | value      |
      | legacy_date_created  | 2014-10-17 |
      | legacy_site_date     | null       |
    When I retrieve that location
    Then legacy_date_created should be "2014-10-17"
    And legacy_site_date should be null

  Scenario: Well without completion date
    Given a well exists with well_completed_on null
    When I retrieve that well
    Then well_completed_on should be null
    And the well should still be valid
