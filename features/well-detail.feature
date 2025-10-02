Feature: Well details page in Ocotillo
  As a hydrogeologist or data specialist
  I want to navigate to a well details page by searching for an identifier
  So that I can view hydrographs, maps, measurements, metadata, and associated assets

  Background:
    Given I am logged in as a hydrogeologist or data specialist
    And I am on the Ocotillo web UI

  # --- Happy Path End-to-End ---

  Scenario: View a complete well details page with all data available
    Given I enter a well identifier "NM-01234" in the search bar
    And I select the well from the search results
    When I navigate to the well details page
    Then I should see a hydrograph of historical water level measurements
    And I should be able to expand the hydrograph to full width
    And I should see a small map centered on the well location
    And the map should also display nearby sites within 5, 15, and 50 miles
    And when I hover over a site marker the site name should appear
    And when I click a site marker I should be navigated to that site’s well details page
    And I should see a table of water level measurements with date, method, and observed values
    And I should see a table of water level statistics including min, max, mean, latest, and total measurements
    And I should see a metadata section including well status, project, coordinates, formation, monitoring status, current use, well construction, and a link to OSE PODs
    And I should see an equipment table listing associated instruments
    And I should see a contacts table listing well owner, property manager, or other associated contacts
    And I should see a gallery of associated photos of the well and surroundings
    And I should see a listing of other associated digital assets such as PDFs, logs, or reports

  # --- Navigation ---

  Scenario: Search well by different identifiers
    When I enter "NM-01234" in the search bar
    And I select the well from the search results
    Then I should be navigated to the well details page
    When I enter a USGS identifier "USGS-87654"
    And I select the well
    Then I should be navigated to the same well details page
    When I enter an NMOSE POD identifier "OSE-44321"
    And I select the well
    Then I should be navigated to the same well details page

  Scenario: Well not found
    When I enter "NM-99999" in the search bar
    And I attempt to select it
    Then I should see a message indicating the well could not be found
    And I should not be navigated to a details page

  # --- Hydrograph ---

  Scenario: Hydrograph display and expansion
    Given I am on the well details page
    Then I should see a hydrograph of historical water level measurements
    When I expand the hydrograph to full width
    Then it should resize to fill the available page width

  Scenario: Well with no water level data
    Given a well has no historical water level measurements
    When I view the well details page
    Then the hydrograph section should display a message stating “No water level data available”

  # --- Map ---

  Scenario: Display map with nearby sites
    Given I am on the well details page
    Then I should see a small map centered on the well’s location
    And the map should also show sites within 5, 15, and 50 miles
    When I hover over a site marker
    Then the site name should be displayed
    When I click on a site marker
    Then I should be navigated to that site’s well details page

  Scenario: No nearby sites on map
    Given the well has no nearby sites within 50 miles
    When I view the well details page
    Then the map should still display the well location marker
    And it should show a message stating “No nearby sites”

  # --- Water Level Measurements ---

  Scenario: Water level measurements table
    Given I am on the well details page
    Then I should see a table of water level measurements
    And the table should include date, method, and observed values

  Scenario: No water level measurements in table
    Given a well has no measurements stored
    When I view the well details page
    Then the water level table should be empty
    And a message should state “No measurements available”

  # --- Metadata Section ---

  Scenario: Metadata display
    Given I am on the well details page
    Then I should see a metadata section including:
      | Field             |
      | Well status       |
      | Project           |
      | Coordinates       |
      | Formation         |
      | Monitoring status |
      | Current use       |
      | Well construction |
      | Link to OSE PODs  |

  Scenario: Missing metadata fields
    Given some metadata fields are not available for the well
    When I view the metadata section
    Then unavailable fields should be clearly marked as “Not available”
    And available fields should still display normally

  # --- Equipment and Contacts ---

  Scenario: Equipment table
    Given I am on the well details page
    Then I should see an equipment table listing any associated instruments

  Scenario: No equipment associated
    Given the well has no associated equipment
    When I view the well details page
    Then the equipment table should state “No equipment listed”

  Scenario: Contacts table
    Given I am on the well details page
    Then I should see a contacts table listing owner, property manager, or other associated contacts

  Scenario: No contacts associated
    Given the well has no associated contacts
    When I view the well details page
    Then the contacts table should state “No contacts listed”

  # --- Photos and Assets ---

  Scenario: Well gallery
    Given I am on the well details page
    Then I should see a gallery of associated photos of the well and surroundings

  Scenario: No photos available
    Given the well has no associated photos
    When I view the well details page
    Then the gallery section should state “No photos available”

  Scenario: Other digital assets
    Given I am on the well details page
    Then I should see a listing of associated digital assets (e.g., PDFs, logs, reports)

  Scenario: No digital assets
    Given the well has no associated digital assets
    When I view the well details page
    Then the digital assets section should state “No assets available”
