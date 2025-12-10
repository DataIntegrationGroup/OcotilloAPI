# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
import csv
import mimetypes
from pathlib import Path

from dotenv import load_dotenv
from fastapi import UploadFile
from sqlalchemy import select

from db import Thing
from db.engine import session_ctx
from services.gcs_helper import get_storage_bucket
from services.validation.asset_helper import upload_and_associate

load_dotenv()

import click
from core.initializers import init_lexicon


@click.group()
def cli():
    """Command line interface for managing the application."""
    pass


@cli.command()
def initialize_lexicon():
    init_lexicon()


@cli.command()
def associate_assets_command():
    associate_assets()


@cli.command()
def well_inventory_csv():
    """
    parse and upload a csv to database
    """
    # TODO: use the same helper function used by api to parse and upload a WI csv


@cli.command()
def waterlevels_csv():
    """
    parse and upload a csv
    """
    # TODO: use the same helper function used by api to parse and upload a WL csv


def associate_assets(source_directory: Path) -> list[str]:
    """
    given a directory
    and the directory contains a manifest file
    and the manifest file is a 3-column csv (asset_file_name, thing_name aka pointid, asset_type)
    and the directory contains a set of photos

    then when i run the associate photos command
    the app should save the photos to gcs
    and associate each uploaded photo with the corresponding thing

    """

    bucket = get_storage_bucket()
    m = source_directory / "manifest.txt"
    with open(m, "r") as rf:
        reader = csv.DictReader(rf)

    blobs = []
    with session_ctx() as sess:
        for row in reader:
            # save file to gcs
            path = row["asset_file_name"]

            with open(source_directory / path, "rb") as fp:
                file = UploadFile(fp)

            sql = select(Thing).where(Thing.name == row["thing_name"])
            thing = sess.scalars(sql).one_or_none()
            if thing:
                # get mime_type from file
                mime_type, encoding = mimetypes.guess_type(path)
                uri, blob_name = upload_and_associate(
                    sess, file, bucket, thing, path, **{"mime_type": mime_type}
                )
                blobs.append(blob_name)

            else:
                pass
    return blobs


if __name__ == "__main__":
    cli()

# ============= EOF =============================================
