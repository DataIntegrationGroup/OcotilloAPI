Feature: Well Completion Date
  As a hydrogeologist
  I want to track when wells were completed/constructed
  So that I can analyze well age and relate construction standards to time periods

  Background:
    Given a functioning api

  Scenario: Create water well with completion date
    When I create a water well with well_completed_on "2004-08-08"
    Then the response should include well_completed_on as "2004-08-08"
    And the response should have thing_type "water well"

  Scenario: Create water well without completion date
    When I create a water well without well_completed_on
    Then the response should include well_completed_on as null
    And the well should be created successfully

  Scenario: Update well to add completion date
    Given a water well exists without well_completed_on
    When I update the well to add well_completed_on "2004-08-08"
    Then the response should include well_completed_on as "2004-08-08"

  Scenario: Update well to change completion date
    Given a water well exists with well_completed_on "2004-08-08"
    When I update the well to change well_completed_on to "2005-03-15"
    Then the response should include well_completed_on as "2005-03-15"

  Scenario: Historical well from 1936
    When I create a water well with well_completed_on "1936-01-01"
    Then the response should include well_completed_on as "1936-01-01"
    And the well age should be over 88 years

  Scenario: Retrieve well with completion date via GET
    Given a water well exists with well_completed_on "2004-08-08"
    When I retrieve the well by ID
    Then the response should include well_completed_on as "2004-08-08"
    And the response should include the well's age in years

  Scenario: List wells includes completion dates
    Given multiple wells exist with various completion dates
    When I retrieve all water wells
    Then each well should include well_completed_on field
    And the field should be null for wells without completion dates

  Scenario: Spring does not have completion date
    When I create a spring
    Then the response should include well_completed_on as null
    And the spring should be created successfully

  Scenario: Filter wells by completion date range
    Given wells exist with completion dates ranging from 1936 to 2024
    When I filter wells completed between "2000-01-01" and "2010-12-31"
    Then the response should only include wells completed in that range
    And wells from 1936 should not be included
    And wells from 2020 should not be included

  Scenario: Well completion date with location legacy dates
    When I create a water well with well_completed_on "2004-08-08"
    And the well's location has legacy_date_created "2014-10-17" and inventoried_on "2013-05-01"
    Then the well should have well_completed_on as "2004-08-08"
    And the location should have legacy_date_created as "2014-10-17"
    And the location should have inventoried_on as "2013-05-01"
    And all three date fields should be independently queryable
