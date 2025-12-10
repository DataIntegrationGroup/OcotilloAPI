# Created by jakeross at 12/9/25
@backend @cli @gcs
Feature: Associate assets with things based on a manifest file
  In order to keep assets organized and discoverable
  As a manager of the system
  I want assets in a directory to be uploaded and associated to things using a CSV manifest

  Background:
    Given a local directory named "asset_import_batch"
    And the directory contains a manifest file named "manifest.txt"
    And the manifest file is a 2-column CSV with headers asset_file_name and thing_name
    And the directory contains a set of asset files referenced in the manifest

  @happy_path
  Scenario Outline: Successfully upload and associate assets from a valid manifest
    Given the manifest contains a row for "<asset_file_name>" with thing "<thing_name>"
    And the directory contains a asset file named "<asset_file_name>"
    When I run the "associate_assets" command on the directory
    Then the app should upload "<asset_file_name>" to Google Cloud Storage
    And the app should create an association between the uploaded asset and thing "<thing_name>"
#    And the association should record:
#      | field        | value            |
#      | thing_name   | <thing_name>     |
#      | asset_type   | <asset_type>     |
#      | file_name    | <asset_file_name> |
#      | storage_type | gcs              |
#    And the command should exit with a success status

    Examples:
      | asset_file_name    | thing_name |
      | AR0001_1.JPG | AR0001 |
      | AR0001_2.JPG  | AR0001 |

  @idempotent @multiple_runs
  Scenario: Idempotent behavior when running associate photos multiple times with the same manifest
    When I run the "associate_assets" command on the directory
    Then each photo listed in the manifest should be uploaded exactly once to GCS
    And each uploaded photo should be associated exactly once to its corresponding thing
    When I run the "associate photos" command on the same directory again with the same manifest
    Then each uploaded photo should be associated exactly once to its corresponding thing
#
#  @multiple_rows @idempotent
#  Scenario: Upload and associate multiple assets in a single run
#    Given the manifest contains rows for multiple asset_file_name values for the same thing_name
#    And the directory contains asset files matching all listed asset_file_name values
#    When I run the "associate assets" command on the directory
#    Then all assets listed in the manifest should be uploaded to GCS
#    And all uploaded assets should be associated with their corresponding things
#    And no duplicate associations should be created if the command is re-run with the same manifest and files
#
#  @negative @missing-file
#  Scenario: Manifest references a asset that does not exist in the directory
#    Given the manifest contains a row for "missing-asset.jpg" with a valid thing_name and asset_type
#    And the directory does not contain a file named "missing-asset.jpg"
#    When I run the "associate_assets" command on the directory
#    Then the app should not attempt to upload "missing-asset.jpg"
#    And the app should log an error indicating the missing file
#    And the app should report at least one failure in the run summary
#    And other valid assets present in the directory and manifest should still be uploaded and associated
#
#  @negative @extra-file
#  Scenario: Directory contains extra assets that are not listed in the manifest
#    Given the directory contains a asset file named "orphan-asset.jpg"
#    And the manifest does not contain any row with asset_file_name "orphan-asset.jpg"
#    When I run the "associate assets" command on the directory
#    Then the app should not upload "orphan-asset.jpg"
#    And the app should log a warning indicating assets in the directory without manifest entries
#    And the command should still exit with a success status if all manifest-referenced assets are processed successfully
#
#  @negative @invalid-csv
#  Scenario: Manifest file has invalid CSV format
#    Given the manifest file is not a valid 3-column CSV with the expected headers
#    When I run the "associate assets" command on the directory
#    Then the app should not upload any assets
#    And the app should report that the manifest is invalid
#    And the command should exit with a failure status
#
#  @negative @missing-manifest
#  Scenario: Manifest file is missing from the directory
#    Given the directory does not contain "manifest.csv"
#    When I run the "associate assets" command on the directory
#    Then the app should not upload any assets
#    And the app should report that the manifest file is required
#    And the command should exit with a failure status
#
#  @negative @upload-failure @gcs
#  Scenario: GCS upload fails for a specific asset
#    Given the manifest contains a valid row for "unstable-asset.jpg"
#    And the directory contains "unstable-asset.jpg"
#    And an error occurs while uploading "unstable-asset.jpg" to GCS
#    When I run the "associate assets" command on the directory
#    Then the app should report the upload failure for "unstable-asset.jpg"
#    And the app should not create an association for "unstable-asset.jpg"
#    And the app should continue processing other assets where possible
#    And the command should exit with a failure status
#
#  @negative @association-failure
#  Scenario: Association cannot be created after successful upload
#    Given the manifest contains a valid row for "orphan-association.jpg"
#    And the directory contains "orphan-association.jpg"
#    And the asset is successfully uploaded to GCS
#    And an error occurs while creating the association to the corresponding thing
#    When I run the "associate assets" command on the directory
#    Then the app should not repeat the upload of "orphan-association.jpg"
#    And the app should record that the association step failed
#    And the command should exit with a failure status
#    And the error details should identify the affected thing_name and asset_file_name
#
##  @validation @asset-type
##  Scenario Outline: Validate allowed asset types in the manifest
##    Given the manifest contains a row for "<asset_file_name>" with thing "<thing_name>" and asset type "<asset_type>"
##    And the directory contains "<asset_file_name>"
##    When I run the "associate assets" command on the directory
##    Then the app should <result> "<asset_file_name>" for asset type "<asset_type>"
##    And the app should <summary_status> in the run summary
##
##    Examples:
##      | asset_file_name   | thing_name | asset_type   | result             | summary_status              |
##      | pump-002-front.jpg| PUMP-002   | asset_front  | successfully upload and associate | report the row assuccessful |
##      | pump-002-xray.jpg | PUMP-002   | unknown_type | reject processing of             | report the row as invalid asset type |
