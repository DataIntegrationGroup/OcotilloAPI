@ampapi @public_release @business_logic
Feature: Public data release control
  AMPAPI manages sensitive groundwater data for New Mexico and provides controlled
  public access to approved datasets. Data owners and NMBGMR staff control which
  data is released to the public through public release status.

  Background:
    Given the AMPAPI system is operational

  # ---------------------------------------------------------------------------
  # PUBLIC USER ACCESS
  # ---------------------------------------------------------------------------

  @public_access @visibility
  Scenario Outline: Public users can only access data marked for public release
    Given I am a public user (unauthenticated)
    And there is <data_type> data in the system
    When I view <data_type> data through public endpoints
    Then I should only see data marked for public release
    And I should not see any data marked as private
    And I should not see any data with unknown release status

    Examples:
      | data_type                     |
      | location information          |
      | water level measurements      |
      | continuous water level data   |
      | water chemistry results       |

  @public_access @reports
  Scenario: Public release status controls visibility in public reports
    Given there are water level measurements for various locations
    And some measurements are marked for public release
    And some measurements are marked as private
    When a public user generates a hydrograph report
    Then only measurements marked for public release should appear
    And private measurements should be excluded from the report

  @public_access @maps
  Scenario: Public release status controls visibility on web maps
    Given there are monitoring locations throughout New Mexico
    And some locations are marked for public release
    And some locations are marked as private
    When a public user views the interactive web map
    Then only locations marked for public release should be displayed
    And private locations should not appear on the map
    And clicking a public location should show its details

  @public_access @data_download
  Scenario: Public data downloads exclude private data
    Given a public user requests bulk water chemistry data
    And the dataset contains both public and private samples
    When the download is prepared
    Then only samples marked for public release should be included
    And private samples should be automatically filtered out
    And the download should indicate it contains public data only

  # ---------------------------------------------------------------------------
  # AUTHENTICATED STAFF ACCESS
  # ---------------------------------------------------------------------------

  @staff_access @visibility
  Scenario Outline: NMBGMR staff can access all data regardless of release status
    Given I am an authenticated NMBGMR staff member
    When I view <data_type> data through authenticated endpoints
    Then I should see all data including public and private datasets
    And each record should clearly indicate its public release status

    Examples:
      | data_type                     |
      | location information          |
      | water level measurements      |
      | water chemistry results       |

  @staff_access @management
  Scenario: Staff can view and manage private data for internal operations
    Given I am an authenticated NMBGMR staff member
    And there are private water level measurements
    When I access internal data management tools
    Then I can view all private measurements
    And I can analyze trends including private data
    And I can update the public release status of measurements

  # ---------------------------------------------------------------------------
  # DATA SUBMISSION AND RELEASE WORKFLOW
  # ---------------------------------------------------------------------------

  @workflow @data_creation
  Scenario: New location data defaults to appropriate release status
    Given data is being submitted to AMPAPI
    When a new monitoring location is created
    Then the system should require specification of public release status
    And apply a safe default release status based on data source

  @workflow @privacy_protection
  Scenario: Private well owner data is protected by default
    Given a private well owner submits groundwater data
    When the data is entered into the system
    Then the location should be marked as private by default
    And the data should only be visible to NMBGMR staff
    And it remains private until the owner grants permission for public release

  @workflow @public_data
  Scenario: Government-collected data is generally public
    Given NMBGMR field staff collect water level measurements
    When the measurements are entered into AMPAPI
    Then the data should be marked for public release
    And become immediately available to public users

  # ---------------------------------------------------------------------------
  # RELEASE STATUS MANAGEMENT
  # ---------------------------------------------------------------------------

  @management @status_change
  Scenario: Changing release status from private to public
    Given a location is currently marked as private
    And appropriate authorization has been obtained
    When staff changes the release status to public
    Then the location should become visible in public endpoints
    And the location should appear on public web maps
    And all associated data should become publicly accessible

  @management @status_change
  Scenario: Changing release status from public to private
    Given a location is currently marked for public release
    And a data owner requests privacy
    When staff changes the release status to private
    Then the location should be removed from public endpoints
    And the location should disappear from public web maps
    And all associated data should become private

  @management @bulk_operations
  Scenario: Bulk release status changes for project data
    Given a research project has 50 locations marked as private
    And the project has completed and results are approved for release
    When staff performs a bulk status change to public
    Then all 50 locations should become publicly visible
    And all associated measurements should become public

  # ---------------------------------------------------------------------------
  # DATA INTEGRITY AND CONSISTENCY
  # ---------------------------------------------------------------------------

  @integrity @cascading
  Scenario: Location release status affects associated data visibility
    Given a location is marked as private
    And the location has water level measurements
    And the location has water chemistry samples
    When a public user queries for data
    Then all data associated with the private location should be hidden
    And this includes water levels, chemistry, and well construction details

  @integrity @mixed_status
  Scenario: Handling measurements with different release statuses at same location
    Given a location is marked for public release
    But individual measurements can have their own release status
    When a public user views the location's hydrograph
    Then only measurements marked for public release should appear
    And the hydrograph should indicate if some data is excluded

  # ---------------------------------------------------------------------------
  # SPECIAL DATA CATEGORIES
  # ---------------------------------------------------------------------------

  @special_cases @continuous_monitoring
  Scenario: Continuous pressure transducer data is always public
    Given continuous pressure transducer data is being collected
    When the data is processed and loaded into AMPAPI
    Then this data type should always be marked for public release
    And should be immediately available to public users

  @special_cases @confidential_tag
  Scenario: Confidential flag works opposite to public release
    Given a location has both PublicRelease and Confidential indicators
    When PublicRelease is set to true
    Then Confidential should be false
    And vice versa
