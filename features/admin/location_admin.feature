@admin @location
Feature: Location Admin CRUD Operations
  As a data manager who previously used MS Access
  I need to create, read, update, and delete location records via the web admin interface
  So that I can manage location data without opening an Access database file

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  # ========== List View (MS Access Datasheet Equivalent) ==========

  @smoke @list-view
  Scenario: View location list with default columns
    When I navigate to "/admin/location"
    Then I should see the location list page
    And I should see the following columns:
      | Column Name     |
      | Location ID     |
      | Description     |
      | County          |
      | State           |
      | Elevation       |
      | Quad Name       |
      | Release Status  |
      | Created At      |
      | Updated By      |
    And the list should be sorted by "Created At" descending by default

  @list-view @search
  Scenario: Search locations by description
    Given the following locations exist:
      | description              | county      | state      |
      | Well near Albuquerque    | Bernalillo  | New Mexico |
      | Spring in Santa Fe       | Santa Fe    | New Mexico |
      | Test well in Rio Rancho  | Sandoval    | New Mexico |
    When I navigate to "/admin/location"
    And I enter "Albuquerque" in the search box
    Then I should see 1 location in the results
    And I should see "Well near Albuquerque" in the results
    But I should not see "Spring in Santa Fe" in the results

  @list-view @filter
  Scenario: Filter locations by county
    Given the following locations exist:
      | description     | county      | release_status |
      | Well A          | Bernalillo  | published      |
      | Well B          | Bernalillo  | draft          |
      | Well C          | Santa Fe    | published      |
    When I navigate to "/admin/location"
    And I select "Bernalillo" from the "County" filter
    Then I should see 2 locations in the results
    And I should see "Well A" in the results
    And I should see "Well B" in the results
    But I should not see "Well C" in the results

  @list-view @filter
  Scenario: Filter locations by release status
    Given the following locations exist:
      | description  | release_status |
      | Published 1  | published      |
      | Published 2  | published      |
      | Draft 1      | draft          |
    When I navigate to "/admin/location"
    And I select "published" from the "Release Status" filter
    Then I should see 2 locations in the results
    And I should see "Published 1" in the results
    And I should see "Published 2" in the results
    But I should not see "Draft 1" in the results

  @list-view @sorting
  Scenario: Sort locations by column
    Given the following locations exist:
      | description | elevation |
      | High Point  | 2500.0    |
      | Low Point   | 1200.0    |
      | Mid Point   | 1800.0    |
    When I navigate to "/admin/location"
    And I click the "Elevation" column header
    Then the locations should be sorted by elevation ascending
    And I should see "Low Point" as the first result
    And I should see "High Point" as the last result

  @list-view @pagination
  Scenario: Paginate through location list
    Given 75 locations exist in the database
    When I navigate to "/admin/location"
    Then I should see 50 locations on page 1
    And I should see a "Next" pagination button
    When I click the "Next" button
    Then I should see 25 locations on page 2
    And I should see a "Previous" pagination button

  @list-view @export
  Scenario: Export locations to CSV
    Given the following locations exist:
      | description | county     | elevation |
      | Well 1      | Bernalillo | 1500.0    |
      | Well 2      | Santa Fe   | 2000.0    |
    When I navigate to "/admin/location"
    And I click the "Export" button
    And I select "CSV" as the export format
    Then a CSV file should be downloaded
    And the CSV file should contain 2 data rows plus 1 header row
    And the CSV should include columns: "id,description,county,state,elevation,release_status"

  # ========== Create Operation (MS Access Form Equivalent) ==========

  @smoke @create
  Scenario: Create a new location with valid data
    When I navigate to "/admin/location"
    And I click the "Create" button
    Then I should see the location creation form
    When I fill in the form:
      | Field                | Value                                          |
      | Description          | Test well near Albuquerque                     |
      | Coordinates (WKT)    | POINT(-106.65082 35.08352)                     |
      | Elevation            | 1500.5                                         |
      | County               | Bernalillo                                     |
      | State                | New Mexico                                     |
      | Quad Name            | Albuquerque West                               |
      | Release Status       | draft                                          |
    And I click the "Save" button
    Then I should see a success message "Location created successfully"
    And I should be redirected to the location list
    And I should see "Test well near Albuquerque" in the location list

  @create @validation
  Scenario: Create location fails with invalid WKT format
    When I navigate to "/admin/location/create"
    And I fill in the form:
      | Field              | Value                     |
      | Description        | Invalid coordinates test  |
      | Coordinates (WKT)  | INVALID WKT STRING        |
      | Elevation          | 1500.0                    |
    And I click the "Save" button
    Then I should see a validation error "Invalid WKT geometry"
    And the error should explain "Expected format: POINT(longitude latitude)"
    And the location should not be created

  @create @validation
  Scenario: Create location fails with longitude/latitude reversed
    When I navigate to "/admin/location/create"
    And I fill in the form:
      | Field              | Value                        |
      | Description        | Reversed coordinates test    |
      | Coordinates (WKT)  | POINT(35.08352 -106.65082)   |
      | Elevation          | 1500.0                       |
    And I click the "Save" button
    Then I should see a warning "Are you sure these coordinates are correct? Longitude should be negative for New Mexico."
    # Note: This is a soft validation - staff can override if intentional

  @create @ms-access-migration
  Scenario: WKT field provides help for UTM conversion
    When I navigate to "/admin/location/create"
    And I hover over the "Coordinates (WKT)" field
    Then I should see help text explaining:
      """
      Enter coordinates in WKT (Well-Known Text) format.

      Format: POINT(longitude latitude)
      Example: POINT(-106.65082 35.08352)

      Important:
        " Longitude comes FIRST (negative for western hemisphere)
        " Latitude comes SECOND
        " No comma between values

      If you have UTM coordinates, use an online converter first.
      """

  @create @required-fields
  Scenario: Create location fails with missing required fields
    When I navigate to "/admin/location/create"
    And I click the "Save" button without filling any fields
    Then I should see validation errors:
      | Field              | Error                      |
      | Description        | This field is required     |
      | Coordinates (WKT)  | This field is required     |
      | Elevation          | This field is required     |

  # ========== Read/Detail View ==========

  @read @detail-view
  Scenario: View location details
    Given a location exists with:
      | Field             | Value                          |
      | description       | Test Well ABC                  |
      | point             | POINT(-106.65082 35.08352)     |
      | elevation         | 1500.5                         |
      | county            | Bernalillo                     |
      | state             | New Mexico                     |
      | release_status    | draft                          |
      | nma_pk_location   | 550e8400-e29b-41d4-a716-446655440000 |
    When I navigate to the location detail page
    Then I should see all location fields displayed
    And I should see "POINT(-106.65082 35.08352)" for coordinates
    And I should see "1500.5" for elevation
    And I should see read-only legacy fields:
      | Field                        | Value                                      |
      | AMPAPI Location ID (Legacy)  | 550e8400-e29b-41d4-a716-446655440000       |
      | AMPAPI Date Created (Legacy) | (if populated during migration)            |

  # ========== Update Operation ==========

  @update
  Scenario: Edit an existing location
    Given a location exists with description "Old description"
    When I navigate to the location edit page
    And I update the form:
      | Field        | Value            |
      | Description  | New description  |
    And I click the "Save" button
    Then I should see a success message "Location updated successfully"
    And the location should have description "New description"

  @update @audit
  Scenario: Editing a location updates audit fields
    Given a location exists with description "Test Location"
    And the location was created by "admin@nmbgmr.nmt.edu"
    When I am authenticated as "editor@nmbgmr.nmt.edu" with "Editor" role
    And I navigate to the location edit page
    And I update the description to "Updated Location"
    And I click the "Save" button
    Then the location's "updated_by_name" should be "editor@nmbgmr.nmt.edu"
    And the location's "created_by_name" should still be "admin@nmbgmr.nmt.edu"

  @update @read-only-fields
  Scenario: Legacy migration fields cannot be edited
    Given a location exists with nma_pk_location "550e8400-e29b-41d4-a716-446655440000"
    When I navigate to the location edit page
    Then the "AMPAPI Location ID" field should be read-only
    And the "AMPAPI Date Created" field should be read-only
    And the "AMPAPI Site Date" field should be read-only

  # ========== Delete Operation ==========

  @delete @permissions
  Scenario: Admin can delete a location
    Given a location exists with description "Location to delete"
    And I am authenticated as "admin@nmbgmr.nmt.edu" with "Admin" role
    When I navigate to the location detail page
    And I click the "Delete" button
    Then I should see a confirmation dialog "Are you sure you want to delete this location?"
    When I confirm the deletion
    Then I should see a success message "Location deleted successfully"
    And the location should no longer exist in the database

  @delete @permissions
  Scenario: Editor cannot delete a location
    Given a location exists with description "Location to delete"
    And I am authenticated as "editor@nmbgmr.nmt.edu" with "Editor" role
    When I navigate to the location detail page
    Then I should not see a "Delete" button

  # ========== Bulk Actions (MS Access Update Query Equivalent) ==========

  @bulk-actions @publish
  Scenario: Bulk publish selected locations
    Given the following locations exist:
      | description  | release_status |
      | Location 1   | draft          |
      | Location 2   | draft          |
      | Location 3   | published      |
    And I am authenticated as "admin@nmbgmr.nmt.edu" with "Admin" role
    When I navigate to "/admin/location"
    And I select locations "Location 1" and "Location 2" using checkboxes
    And I select "Publish Selected" from the actions dropdown
    And I click "Execute" button
    Then I should see a confirmation "Are you sure you want to publish the selected locations?"
    When I confirm the action
    Then I should see "Successfully published 2 location(s)"
    And "Location 1" should have release_status "published"
    And "Location 2" should have release_status "published"

  @bulk-actions @unpublish
  Scenario: Bulk unpublish selected locations
    Given the following locations exist:
      | description  | release_status |
      | Location 1   | published      |
      | Location 2   | published      |
    And I am authenticated as "admin@nmbgmr.nmt.edu" with "Admin" role
    When I navigate to "/admin/location"
    And I select locations "Location 1" and "Location 2" using checkboxes
    And I select "Unpublish Selected" from the actions dropdown
    And I click "Execute" button
    Then I should see "Successfully unpublished 2 location(s)"
    And "Location 1" should have release_status "draft"
    And "Location 2" should have release_status "draft"

  @bulk-actions @permissions
  Scenario: Editor cannot perform bulk publish action
    Given the following locations exist:
      | description  | release_status |
      | Location 1   | draft          |
    And I am authenticated as "editor@nmbgmr.nmt.edu" with "Editor" role
    When I navigate to "/admin/location"
    And I select location "Location 1" using checkbox
    And I attempt to execute "Publish Selected" action
    Then I should see an error "Only admins can publish locations"
    And "Location 1" should still have release_status "draft"

  # ========== Data Visibility (Release Status Filtering) ==========

  @data-visibility @viewer
  Scenario: Viewer only sees published locations
    Given the following locations exist:
      | description     | release_status |
      | Public Well     | published      |
      | Draft Well      | draft          |
      | Internal Well   | draft          |
    And I am authenticated as "viewer@nmbgmr.nmt.edu" with "Viewer" role
    When I navigate to "/admin/location"
    Then I should see 1 location in the results
    And I should see "Public Well" in the results
    But I should not see "Draft Well" in the results
    And I should not see "Internal Well" in the results

  @data-visibility @editor
  Scenario: Editor sees all locations (draft and published)
    Given the following locations exist:
      | description     | release_status |
      | Public Well     | published      |
      | Draft Well      | draft          |
    And I am authenticated as "editor@nmbgmr.nmt.edu" with "Editor" role
    When I navigate to "/admin/location"
    Then I should see 2 locations in the results
    And I should see "Public Well" in the results
    And I should see "Draft Well" in the results
