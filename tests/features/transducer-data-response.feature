# Created by jakeross at 11/4/25
@backend @production
Feature: Transducer Data Response
  This feature tests the API's ability to retrieve transducer data for wells.
    Background:
        Given a functioning api
        And the system has valid well and transducer data in the database

    @positive @happy_path
    Scenario: Retrieve transducer data for an existing well
      When the user requests transducer data for a well
      Then the system should return a 200 status code
      And the system should return a response in JSON format

      And the response should be paginated
      And each page should be an array of transducer data
      And each transducer data entry should include a timestamp, value, status
      And the timestamp should be in ISO 8601 format
      And the value should be a numeric type
      And the status should be one of "approved", "not reviewed"



    @negative @sad_path
    Scenario: Retrieve transducer data for a non-existing well
      When the user requests transducer data for a non-existing well
      Then the system should return a 200 status code
      And the system should return a response in JSON format
      And the response should be paginated
      And the items should be an empty list