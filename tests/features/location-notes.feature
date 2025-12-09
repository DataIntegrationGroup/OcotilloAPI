# Created by jakeross at 10/21/25
@backend @BDMS-199 @production
Feature: Retrieve location notes by well name
  As a user
  I want to retrieve location notes for a given well name
  So that I can view important information about the well's location
  Background:
    Given a functioning api
    And the system has valid well and location data in the database

  @positive @happy_path
  Scenario: Retrieve location notes for an existing well
    When the user retrieves the well by ID via path parameter
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And the response should include a current location
    And the current location should include notes
    And the notes should be a list of dictionaries
    And each note dictionary should have "content" and "note_type" keys
    And each note in the notes list should be a non-empty string

  @positive @happy_path
  Scenario: Retrieve location notes by location ID
    When the user retrieves the location by ID via path parameter
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And the location response should include notes
    And the notes should be a list of dictionaries
    And each note dictionary should have "content" and "note_type" keys
    And each note in the notes list should be a non-empty string
