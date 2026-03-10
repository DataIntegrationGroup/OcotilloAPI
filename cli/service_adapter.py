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
import json
import mimetypes
import sys
from dataclasses import dataclass
from pathlib import Path

from db import Thing, Asset
from db.engine import session_ctx
from fastapi import UploadFile
from services.asset_helper import upload_and_associate
from services.gcs_helper import get_storage_bucket, make_blob_name_and_uri
from services.water_level_csv import bulk_upload_water_levels
from services.well_inventory_csv import import_well_inventory_csv
from sqlalchemy import select


@dataclass
class WellInventoryResult:
    exit_code: int
    stdout: str
    stderr: str
    payload: dict


def well_inventory_csv(source_file: Path | str):
    if isinstance(source_file, str):
        source_file = Path(source_file)
    if source_file.suffix.lower() != ".csv":
        payload = {"detail": "Unsupported file type"}
        return WellInventoryResult(1, json.dumps(payload), payload["detail"], payload)
    content = source_file.read_bytes()
    if not content:
        payload = {"detail": "Empty file"}
        return WellInventoryResult(1, json.dumps(payload), payload["detail"], payload)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        payload = {"detail": "File encoding error"}
        return WellInventoryResult(1, json.dumps(payload), payload["detail"], payload)
    try:
        payload = import_well_inventory_csv(
            text=text, user={"sub": "cli", "name": "cli"}
        )
    except ValueError as exc:
        payload = {"detail": str(exc)}
        return WellInventoryResult(1, json.dumps(payload), payload["detail"], payload)
    exit_code = (
        0 if not payload.get("validation_errors") and not payload.get("detail") else 1
    )
    stderr = ""
    if exit_code != 0:
        if payload.get("validation_errors"):
            stderr = f"Validation errors: {json.dumps(payload.get('validation_errors'), indent=2)}"
        else:
            stderr = f"Error: {payload.get('detail')}"
    return WellInventoryResult(exit_code, json.dumps(payload), stderr, payload)


def water_levels_csv(source_file: Path | str, *, pretty_json: bool = False):
    if isinstance(source_file, str):
        source_file = Path(source_file)

    result = bulk_upload_water_levels(source_file, pretty_json=pretty_json)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


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
