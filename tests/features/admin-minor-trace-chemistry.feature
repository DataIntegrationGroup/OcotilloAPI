@backend @admin
Feature: Minor Trace Chemistry Admin View
  As an administrator
  I want to view Minor Trace Chemistry data in the admin interface
  So that I can browse and manage legacy chemistry results

  @positive
  Scenario: Minor Trace Chemistry view is registered in admin
    Given a functioning api
    When I check the registered admin views
    Then "Minor Trace Chemistry" should be in the list of admin views

  @positive
  Scenario: Minor Trace Chemistry view is read-only
    Given a functioning api
    Then the Minor Trace Chemistry admin view should not allow create
    And the Minor Trace Chemistry admin view should not allow edit
    And the Minor Trace Chemistry admin view should not allow delete

  @positive
  Scenario: Minor Trace Chemistry details page loads
    Given a functioning api
    When I request the Minor Trace Chemistry admin list page
    Then the response status should be 200
    When I request the Minor Trace Chemistry admin detail page for an existing record
    Then the response status should be 200

  @positive
  Scenario: Minor Trace Chemistry detail page shows expected fields
    Given a functioning api
    Then the Minor Trace Chemistry admin view should have these fields configured:
      | field                     |
      | global_id                 |
      | sample_pt_id              |
      | analyte                   |
      | symbol                    |
      | sample_value              |
      | units                     |
      | uncertainty               |
      | analysis_method           |
      | analysis_date             |
      | notes                     |
      | volume                    |
      | volume_unit               |
      | analyses_agency           |
