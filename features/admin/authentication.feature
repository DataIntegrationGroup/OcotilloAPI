@admin @authentication
Feature: Admin Authentication and Authorization
  As a data manager transitioning from MS Access
  I need to authenticate and be authorized to use the admin interface
  So that I can manage location data securely via web browser

  Background:
    Given the admin interface is mounted at "/admin"
    And Authentik OIDC authentication is configured

  @smoke
  Scenario: Unauthenticated user is redirected to login
    Given I am not authenticated
    When I navigate to "/admin"
    Then I should be redirected to the Authentik login page
    And the login page should display "Sign in with Authentik"

  @smoke
  Scenario: Authenticated admin user can access admin interface
    Given I am authenticated as user "admin@nmbgmr.nmt.edu"
    And my user has the "Admin" group
    When I navigate to "/admin"
    Then I should see the admin dashboard
    And I should see "Locations" in the sidebar menu
    And I should see my username "admin@nmbgmr.nmt.edu" in the header

  Scenario: Editor user has limited permissions
    Given I am authenticated as user "editor@nmbgmr.nmt.edu"
    And my user has the "Editor" group
    When I navigate to "/admin/location"
    Then I should see the "Create" button
    But I should not see the "Delete" button on any row

  Scenario: Viewer user has read-only access
    Given I am authenticated as user "viewer@nmbgmr.nmt.edu"
    And my user has the "Viewer" group
    When I navigate to "/admin/location"
    Then I should not see the "Create" button
    And I should not see the "Edit" button on any row
    And I should not see the "Delete" button on any row
    And I should only see locations with release_status "published"

  @rbac
  Scenario Outline: Role-based access to location operations
    Given I am authenticated as user "<email>"
    And my user has the "<role>" group
    When I navigate to "/admin/location"
    Then I <can_create> see the "Create" button
    And I <can_edit> see the "Edit" button on rows
    And I <can_delete> see the "Delete" button on rows
    And I <visibility> see draft locations

    Examples:
      | role   | email                  | can_create | can_edit | can_delete | visibility   |
      | Admin  | admin@nmbgmr.nmt.edu   | should     | should   | should     | should       |
      | Editor | editor@nmbgmr.nmt.edu  | should     | should   | should not | should       |
      | Viewer | viewer@nmbgmr.nmt.edu  | should not | should not | should not | should not |

  Scenario: Logout clears session and redirects
    Given I am authenticated as user "admin@nmbgmr.nmt.edu"
    And I am on the admin dashboard at "/admin"
    When I click the "Logout" button
    Then my session token should be cleared
    And I should be redirected to "/"
    And I should not be able to access "/admin" without re-authenticating

  @security
  Scenario: Invalid JWT token is rejected
    Given I have an invalid JWT token
    When I attempt to access "/admin/location"
    Then I should receive a 401 Unauthorized response
    And I should be redirected to the login page

  @security
  Scenario: Expired JWT token requires re-authentication
    Given I am authenticated as user "admin@nmbgmr.nmt.edu"
    And my JWT token has expired
    When I navigate to "/admin/location"
    Then I should be redirected to the Authentik login page
    And I should see a message "Session expired, please log in again"

  @development-mode
  Scenario: Development mode bypasses authentication
    Given the environment variable "AUTHENTIK_DISABLE_AUTHENTICATION" is set to "1"
    And the application mode is "development"
    When I navigate to "/admin/location"
    Then I should see the admin interface without logging in
    And I should have "admin" role by default

  @security
  Scenario: Authentication bypass is blocked in production
    Given the environment variable "AUTHENTIK_DISABLE_AUTHENTICATION" is set to "1"
    And the application mode is "production"
    When I attempt to access "/admin/location"
    Then I should receive a 424 Failed Dependency response
    And I should see an error "Authentication is disabled in production mode"
