Feature: Add a new well to the Ocotillo inventory
  As a field technician or data manager
  I want to add a new well with location, identifiers, and metadata
  So that the well can be managed, visualized, and linked with related agencies

  Background:
    Given I am logged in as a field technician or data manager
    And I have access to the Ocotillo web UI

  # --- Happy Path ---

  Scenario: Create a new well with all required and optional information
    When I open the "Add New Well" form
    And I set the GPS coordinates of the well
    And I verify that a marker appears on the map at the correct location
    And I enter the elevation or select the option to auto-fill from DEM
    And I select or add associated contacts such as owner or property manager
    And I save the new well
    Then the system should automatically assign a well identifier in the format "NM-01234"
    And the well should appear in the inventory with its details

  # --- Location and Map Verification ---

  Scenario: Enter GPS coordinates and see marker on map
    When I enter coordinates "34.051N, 106.892W"
    Then a marker should appear on the map at that location
    And I should be able to confirm the position is correct

  Scenario: Invalid GPS coordinates
    When I enter coordinates "XYZ"
    And I attempt to save the well
    Then I should receive an error message indicating invalid coordinates
    And the well should not be created

  # --- Elevation Handling ---

  Scenario: Auto-fill elevation from DEM
    When I create a new well and select "Auto-fill elevation"
    Then the elevation field should be populated from the DEM at the GPS location

  Scenario: Manual entry of elevation
    When I enter elevation "5500 ft" manually
    And I save the well
    Then the elevation should be stored with the well record

  # --- Contacts and Ownership ---

  Scenario: Associate contacts with well
    When I add the well and select an owner "Jane Smith"
    And I add a property manager "Joe Farmhand"
    Then these contacts should be linked to the well
    And they should appear in the well’s record

  Scenario: Well with no contacts
    When I create a new well without selecting any contacts
    Then the well should still be created
    And the contacts field should remain empty

  # --- Identifiers ---

  Scenario: Automatically assigned Ocotillo well identifier
    When I save the new well
    Then the system should generate a unique identifier in the format "NM-01234"

  Scenario: Associate external identifiers
    When I create a new well
    And I enter a USGS identifier "USGS-87654"
    And I enter a NMOSE identifier "OSE-44321"
    Then these identifiers should be stored with the well record
    And displayed in the well’s details

  # --- Digital Assets ---

  Scenario: Attach photos to well record
    When I upload a photo of the wellhead
    And I save the well
    Then the photo should be associated with the well record
    And it should be visible in the well’s details

  Scenario: Attach other digital assets
    When I upload a PDF construction log to the well record
    And I save the well
    Then the document should be associated with the well record
    And it should be available for download

  # --- Edge Cases: Well ID Assignment ---

  Scenario: Prevent duplicate well IDs
    Given a well with identifier "NM-01234" already exists
    When I create a new well
    Then the system should assign the next available ID "NM-01235"
    And not allow duplicate identifiers

  Scenario: Enforce well ID format
    When I create a new well
    Then the system should generate an identifier matching the format "NM-#####"
    And any attempt to manually assign an identifier outside this format should be rejected

  # --- Edge Cases: Digital Assets ---

  Scenario: Upload unsupported file type
    When I attempt to upload a file "well_data.exe" to the well record
    Then I should receive an error message indicating the file type is not supported
    And the file should not be stored

  Scenario: Upload fails due to network error
    When I attempt to upload a photo to the well record during connectivity loss
    Then I should see an error message
    And the file should not be attached
    And I should be able to retry once the connection is restored

  Scenario: Upload file exceeds size limit
    When I attempt to upload a file larger than the allowed size
    Then I should receive an error message indicating the file is too large
    And the file should not be uploaded
