@backend @migration @chemistry
Feature: Refactor legacy Radionuclides into the Ocotillo schema via backfill job
  As an Ocotillo database engineer
  I want a repeatable backfill job to refactor legacy Radionuclides into the new schema
  So that radionuclide chemistry results are migrated with auditability and idempotence

  Background:
    Given a database session is available
    And legacy NMA_Radionuclides records exist in the database
    And lexicon terms exist for parameter_name, unit, analysis_method_type, and sample_matrix "water"

  @backfill @idempotent
  Scenario: Backfill creates Observation records and can be re-run without duplicates
    Given a legacy NMA_Radionuclides record exists with:
      | field          | value                               |
      | GlobalID       | 0C354D8D-5404-41CE-9C95-002213371C4F |
      | SamplePtID     | 77F1E3CF-A961-440E-966C-DD2E3675044B |
      | Analyte        | GB                                  |
      | SampleValue    | 5                                   |
      | Units          | pCi/L                               |
      | AnalysisDate   | 2005-01-18                           |
      | AnalysisMethod | E900.0                               |
      | AnalysesAgency | Hall Environmental Analysis          |
      | Uncertainty    | 2                                   |
    And a Sample record exists with nma_pk_chemistrysample "77F1E3CF-A961-440E-966C-DD2E3675044B"
    When I run the Radionuclides backfill job
    Then exactly 1 Observation record should exist with nma_pk_chemistryresults "0C354D8D-5404-41CE-9C95-002213371C4F"
    And the Observation should reference the Sample with nma_pk_chemistrysample "77F1E3CF-A961-440E-966C-DD2E3675044B"
    And the Observation should set observation_datetime to "2005-01-18"
    And the Observation should set value to 5
    And the Observation should set unit to "pCi/L"
    And a Parameter record should exist with parameter_name "GB" and matrix "water"
    And the Observation should reference the Parameter with parameter_name "GB" and matrix "water"
    And the Observation should set analysis_method_name to "E900.0"
    And the Observation should set uncertainty to 2
    And the Observation should set analysis_agency to "Hall Environmental Analysis"
    When I run the Radionuclides backfill job again
    Then exactly 1 Observation record should exist with nma_pk_chemistryresults "0C354D8D-5404-41CE-9C95-002213371C4F"

  @backfill @volume
  Scenario: Volume and VolumeUnit populate the related Sample
    Given a legacy NMA_Radionuclides record exists with:
      | field       | value                               |
      | GlobalID    | 9cece0ef-f0b3-4e3d-8df7-2f82dc67cb2c |
      | SamplePtID  | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte     | Uranium                             |
      | SampleValue | 0.12                                |
      | Units       | pCi/L                               |
      | Volume      | 25                                  |
      | VolumeUnit  | mL                                  |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Radionuclides backfill job
    Then the Sample should set volume to 25
    And the Sample should set volume_unit to "mL"

  @backfill @linkage
  Scenario: Observations are not orphaned and link to Sample (and Thing) by SamplePtID
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                               |
      | SamplePtID   | 7758D992-0394-42B1-BE96-734FCACB6412 |
      | SamplePointID| EB-490A                             |
    And a legacy NMA_Radionuclides record exists with:
      | field       | value                               |
      | GlobalID    | 76F3A993-A29B-413B-83E0-00ADF51D15A2 |
      | SamplePtID  | 7758D992-0394-42B1-BE96-734FCACB6412 |
      | Analyte     | GA                                  |
      | SampleValue | 5.7                                 |
      | Units       | pCi/L                               |
    And a Sample record exists with nma_pk_chemistrysample "7758D992-0394-42B1-BE96-734FCACB6412"
    When I run the Radionuclides backfill job
    Then the Observation for GlobalID "76F3A993-A29B-413B-83E0-00ADF51D15A2" should reference the Sample with nma_pk_chemistrysample "7758D992-0394-42B1-BE96-734FCACB6412"
    And the Observation for GlobalID "76F3A993-A29B-413B-83E0-00ADF51D15A2" should reference the Thing associated with that Sample

  @backfill @analysis-methods
  Scenario: AnalysisMethod values are preserved as-is
    Given legacy NMA_Radionuclides records exist with:
      | GlobalID                             | SamplePtID                           | Analyte | SampleValue | Units | AnalysisDate | AnalysisMethod   |
      | 0C354D8D-5404-41CE-9C95-002213371C4F | 77F1E3CF-A961-440E-966C-DD2E3675044B | GB      | 5           | pCi/L| 2005-01-18   | E900.0           |
      | 095DA2E3-79E3-4BF2-B096-025C6D9A64B7 | BC50F55E-5BF1-471D-931D-03501081B4FD | Ra228   | 2.6         | pCi/L| 2003-11-26   | EPA 904.0 Mod    |
    And a Sample record exists with nma_pk_chemistrysample "77F1E3CF-A961-440E-966C-DD2E3675044B"
    And a Sample record exists with nma_pk_chemistrysample "BC50F55E-5BF1-471D-931D-03501081B4FD"
    When I run the Radionuclides backfill job
    Then the Observation for GlobalID "0C354D8D-5404-41CE-9C95-002213371C4F" should set analysis_method_name to "E900.0"
    And the Observation for GlobalID "095DA2E3-79E3-4BF2-B096-025C6D9A64B7" should set analysis_method_name to "EPA 904.0 Mod"

  @backfill @notes
  Scenario: Notes are stored in the Notes table and linked to the Observation
    Given a legacy NMA_Radionuclides record exists with:
      | field       | value                               |
      | GlobalID    | 6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74 |
      | SamplePtID  | 550e8400-e29b-41d4-a716-446655440000 |
      | Analyte     | Uranium-238                         |
      | Notes       | counts below detection              |
      | SampleValue | 0.02                                |
      | Units       | pCi/L                               |
    And a Sample record exists with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    When I run the Radionuclides backfill job
    Then a Parameter record should exist with parameter_name "Uranium-238" and matrix "water"
    And the Observation for GlobalID "6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74" should reference the Parameter with parameter_name "Uranium-238" and matrix "water"
    And a Notes record should exist with:
      | field        | value   |
      | target_table | observation |
      | target_id    | (observation.id for GlobalID 6a5d2f1e-7b86-4b64-a7b7-9b5f5a612f74) |
      | note_type    | Chemistry Observation |
      | content      | counts below detection |

  @backfill @qualifiers
  Scenario: Symbol "<" means SampleValue is a detection limit (not a detected concentration)
    Given a legacy NMA_Radionuclides record exists with:
      | field       | value                               |
      | GlobalID    | F7370DC2-668F-447A-9E46-00D8CA514299 |
      | SamplePtID  | D8CCC58C-55F2-4A35-B65D-A08F4A07902A |
      | Analyte     | GA                                  |
      | Symbol      | <                                   |
      | SampleValue | 2                                   |
      | Units       | pCi/L                               |
    And a Sample record exists with nma_pk_chemistrysample "D8CCC58C-55F2-4A35-B65D-A08F4A07902A"
    When I run the Radionuclides backfill job
    Then the Observation for GlobalID "F7370DC2-668F-447A-9E46-00D8CA514299" should set detect_flag to false

  @backfill @ignore
  Scenario: Unmapped legacy fields are not persisted in the new schema
    Given a legacy NMA_Radionuclides record exists with:
      | field        | value                               |
      | GlobalID     | 76F3A993-A29B-413B-83E0-00ADF51D15A2 |
      | SamplePtID   | 7758D992-0394-42B1-BE96-734FCACB6412 |
      | Analyte      | Radium-226                          |
      | SamplePointID| EB-490A                             |
      | OBJECTID     | 333                                 |
      | WCLab_ID     | null                                |
    And a Sample record exists with nma_pk_chemistrysample "7758D992-0394-42B1-BE96-734FCACB6412"
    When I run the Radionuclides backfill job
    Then the Observation for GlobalID "76F3A993-A29B-413B-83E0-00ADF51D15A2" should not store SamplePointID, OBJECTID, or WCLab_ID

  @backfill @orphan-prevention
  Scenario: Orphan legacy records are skipped and reported
    Given a legacy NMA_Radionuclides record exists with:
      | field      | value                               |
      | GlobalID   | 02b8a58c-9a7e-44e0-9e9f-9b26f2b8c71f |
      | SamplePtID | 319c1256-1237-4e17-b93e-03ad8a7789d6 |
      | Analyte    | Nitrate                             |
      | SampleValue| 1.2                                 |
      | Units      | pCi/L                               |
    When I run the Radionuclides backfill job
    Then no Observation record should exist with nma_pk_chemistryresults "02b8a58c-9a7e-44e0-9e9f-9b26f2b8c71f"
    And the backfill job should report 1 skipped record due to missing Sample linkage (SamplePtID)
