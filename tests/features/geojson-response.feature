# Created by jakeross at 10/22/25
@backend @production
Feature: Geojson Response
  # Enter feature description here
  Background:
    Given a functioning api
    And the system has valid well and location data in the database

  @positive @happy_path
    Scenario: Request all wells as geojson
      When the user requests all the wells as geojson
      Then the system should return a 200 status code
      And the system should return a response in GEOJSON format
      And the response should be a feature collection
      And the feature collection should have 3 features

  @positive @happy_path
    Scenario: Request all wells in a group as geojson
      When the user requests all the wells for group Collabnet
      Then the system should return a 200 status code
      And the system should return a response in GEOJSON format
      And the response should be a feature collection
      And the feature collection should have 2 features
