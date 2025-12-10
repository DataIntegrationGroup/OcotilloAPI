# ===============================================================================
# Author:  Jake Ross
# Copyright 2025 New Mexico Bureau of Geology & Mineral Resources
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
# ===============================================================================
import csv
import mimetypes
from pathlib import Path

from behave import given, when, then
from behave.runner import Context

from manage import associate_assets
from services.gcs_helper import get_storage_bucket


@given('a local directory named "asset_import_batch"')
def step_impl(context: Context):
    context.source_directory = (
        Path("tests") / "features" / "steps" / "asset_import_batch"
    )
    assert context.source_directory.exists()
    assert context.source_directory.is_dir()


@given('the directory contains a manifest file named "manifest.txt"')
def step_impl(context: Context):
    context.manifest_file = context.source_directory / "manifest.txt"
    assert context.manifest_file.exists()


@given(
    "the manifest file is a 3-column CSV with headers asset_file_name, thing_name and asset_type"
)
def step_impl(context: Context):
    header = ["asset_file_name", "thing_name", "asset_type"]
    with open(context.manifest_file) as f:
        inheader = csv.DictReader(f).fieldnames

    assert sorted(inheader) == sorted(header)


@given("the directory contains a set of asset files referenced in the manifest")
def step_impl(context: Context):
    for path in context.source_directory.iterdir():
        if path.name == "manifest.txt":
            continue

        assert mimetypes.guess_type(str(path)) in ("image/png", "application/pdf")


@given(
    'the manifest contains a row for "{asset_file_name}" with thing "{thing_name}" and asset type "{asset_type}"'
)
def step_impl(context: Context, asset_file_name, thing_name, asset_type):
    with open(context.manifest_file) as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["asset_file_name"] == asset_file_name:
                assert r["thing_name"] == thing_name
                assert r["asset_type"] == asset_type
                break
        else:
            raise Exception(f"{asset_file_name} not found in manifest")


@given('the directory contains a asset file named "{asset_file_name}"')
def step_impl(context: Context, asset_file_name):
    for path in context.source_directory.iterdir():
        if path.name == asset_file_name:
            break
    else:
        raise Exception(f"{asset_file_name} not found in directory")


@when('I run the "associate_assets" command on the directory')
def step_impl(context: Context):
    uploaded_blobs = associate_assets(context.source_directory)
    context.upload_blobs = uploaded_blobs


@then('the app should upload "<asset_file_name>" to Google Cloud Storage')
def step_impl(context: Context, asset_file_name):
    bucket = get_storage_bucket()
    head, ext = asset_file_name.split(".")
    for blob in context.uploaded_blobs:
        if blob.startswith(head):
            if bucket.get_blob(blob):
                break
            else:
                raise Exception(f"{blob} not found in gcs")
    else:
        raise Exception(f"{blob} not uploaded")


# ============= EOF =============================================
