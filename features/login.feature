Feature: Ocotillo staging login page
  As a visitor to the staging site
  I want to see the login page when not logged in
  So that I know authentication is required

  Scenario: View login page when not logged in
    When I visit the Ocotillo staging site when not logged in
    Then I should see the login page with body:
      """
      NMBGMR Ocotillo
      Sign in to your account
      Sign in with Authentik
      """
