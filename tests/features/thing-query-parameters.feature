# Created by jakeross at 11/2/25
@backend @BDMS-218 @production
Feature: Thing query paramaters
  Use query parameters to filter things
  Background:
    Given a functioning api
    And the system has valid well and location data in the database

  @positive @happy_path
  Scenario: Filter things by type
    When the user requests things with type "water well"
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And the response should include at least one thing
    And the response should only include things of type "water well"

  @positive @happy_path
  Scenario:
    When the user requests things with type "spring"
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And the response should include at least one thing
    And the response should only include things of type "spring"

