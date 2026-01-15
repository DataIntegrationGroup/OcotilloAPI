@admin @ngwmn-lithology
Feature: NGWMN Lithology Admin View
  As a data manager who needs legacy NGWMN lithology records
  I need to view NGWMN lithology data in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View NGWMN lithology list with all columns
    Given the following NGWMN lithology records exist:
      | object_id | point_id | lithology | term           |
      | 301       | NG-0003  | Sand      | Santa Fe Group |
    When I navigate to "/admin/ngwmnlithology"
    Then I should see the NGWMN lithology list page
    And I should see the following columns:
      | Column Name     |
      | OBJECTID        |
      | PointID         |
      | Lithology       |
      | TERM            |
      | StratSource     |
      | StratTop        |
      | StratTopUnit    |
      | StratBottom     |
      | StratBottomUnit |
