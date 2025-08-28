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
import io

from requests import Session
from starlette.datastructures import UploadFile

from db import Asset, AssetThingAssociation, Thing
from services.audit_helper import audit_add
from services.gcs_helper import (
    gcs_upload,
    check_asset_exists,
    get_storage_bucket,
    get_storage_client,
)
from transfers.util import get_valid_point_ids


def transfer_assets(session: Session) -> None:
    client = get_storage_client()

    tempbucket = client.get_bucket("temp-assets")
    bucket = get_storage_bucket(client)

    point_ids = get_valid_point_ids(session)
    for p in point_ids:
        # find images in temp bucket
        blobs = tempbucket.list_blobs(match_glob=f"{p}*")

        # move blobs from temp to assets bucket
        for srcblob in blobs:
            f = srcblob.download_as_bytes()
            ff = UploadFile(file=io.BytesIO(f), filename=srcblob.name, size=len(f))
            uri, blob = gcs_upload(ff, bucket)
            add_asset(session, ff, srcblob.name, p, uri, blob.name)


def transfer_assets_testing(session: Session) -> None:
    for p in ("asset1.png", "asset2.png", "asset3.png"):
        with open(f"./data/assets/{p}", "rb") as f:
            uf = UploadFile(file=f, filename=p, size=10)
            uri, blob_name = gcs_upload(uf)
            thing_id = 151

            if check_asset_exists(session, blob_name, thing_id):
                print(f"Asset {blob_name} already exists. Skipping.")
                continue
            add_asset(session, uf, p, thing_id, uri, blob_name)


def add_asset(
    session: Session, uf: UploadFile, p: str, thing_id: int, uri: str, blob_name: str
) -> None:
    asset = Asset(
        name=p,
        label=p,
        storage_path=blob_name,
        storage_service="gcs",
        mime_type="image/png",
        size=uf.size,
        uri=uri,
    )
    assoc = AssetThingAssociation()
    audit_add({"sub": "foobar", "name": "Mr. Foobar"}, assoc)
    thing = session.get(Thing, thing_id)
    assoc.thing = thing
    assoc.asset = asset
    session.add(assoc)
    session.add(asset)
    session.commit()


# ============= EOF =============================================
