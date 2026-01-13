@admin @chemistry-sample-info
Feature: Chemistry Sample Info Admin View
  As a data manager who needs legacy chemistry records
  I need to view chemistry sample info in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View chemistry sample info list with all columns
    Given the following chemistry sample info records exist:
      | sample_point_id | sample_pt_id | wclab_id | collection_date | sample_type | data_source |
      | NM-0001         | SP-0001      | WC-1001  | 2020-06-15      | groundwater | AMPAPI      |
    When I navigate to "/admin/chemistrysampleinfo"
    Then I should see the chemistry sample info list page
    And I should see the following columns:
      | Column Name               |
      | OBJECTID                  |
      | Thing ID                  |
      | SamplePointID             |
      | SamplePtID                |
      | WCLab ID                  |
      | Collection Date           |
      | Collection Method         |
      | Collected By              |
      | Analyses Agency           |
      | Sample Type               |
      | Sample Material Not H2O   |
      | Water Type                |
      | Study Sample              |
      | Data Source               |
      | Data Quality              |
      | Public Release            |
      | Added Day to Date         |
      | Added Month Day to Date   |
      | Sample Notes              |
