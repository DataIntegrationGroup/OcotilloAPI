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
import io
import mimetypes
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select

from db import Thing, Asset
from db.engine import session_ctx
from services.asset_helper import upload_and_associate
from services.gcs_helper import get_storage_bucket, make_blob_name_and_uri


def well_inventory_csv(source_file: Path | str):
    if isinstance(source_file, str):
        source_file = Path(source_file)


def water_levels_csv(source_file: Path | str):
    if isinstance(source_file, str):
        source_file = Path(source_file)


def associate_assets(source_directory: Path | str) -> list[str]:
    """
    given a directory
    and the directory contains a manifest file
    and the manifest file is a 3-column csv (asset_file_name, thing_name aka pointid, asset_type)
    and the directory contains a set of photos

    then when i run the associate photos command
    the app should save the photos to gcs
    and associate each uploaded photo with the corresponding thing

    """
    if isinstance(source_directory, str):
        source_directory = Path(source_directory)
    m = source_directory / "manifest.txt"

    bucket = get_storage_bucket()
    uris = []
    with session_ctx() as sess:
        with open(m, "r") as rf:
            reader = csv.DictReader(rf)
            for row in reader:
                # save file to gcs
                path = row["asset_file_name"].strip()

                with open(source_directory / path, "rb") as fp:
                    file = UploadFile(
                        io.BytesIO(fp.read()), filename=path, size=len(fp.read())
                    )

                sql = select(Thing).where(Thing.name == row["thing_name"].strip())
                thing = sess.scalars(sql).one_or_none()
                if thing:
                    # get mime_type from file
                    mime_type, encoding = mimetypes.guess_type(path)
                    blob_name, uri = make_blob_name_and_uri(file)
                    sql = select(Asset).where(Asset.uri == uri)
                    existing_asset = sess.scalars(sql).one_or_none()
                    if existing_asset:
                        continue
                    uri, blob_name = upload_and_associate(
                        sess, file, bucket, thing, path, **{"mime_type": mime_type}
                    )
                    uris.append(uri)

                else:
                    print(f"no thing with name={row['thing_name']} found in db")
        sess.commit()

    return uris


# ============= EOF =============================================
