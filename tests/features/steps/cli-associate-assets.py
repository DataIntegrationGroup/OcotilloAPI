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
from cli.service_adapter import associate_assets
from db import Thing, Asset
from db.engine import session_ctx
from services.gcs_helper import get_storage_bucket
from sqlalchemy import select


@given('a local directory named "asset_import_batch"')
def step_given_a_local_directory_named_asset_import_batch(context: Context):
    context.source_directory = (
        Path("tests") / "features" / "data" / "asset_import_batch"
    )
    assert context.source_directory.exists()
    assert context.source_directory.is_dir()


@given('the directory contains a manifest file named "manifest.txt"')
def step_given_the_directory_contains_a_manifest_file_named_manifest_txt(
    context: Context,
):
    context.manifest_file = context.source_directory / "manifest.txt"
    assert context.manifest_file.exists()


@given(
    "the manifest file is a 2-column CSV with headers asset_file_name and thing_name"
)
def step_step_step(context: Context):
    header = ["asset_file_name", "thing_name"]
    with open(context.manifest_file) as f:
        reader = csv.DictReader(f)
        inheader = reader.fieldnames
        context.asset_file_names = [r["asset_file_name"] for r in reader]

    assert sorted(inheader) == sorted(header)


@given("the directory contains a set of asset files referenced in the manifest")
def step_given_the_directory_contains_a_set_of_asset_files_referenced_in(
    context: Context,
):
    for a in context.asset_file_names:
        p = context.source_directory / a
        assert p.exists()
        assert mimetypes.guess_type(str(p))[0] in (
            "image/png",
            "image/jpeg",
            "application/pdf",
        )


@given('the manifest contains a row for "{asset_file_name}" with thing "{thing_name}"')
def step_given_the_manifest_contains_a_row_for_asset_file_name_with(
    context: Context, asset_file_name, thing_name
):
    with open(context.manifest_file) as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["asset_file_name"].strip() == asset_file_name.strip():
                assert r["thing_name"].strip() == thing_name.strip()
                break
        else:
            raise Exception(f"{asset_file_name} not found in manifest")


@given('the directory contains a asset file named "{asset_file_name}"')
def step_given_the_directory_contains_a_asset_file_named_asset_file_name(
    context: Context, asset_file_name
):
    for path in context.source_directory.iterdir():
        if path.name == asset_file_name:
            break
    else:
        raise Exception(f"{asset_file_name} not found in directory")


@when('I run the "associate_assets" command on the directory')
def step_when_i_run_the_associate_assets_command_on_the_directory(context: Context):
    uris = associate_assets(context.source_directory)
    context.uris = uris


@then('the app should upload "{asset_file_name}" to Google Cloud Storage')
def step_then_the_app_should_upload_asset_file_name_to_google_cloud(
    context: Context, asset_file_name
):
    bucket = get_storage_bucket()
    head, ext = asset_file_name.split(".")
    for uri in context.uris:
        blob = uri.split("/")[-1]
        if blob.startswith(head):
            if bucket.get_blob(blob):
                break
            else:
                raise Exception(f"{asset_file_name} not found in gcs")
    else:
        raise Exception(f"{asset_file_name} not uploaded")


@then(
    'the app should create an association between the uploaded asset and thing "{thing_name}"'
)
def step_step_step_2(context: Context, thing_name):
    with session_ctx() as session:
        sql = select(Thing).where(Thing.name == thing_name)
        thing = session.scalars(sql).one_or_none()
        if not thing:
            raise Exception(f"Thing {thing_name} not found")

        assets = thing.assets
        for uri in context.uris:
            a = next((a for a in assets if a.uri == uri), None)
            if a:
                break
            else:
                raise Exception(f"No asset associated with uri {uri}")
        else:
            raise Exception(f"No asset associated with thing {thing_name}")


@given(
    'the manifest contains a row for "missing-asset.jpg" with a valid thing_name and asset_type'
)
def step_step_step_3(context: Context):
    context.manifest_file = context.source_directory / "manifest-missing-asset.txt"
    assert context.manifest_file.exists()


@given('the directory does not contain a file named "missing-asset.jpg"')
def step_given_the_directory_does_not_contain_a_file_named_missing_asset(
    context: Context,
):
    assert not (context.source_directory / "missing-asset.jpg").exists()


@then("each photo listed in the manifest should be uploaded exactly once to GCS")
def step_then_each_photo_listed_in_the_manifest_should_be_uploaded_exactly(
    context: Context,
):
    bucket = get_storage_bucket()
    for uri in context.uris:
        blob = uri.split("/")[-1]
        assert bucket.get_blob(blob) is not None, f"{uri} not uploaded exactly once"


@then(
    "each uploaded photo should be associated exactly once to its corresponding thing"
)
def step_step_step_4(context: Context):
    with session_ctx() as session:
        for uri in context.uris:
            sql = select(Asset).where(Asset.uri == uri)
            a = session.scalars(sql).one_or_none()
            assert (
                len(a.things) == 1
            ), f"{uri} associated with multiple things {[t.name for t in a.things]}"


@when(
    'I run the "associate photos" command on the same directory again with the same manifest'
)
def step_step_step_5(context: Context):
    uris = associate_assets(context.source_directory)
    context.uris = uris


# ============= EOF =============================================
