@nmsamplelocations @release_status @business_logic
Feature: Public data visibility control
  NMSampleLocations manages sensitive water data for New Mexico and provides controlled
  public access to approved datasets. Data owners and staff control which data is
  visible to the public through release_status.

  Background:
    Given the NMSampleLocations system is operational

  # ---------------------------------------------------------------------------
  # PUBLIC USER ACCESS
  # ---------------------------------------------------------------------------

  @public_access @visibility
  Scenario Outline: Public users can only access public data
    Given I am a public user (unauthenticated)
    And there is <data_type> data in the system
    When I view <data_type> data through public endpoints
    Then I should only see public data
    And I should not see private data
    And I should not see draft data

    Examples:
      | data_type  |
      | locations  |
      | things     |
      | samples    |
      | observations |

  @public_access @reports
  Scenario: Public reports exclude private data
    Given there are observations for various locations
    And some observations are public
    And some observations are private
    When a public user generates a report
    Then only public observations should appear
    And private observations should be excluded from the report

  @public_access @maps
  Scenario: Web maps show only public locations
    Given there are sample locations throughout New Mexico
    And some locations are public
    And some locations are private
    When a public user views the interactive web map
    Then only public locations should be displayed
    And private locations should not appear on the map
    And clicking a public location should show its details

  @public_access @data_download
  Scenario: Data downloads exclude private data
    Given a public user requests bulk data
    And the dataset contains both public and private records
    When the download is prepared
    Then only public records should be included
    And private records should be automatically filtered out
    And the download should indicate it contains public data only

  # ---------------------------------------------------------------------------
  # AUTHENTICATED STAFF ACCESS
  # ---------------------------------------------------------------------------

  @staff_access @visibility
  Scenario Outline: Staff can access all data regardless of visibility status
    Given I am an authenticated staff member
    When I view <data_type> data through authenticated endpoints
    Then I should see all data including public and private datasets
    And each record should clearly indicate whether it is public or private

    Examples:
      | data_type    |
      | locations    |
      | observations |
      | samples      |

  @staff_access @management
  Scenario: Staff can view and manage private data
    Given I am an authenticated staff member
    And there are private observations
    When I access internal data management tools
    Then I can view all private observations
    And I can analyze data including private records
    And I can change data from private to public

  # ---------------------------------------------------------------------------
  # DATA SUBMISSION AND RELEASE WORKFLOW
  # ---------------------------------------------------------------------------

  @workflow @data_creation
  Scenario: New data defaults to safe visibility status
    Given data is being submitted to the system
    When a new record is created
    Then the system should apply a safe default visibility status
    And the default should protect sensitive data

  @workflow @privacy_protection
  Scenario: Private owner data is protected by default
    Given a private data owner submits data
    When the data is entered into the system
    Then the data should be private by default
    And the data should only be visible to staff
    And it remains private until the owner grants permission for public release

  @workflow @public_data
  Scenario: Government-collected data can be made public
    Given staff collect observation data
    When the observations are entered into the system
    Then staff can mark the data as public
    And it becomes immediately available to public users

  # ---------------------------------------------------------------------------
  # RELEASE STATUS MANAGEMENT
  # ---------------------------------------------------------------------------

  @management @status_change
  Scenario: Making private data public
    Given a location is currently private
    And appropriate authorization has been obtained
    When staff changes the data to public
    Then the location should become visible in public endpoints
    And the location should appear on public web maps
    And all associated data should become publicly accessible

  @management @status_change
  Scenario: Making public data private
    Given a location is currently public
    And a data owner requests privacy
    When staff changes the data to private
    Then the location should be removed from public endpoints
    And the location should disappear from public web maps
    And all associated data should become private

  @management @bulk_operations
  Scenario: Bulk visibility changes for project data
    Given a research project has 50 private locations
    And the project has completed and results are approved for release
    When staff performs a bulk change to make the data public
    Then all 50 locations should become publicly visible
    And all associated observations should become public

  # ---------------------------------------------------------------------------
  # DATA INTEGRITY AND CONSISTENCY
  # ---------------------------------------------------------------------------

  @integrity @cascading
  Scenario: Location visibility affects associated data visibility
    Given a location is private
    And the location has observations
    And the location has samples
    When a public user queries for data
    Then all data associated with the private location should be hidden
    And this includes observations, samples, and thing details

  @integrity @mixed_status
  Scenario: Handling observations with different visibility at same location
    Given a location is public
    But individual observations can have their own visibility status
    When a public user views the location's data
    Then only public observations should appear
    And the display should indicate if some data is excluded

  # ---------------------------------------------------------------------------
  # SPECIAL DATA CATEGORIES
  # ---------------------------------------------------------------------------

  @special_cases @default_public
  Scenario: Certain data types default to public
    Given certain categories of data are configured to be public by default
    When new data of these types is collected
    Then the data should be automatically marked as public
    And should be immediately available to public users

  @special_cases @visibility_consistency
  Scenario: Data visibility is consistently represented
    Given a record has a visibility status
    When the data is viewed through any interface
    Then the visibility status should be clearly indicated
    And public/private status should be unambiguous
