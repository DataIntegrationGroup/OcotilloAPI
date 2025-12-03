Feature: Post-Migration AMPAPI Date Field Retrieval
  As a data manager
  After migrating data from AMPAPI to NMSampleLocations
  I want to verify that all AMPAPI temporal information is preserved and queryable
  So that no historical context is lost

  Background:
    Given a functioning api
    And the AMPAPI data has been migrated to the database

  # Location AMPAPI Date Lookups (Read-Only Fields)

  Scenario: Retrieve location with both AMPAPI date fields via API
    Given a location exists with:
      | field                | value      |
      | nma_date_created  | 2014-04-03 |
      | nma_site_date     | 2002-12-10 |
    When I retrieve that location via the API
    Then the response should include nma_date_created as "2014-04-03"
    And the response should include nma_site_date as "2002-12-10"
    And the time gap should be approximately 11.3 years

  Scenario: Retrieve location with large time gap (54 years)
    Given a location exists with:
      | field                | value      |
      | nma_date_created  | 2008-05-28 |
      | nma_site_date     | 1954-05-01 |
    When I retrieve that location via the API
    Then the response should include nma_date_created as "2008-05-28"
    And the response should include nma_site_date as "1954-05-01"
    And the time gap should be approximately 54 years

  Scenario: List all locations includes AMPAPI date fields
    Given 5 locations exist with various AMPAPI dates
    When I GET /location to list all locations
    Then each location should have a date created field
    And each location should have a site date field
    And some locations should have null site date

  Scenario: Filter locations by AMPAPI site date range
    Given locations exist with nma_site_date ranging from 1950 to 2024
    When I filter locations where nma_site_date is between "2000-01-01" and "2010-12-31"
    Then the response should only include locations with site date in that decade
    And locations with site date before 2000 should not be included
    And locations with site date after 2010 should not be included

  Scenario: Query location by nma_date_created
    Given 3 locations exist with nma_date_created "2014-04-03"
    And 2 locations exist with nma_date_created "2017-12-06"
    When I query for locations with nma_date_created "2014-04-03"
    Then the response should include exactly 3 locations
    And all should have nma_date_created "2014-04-03"

  # Data Quality Validation

  Scenario: Verify migration preserved expected percentage of AMPAPI dates
    Given 100 locations were migrated
    And 9 of them had non-null SiteDate in AMPAPI
    When I query the migrated locations
    Then 9% should have non-null nma_site_date
    And 100% should have non-null nma_date_created

  # Audit Trail Verification

  Scenario: AMPAPI dates preserved alongside audit timestamps
    Given a location was migrated with AMPAPI dates
    When I retrieve that location
    Then it should have created_at (new system timestamp from migration)
    And it should have nma_date_created (original AMPAPI DateCreated)
    And it should have nma_site_date (original AMPAPI SiteDate)
    And all three timestamps should be independently queryable
    And created_at should be a recent timestamp
    And nma_date_created should be an older date

  # Edge Cases

  Scenario: Location where SiteDate is later than DateCreated (data anomaly)
    Given a location exists with:
      | field                | value      |
      | nma_date_created  | 2010-01-15 |
      | nma_site_date     | 2015-06-20 |
    When I retrieve that location
    Then nma_date_created should be "2010-01-15"
    And nma_site_date should be "2015-06-20"
    And the system should accept this without error

  Scenario: Location with only nma_date_created (no nma_site_date)
    Given a location exists with:
      | field                | value      |
      | nma_date_created  | 2014-10-17 |
      | nma_site_date     | null       |
    When I retrieve that location
    Then nma_date_created should be "2014-10-17"
    And nma_site_date should be null
