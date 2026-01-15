@admin @ngwmn-well-construction
Feature: NGWMN Well Construction Admin View
  As a data manager who needs legacy NGWMN well construction records
  I need to view NGWMN well construction data in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View NGWMN well construction list with all columns
    Given the following NGWMN well construction records exist:
      | point_id | casing_top | casing_bottom | casing_depth_units |
      | NG-0001  | 10.0       | 50.0          | ft                 |
    When I navigate to "/admin/ngwmnwellconstruction"
    Then I should see the NGWMN well construction list page
    And I should see the following columns:
      | Column Name         |
      | PointID             |
      | CasingTop           |
      | CasingBottom        |
      | CasingDepthUnits    |
      | ScreenTop           |
      | ScreenBottom        |
      | ScreenBottomUnit    |
      | ScreenDescription   |
      | CasingDescription   |
