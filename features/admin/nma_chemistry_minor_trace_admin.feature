@admin @minor-trace-chemistry
Feature: Minor and Trace Chemistry Admin View
  As a data manager who needs legacy chemistry details
  I need to view minor and trace chemistry records in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View minor and trace chemistry list with all columns
    Given the following minor and trace chemistry records exist:
      | sample_pt_id | sample_point_id | analyte | sample_value | units | analysis_date |
      | 1001         | NM-0001         | As      | 0.004        | mg/L  | 2020-06-20    |
    When I navigate to "/admin/minortracechemistry"
    Then I should see the minor and trace chemistry list page
    And I should see the following columns:
      | Column Name     |
      | GlobalID        |
      | ObjectID        |
      | SamplePtID      |
      | SamplePointID   |
      | Analyte         |
      | Symbol          |
      | SampleValue     |
      | Units           |
      | Uncertainty     |
      | AnalysisMethod  |
      | AnalysisDate    |
      | Notes           |
      | Volume          |
      | VolumeUnit      |
