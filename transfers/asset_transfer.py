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
from starlette.datastructures import UploadFile

from db import Asset, AssetThingAssociation, Thing
from services.audit_helper import audit_add
from services.gcs_helper import gcs_upload, check_asset_exists


# ============= EOF =============================================
def transfer_assets(session):
    for p in ("asset1.png", "asset2.png", "asset3.png"):
        with open(f"./data/assets/{p}", "rb") as f:
            uf = UploadFile(file=f, filename=p, size=10)
            uri, blob_name = gcs_upload(uf)
            thing_id = 151

            if check_asset_exists(session, blob_name, thing_id):
                print(f"Asset {blob_name} already exists. Skipping.")
                continue

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
