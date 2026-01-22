@backend @migration @chemistry
Feature: Refactor legacy MajorChemistry into the Ocotillo schema via backfill job
  As an Ocotillo database engineer
  I want a repeatable backfill job to refactor legacy MajorChemistry into the new schema
  So that chemistry results are migrated with auditability and idempotence

  Background:
    Given a database session is available
    And legacy NMA_MajorChemistry records exist in the database
    And lexicon terms exist for parameter_name, unit, analysis_method_type, and sample_matrix "water"

  @backfill @idempotent
  Scenario: Backfill creates Observation records and can be re-run without duplicates
    Given a legacy NMA_MajorChemistry record exists with:
      | field          | value                               |
      | GlobalID       | 6f8a6b2c-2a6c-4b74-8a7b-2f09fcbfef10 |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte        | Calcium                             |
      | SampleValue    | 45.6                                |
      | Units          | mg/L                                |
      | AnalysisDate   | 2001-06-26                           |
      | AnalysisMethod | EPA 200.7                            |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then exactly 1 Observation record should exist with nma_pk_chemistryresults "6f8a6b2c-2a6c-4b74-8a7b-2f09fcbfef10"
    And the Observation should reference the Sample with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Observation should set observation_datetime to "2001-06-26"
    And the Observation should set value to 45.6
    And the Observation should set unit to "mg/L"
    And the Observation should set parameter_name to "Calcium"
    And the Observation should set analysis_method_name to "EPA 200.7"
    When I run the Major Chemistry backfill job again
    Then exactly 1 Observation record should exist with nma_pk_chemistryresults "6f8a6b2c-2a6c-4b74-8a7b-2f09fcbfef10"

  @backfill @linkage
  Scenario: Observations are not orphaned and link to Sample (and Thing) by SamplePtID
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                               |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000 |
      | SamplePointID| AB-0186A                            |
    And a legacy NMA_MajorChemistry record exists with:
      | field       | value                               |
      | GlobalID    | 3c13c4f0-2a2c-4aa3-9d0b-1a6a8f7f9b33 |
      | SamplePtID  | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte     | Magnesium                           |
      | SampleValue | 14.2                                |
      | Units       | mg/L                                |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then the Observation for GlobalID "3c13c4f0-2a2c-4aa3-9d0b-1a6a8f7f9b33" should reference the Sample with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Observation for GlobalID "3c13c4f0-2a2c-4aa3-9d0b-1a6a8f7f9b33" should reference the Thing associated with that Sample

  @backfill @analysis-methods
  Scenario: AnalysisMethod values are preserved as-is
    Given legacy NMA_MajorChemistry records exist with:
      | GlobalID                             | SamplePtID                           | Analyte  | SampleValue | Units | AnalysisDate | AnalysisMethod     |
      | 9bd4ad44-7f1a-4f0d-9d8f-8ff9e39c6df1 | 550e8400-e29b-41d4-a716-446655440000 | Chloride | 12.3        | mg/L  | 2001-06-26   | Field analysis     |
      | 362dc2e3-8ef7-4f4a-8d13-4c09a9f2f4b2 | 550e8400-e29b-41d4-a716-446655440000 | Sulfate  | 22.1        | mg/L  | 2001-06-26   | Taken in the field |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then the Observation for GlobalID "9bd4ad44-7f1a-4f0d-9d8f-8ff9e39c6df1" should set analysis_method_name to "Field analysis"
    And the Observation for GlobalID "362dc2e3-8ef7-4f4a-8d13-4c09a9f2f4b2" should set analysis_method_name to "Taken in the field"

  @backfill @notes
  Scenario: Notes are stored as observation notes
    Given a legacy NMA_MajorChemistry record exists with:
      | field       | value                               |
      | GlobalID    | 6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74 |
      | SamplePtID  | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte     | Alkalinity                          |
      | Notes       | as CaCO3                            |
      | SampleValue | 118                                 |
      | Units       | mg/L                                |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then the Observation for GlobalID "6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74" should set parameter_name to "Alkalinity"
    And the Observation for GlobalID "6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74" should set notes to "as CaCO3"

  @backfill @qualifiers
  Scenario: Symbol "<" means SampleValue is a detection limit (not a detected concentration)
    Given a legacy NMA_MajorChemistry record exists with:
      | field       | value                               |
      | GlobalID    | 28d93dc8-99e3-40a2-8f1b-0b1f48d46cd8 |
      | SamplePtID  | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte     | Fluoride                            |
      | Symbol      | <                                   |
      | SampleValue | 0.05                                |
      | Units       | mg/L                                |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then the Observation for GlobalID "28d93dc8-99e3-40a2-8f1b-0b1f48d46cd8" should set detect_flag to false

  @backfill @agency
  Scenario: AnalysesAgency is standardized and mapped consistently
    Given a legacy Chemistry_SampleInfo record exists with:
      | field          | value                               |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | AnalysesAgency | NMBGMR                              |
    And a legacy NMA_MajorChemistry record exists with:
      | field          | value                               |
      | GlobalID       | 82e8c6d9-6c2b-4b2b-8c86-1b7b6b62cfe0 |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte        | Sodium                              |
      | SampleValue    | 19.4                                |
      | Units          | mg/L                                |
      | AnalysesAgency | NMBGMR & others                     |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then the Observation for GlobalID "82e8c6d9-6c2b-4b2b-8c86-1b7b6b62cfe0" should set analysis_agency to "NMBGMR"

  @backfill @ignore
  Scenario: Unmapped legacy fields are not persisted in the new schema
    Given a legacy NMA_MajorChemistry record exists with:
      | field        | value                               |
      | GlobalID     | 8f1e6dcb-9a5d-4b9c-9bf0-9b7c3f2b6b62 |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000 |
      | SamplePointID| AB-0186A                            |
      | OBJECTID     | 9012                                |
      | WCLab_ID     | LAB-98765                           |
      | Volume       | 25                                  |
      | VolumeUnit   | mL                                  |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Major Chemistry backfill job
    Then the Observation for GlobalID "8f1e6dcb-9a5d-4b9c-9bf0-9b7c3f2b6b62" should not store SamplePointID, OBJECTID, WCLab_ID, Volume, or VolumeUnit

  @backfill @orphan-prevention
  Scenario: Orphan legacy records are skipped and reported
    Given a legacy NMA_MajorChemistry record exists with:
      | field      | value                               |
      | GlobalID   | 02b8a58c-9a7e-44e0-9e9f-9b26f2b8c71f |
      | SamplePtID | 319c1256-1237-4e17-b93e-03ad8a7789d6 |
      | Analyte    | Nitrate                             |
      | SampleValue| 1.2                                 |
      | Units      | mg/L                                |
    When I run the Major Chemistry backfill job
    Then no Observation record should exist with nma_pk_chemistryresults "02b8a58c-9a7e-44e0-9e9f-9b26f2b8c71f"
    And the backfill job should report 1 skipped record due to missing Sample linkage (SamplePtID)
