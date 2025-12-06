# Created by jakeross at 10/21/25
@backend @BDMS-199
Feature: Retrieve sensor notes
  As a user
    I want to retrieve sensor notes for a given well name
    So that I can view important information about the well's deployed sensors
    Background:
      Given a functioning api
      And the system has valid well and location data in the database

#  @positive @happy_path
#  Scenario: Request sensor notes for an existing well
#    When the user requests the sensor for well 1
#    Then the system should return a 200 status code
#    And the system should return a response in JSON format
#    And the response should include notes
#    And the notes should be a non-empty string

  @positive
  Scenario: Request sensor notes by sensor ID
    When the user requests the sensor with ID 1
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And the response should include notes
    And the notes should be a non-empty string

  @negative
  Scenario: Request sensor notes for a non-existing sensor ID
    When the user requests the sensor with ID 9999
    Then the system should return a 404 status code
    And the system should return a response in JSON format
    And the response should include an error message indicating the sensor was not found

#  @negative @sad_path
#  Scenario: Request sensor notes for a non-existing well
#    When the user requests the sensor for well 9999
#    Then the system should return a 404 status code
#    And the system should return a response in JSON format
#    And the response should include an error message indicating the well was not found