@backend @migration @chemistry
Feature: Refactor legacy Chemistry SampleInfo into the Ocotillo schema via backfill job
  As an Ocotillo database engineer
  I want a repeatable backfill job to refactor legacy Chemistry SampleInfo into the new schema
  So that chemistry sampling metadata is migrated with auditability and idempotence

  Background:
    Given a database session is available
    And legacy Chemistry_SampleInfo records exist in the database
    And lexicon terms exist for sample_method, qc_type, note_type "Sampling Procedure", and data_provenance origin_type

  @backfill @idempotent
  Scenario: Backfill creates Sample records and can be re-run without duplicates
    Given a legacy Chemistry_SampleInfo record exists with:
      | field             | value                               |
      | SamplePtID        | 550e8400-e29b-41d4-a716-446655440000 |
      | thing_id          | (thing.id for Thing "AB-0186")       |
      | SamplePointID     | AB-0186A                            |
      | WCLab_ID          | LAB-12345                           |
      | CollectionDate    | 2001-06-25                          |
      | CollectionMethod  | Pump                                |
      | SampleType        | Normal                              |
    And a Thing exists with name "AB-0186"
    When I run the Chemistry SampleInfo backfill job
    Then exactly 1 Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Sample should set lab_sample_id to "LAB-12345"
    And the Sample should set sample_date to "2001-06-25"
    And the Sample should set sample_method to "Pump"
    And the Sample should set qc_type to "Normal"
    When I run the Chemistry SampleInfo backfill job again
    Then exactly 1 Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"

  @backfill @linkage
  Scenario: Observations link to Sample by sample.id resolved from legacy SamplePtID
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                                |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000  |
      | thing_id     | (thing.id for Thing "AB-0186")        |
      | SamplePointID| AB-0186A                             |
    And a Thing exists with name "AB-0186"
    And a FieldActivity exists for Thing "AB-0186"
    And legacy chemistry result rows exist for SamplePtID "550e8400-e29b-41d4-a716-446655440000"
    When I run the Chemistry SampleInfo backfill job
    Then a Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Sample should reference the FieldActivity for Thing "AB-0186"
    And Observation records derived from SamplePtID "550e8400-e29b-41d4-a716-446655440000" should reference that Sample's id

  @backfill @agency
  Scenario: AnalysesAgency is stored on the Sample
    Given a legacy Chemistry_SampleInfo record exists with:
      | field          | value                               |
      | SamplePtID     | 550e8400-e29b-41d4-a716-446655440000 |
      | thing_id       | (thing.id for Thing "AB-0186")       |
      | SamplePointID  | AB-0186A                            |
      | AnalysesAgency | NMBGMR                              |
    And a Thing exists with name "AB-0186"
    When I run the Chemistry SampleInfo backfill job
    Then a Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And the Sample should set analysis_agency to "NMBGMR"

  @backfill @provenance
  Scenario: CollectedBy and DataSource create DataProvenance records for Sample
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                                |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000  |
      | thing_id     | (thing.id for Thing "AB-0186")        |
      | SamplePointID| AB-0186A                             |
      | CollectedBy  | Measured by NMBGMR staff         |
      | DataSource   | WRIR 03-4131                     |
    And a Thing exists with name "AB-0186"
    When I run the Chemistry SampleInfo backfill job
    Then a Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And a DataProvenance record should exist with:
      | field        | value   |
      | target_table | sample  |
      | target_id    | (sample.id for SamplePtID 550e8400-e29b-41d4-a716-446655440000) |
      | field_name   | null    |
      | origin_type  | Measured by NMBGMR staff    |
      | origin_source| WRIR 03-4131 |

  @backfill @data-quality
  Scenario: DataQuality sets reportable on Sample
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                               |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000 |
      | thing_id     | (thing.id for Thing "AB-0186")       |
      | SamplePointID| AB-0186A                            |
      | DataQuality  | Y                                   |
    And a Thing exists with name "AB-0186"
    And legacy chemistry result rows exist for SamplePtID "550e8400-e29b-41d4-a716-446655440000"
    When I run the Chemistry SampleInfo backfill job
    Then the Sample should set reportable to true

  @backfill @notes
  Scenario: SampleNotes are stored as Notes linked to Sample
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                                                                 |
      | SamplePtID   | 550e8400-e29b-41d4-a716-446655440000                                  |
      | thing_id     | (thing.id for Thing "AB-0186")                                        |
      | SamplePointID| AB-0186A                                                              |
      | SampleNotes  | Sample collected by NMED; chemistry is incomplete.                    |
    And a Thing exists with name "AB-0186"
    When I run the Chemistry SampleInfo backfill job
    Then a Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And a Notes record should exist with:
      | field        | value   |
      | target_table | sample  |
      | target_id    | (sample.id for SamplePtID 550e8400-e29b-41d4-a716-446655440000) |
      | note_type    | Sampling Procedure |
      | content      | Sample collected by NMED; chemistry is incomplete. |

  @backfill @release
  Scenario: PublicRelease controls release_status on derived Observation results
    Given a legacy Chemistry_SampleInfo record exists with:
      | field         | value                               |
      | SamplePtID    | 550e8400-e29b-41d4-a716-446655440000 |
      | thing_id      | (thing.id for Thing "AB-0186")       |
      | SamplePointID | AB-0186A                            |
      | PublicRelease | true                                |
    And a Thing exists with name "AB-0186"
    And legacy chemistry result rows exist for SamplePtID "550e8400-e29b-41d4-a716-446655440000"
    When I run the Chemistry SampleInfo backfill job
    Then Observation records derived from that sample should set release_status to "public"

  @backfill @ignore
  Scenario: Unmapped legacy fields are not persisted in the new schema
    Given a legacy Chemistry_SampleInfo record exists with:
      | field                 | value     |
      | SamplePtID            | 550e8400-e29b-41d4-a716-446655440000 |
      | thing_id              | (thing.id for Thing "AB-0186")       |
      | SamplePointID         | AB-0186A  |
      | StudySample           | Y         |
      | WaterType             | NA        |
      | SampleMaterialNotH2O  | Soil      |
      | AddedDaytoDate        | true      |
      | AddedMonthDaytoDate   | false     |
      | LocationID            | 410       |
      | ObjectID              | 2739      |
    And a Thing exists with name "AB-0186"
    When I run the Chemistry SampleInfo backfill job
    Then a Sample record should exist with nma_pk_chemistrysample "550e8400-e29b-41d4-a716-446655440000"
    And no Sample fields should store SamplePointID, StudySample, WaterType, SampleMaterialNotH2O, AddedDaytoDate, AddedMonthDaytoDate, LocationID, or ObjectID

  @backfill @orphan-prevention
  Scenario: Orphan legacy records are skipped and reported
    Given a legacy Chemistry_SampleInfo record exists with:
      | field        | value                               |
      | SamplePtID   | 319c1256-1237-4e17-b93e-03ad8a7789d6 |
      | thing_id     | 999999                              |
      | SamplePointID| AB-0024A                            |
    When I run the Chemistry SampleInfo backfill job
    Then no Sample record should exist with nma_pk_chemistrysample "319c1256-1237-4e17-b93e-03ad8a7789d6"
    And the backfill job should report 1 skipped record due to missing Thing linkage (thing_id)
