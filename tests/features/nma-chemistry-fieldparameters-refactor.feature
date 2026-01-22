@backend @migration @chemistry
Feature: Refactor legacy FieldParameters into the Ocotillo schema via backfill job
  As an Ocotillo database engineer
  I want a repeatable backfill job to refactor legacy FieldParameters into the new schema
  So that field chemistry measurements are migrated with auditability and idempotence

  Background:
    Given a database session is available
    And legacy NMA_FieldParameters records exist in the database
    And lexicon terms exist for parameter_name, unit, note_type "Chemistry Observation", and sample_matrix "water"

  @backfill @idempotent
  Scenario: Backfill creates Observation records and can be re-run without duplicates
    Given a legacy NMA_FieldParameters record exists with:
      | field          | value                               |
      | GlobalID       | 6f8a6b2c-2a6c-4b74-8a7b-2f09fcbfef10 |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | FieldParameter | pH                                  |
      | SampleValue    | 7.42                                |
      | Units          | null                                |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Field Parameters backfill job
    Then exactly 1 Observation record should exist with nma_pk_chemistryresults "6f8a6b2c-2a6c-4b74-8a7b-2f09fcbfef10"
    And the Observation should reference the Sample with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Observation should set value to 7.42
    And the Observation should set unit to null
    And a Parameter record should exist with parameter_name "pH" and matrix "water"
    And the Observation should reference the Parameter with parameter_name "pH" and matrix "water"
    When I run the Field Parameters backfill job again
    Then exactly 1 Observation record should exist with nma_pk_chemistryresults "6f8a6b2c-2a6c-4b74-8a7b-2f09fcbfef10"

  @backfill @linkage
  Scenario: Observations are not orphaned and link to Sample (and Thing) by SamplePtID
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                               |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000 |
      | SamplePointID| AB-0186A                            |
    And a legacy NMA_FieldParameters record exists with:
      | field          | value                               |
      | GlobalID       | 3c13c4f0-2a6c-4aa3-9d0b-1a6a8f7f9b33 |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | FieldParameter | Temperature                         |
      | SampleValue    | 18.6                                |
      | Units          | deg C                               |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Field Parameters backfill job
    Then the Observation for GlobalID "3c13c4f0-2a6c-4aa3-9d0b-1a6a8f7f9b33" should reference the Sample with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Observation for GlobalID "3c13c4f0-2a6c-4aa3-9d0b-1a6a8f7f9b33" should reference the Thing associated with that Sample

  @backfill @notes
  Scenario: Notes are stored in the Notes table and linked to the Observation
    Given a legacy NMA_FieldParameters record exists with:
      | field          | value                               |
      | GlobalID       | 6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74 |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | FieldParameter | Conductivity                        |
      | Notes          | field meter calibration drift       |
      | SampleValue    | 425                                 |
      | Units          | uS/cm                               |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Field Parameters backfill job
    Then a Parameter record should exist with parameter_name "Conductivity" and matrix "water"
    And the Observation for GlobalID "6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74" should reference the Parameter with parameter_name "Conductivity" and matrix "water"
    And a Notes record should exist with:
      | field        | value   |
      | target_table | observation |
      | target_id    | (observation.id for GlobalID 6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74) |
      | note_type    | Chemistry Observation |
      | content      | field meter calibration drift |

  @backfill @ignore
  Scenario: Unmapped legacy fields are not persisted in the new schema
    Given a legacy NMA_FieldParameters record exists with:
      | field        | value                               |
      | GlobalID     | 8f1e6dcb-9a5d-4b9c-9bf0-9b7c3f2b6b62 |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000 |
      | SamplePointID| AB-0186A                            |
      | OBJECTID     | 9012                                |
      | WCLab_ID     | LAB-98765                           |
      | AnalysesAgency | NMBGMR                            |
      | SSMA_Timestamp | 2025-01-01T00:00:00Z              |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Field Parameters backfill job
    Then the Observation for GlobalID "8f1e6dcb-9a5d-4b9c-9bf0-9b7c3f2b6b62" should not store SamplePointID, OBJECTID, WCLab_ID, AnalysesAgency, or SSMA_Timestamp

  @backfill @orphan-prevention
  Scenario: Orphan legacy records are skipped and reported
    Given a legacy NMA_FieldParameters record exists with:
      | field      | value                               |
      | GlobalID   | 02b8a58c-9a7e-44e0-9e9f-9b26f2b8c71f |
      | SamplePtID | 319c1256-1237-4e17-b93e-03ad8a7789d6 |
      | FieldParameter | Nitrate                          |
      | SampleValue| 1.2                                 |
      | Units      | mg/L                                |
    When I run the Field Parameters backfill job
    Then no Observation record should exist with nma_pk_chemistryresults "02b8a58c-9a7e-44e0-9e9f-9b26f2b8c71f"
    And the backfill job should report 1 skipped record due to missing Sample linkage (SamplePtID)
