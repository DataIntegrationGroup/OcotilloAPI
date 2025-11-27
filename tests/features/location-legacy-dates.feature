Feature: Location Legacy Date Fields
  As a data manager
  I want to preserve legacy date information from the AMPAPI system
  So that historical temporal context is not lost during migration

  Background:
    Given a functioning api

  Scenario: Create location with both legacy dates
    When I create a location with legacy_date_created "2014-10-17" and inventoried_on "2003-12-10"
    Then the response should include legacy_date_created as "2014-10-17"
    And the response should include inventoried_on as "2003-12-10"
    And the created_at timestamp should be the current system time
    And the time gap between inventoried_on and legacy_date_created should be preserved

  Scenario: Create location with only legacy_date_created
    When I create a location with legacy_date_created "2014-10-17"
    Then the response should include legacy_date_created as "2014-10-17"
    And the response should include inventoried_on as null
    And the created_at timestamp should be the current system time

  Scenario: Create location with only inventoried_on
    When I create a location with inventoried_on "2003-12-10"
    Then the response should include inventoried_on as "2003-12-10"
    And the response should include legacy_date_created as null
    And the created_at timestamp should be the current system time

  Scenario: Create location with neither legacy date
    When I create a location without legacy dates
    Then the response should include legacy_date_created as null
    And the response should include inventoried_on as null
    And the created_at timestamp should be the current system time

  Scenario: Update location legacy dates
    Given a location exists with legacy_date_created "2014-10-17"
    When I update the location to add inventoried_on "2003-12-10"
    Then the response should include legacy_date_created as "2014-10-17"
    And the response should include inventoried_on as "2003-12-10"

  Scenario: Retrieve location with legacy dates via GET
    Given a location exists with legacy_date_created "2014-10-17" and inventoried_on "2003-12-10"
    When I retrieve the location by ID
    Then the response should include legacy_date_created as "2014-10-17"
    And the response should include inventoried_on as "2003-12-10"

  Scenario: Historical data preservation - 54 year gap (Site SM-0227)
    When I create a location with legacy_date_created "2008-05-28" and inventoried_on "1954-05-01"
    Then the response should include legacy_date_created as "2008-05-28"
    And the response should include inventoried_on as "1954-05-01"
    And the time gap should be approximately 19751 days

  Scenario: List locations includes legacy dates
    Given multiple locations exist with various legacy dates
    When I retrieve all locations
    Then each location should include legacy_date_created field
    And each location should include inventoried_on field
    And the fields should be null for locations without legacy dates
