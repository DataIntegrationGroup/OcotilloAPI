@admin @hydraulics-data
Feature: Hydraulics Data Admin View
  As a data manager who needs legacy hydraulics records
  I need to view hydraulics data in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View hydraulics data list with all columns
    Given the following hydraulics data records exist:
      | global_id                            | point_id | thing_id | hydraulic_unit | test_top | test_bottom | t_ft2_d | data_source |
      | 550e8400-e29b-41d4-a716-446655440000 | NM-0001  | 1        | HU-1           | 10       | 50          | 123.4   | AMPAPI      |
    When I navigate to "/admin/hydraulicsdata"
    Then I should see the hydraulics data list page
    And I should see the following columns:
      | Column Name         |
      | GlobalID            |
      | WellID              |
      | PointID             |
      | Thing ID            |
      | HydraulicUnit       |
      | HydraulicUnitType   |
      | TestTop             |
      | TestBottom          |
      | T (ft2/d)           |
      | k (darcy)           |
      | Data Source         |
      | OBJECTID            |
