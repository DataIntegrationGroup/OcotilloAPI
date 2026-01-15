@admin @surface-water
Feature: Surface Water Admin View
  As a data manager who needs legacy surface water records
  I need to view surface water data in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View surface water list with all columns
    Given the following surface water data records exist:
      | surface_id                          | point_id | object_id | date_measured | discharge | discharge_units |
      | 1f41f8b3-8a0d-41a5-9c83-7f9b3f2b6f2d | SW-0001  | 101       | 2020-07-01    | 15.2      | cfs             |
    When I navigate to "/admin/surfacewaterdata"
    Then I should see the surface water list page
    And I should see the following columns:
      | Column Name         |
      | SurfaceID           |
      | PointID             |
      | OBJECTID            |
      | DateMeasured        |
      | Discharge           |
      | DischargeRate       |
      | DischargeUnits      |
      | DischargeMethod     |
      | DischargeSource     |
      | FormationZone       |
      | AqClass             |
      | SiteNotes           |
      | FieldMethodNotes    |
      | SourceNotes         |
      | DataSource          |
