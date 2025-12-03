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

from starlette.datastructures import UploadFile

from db import Asset, AssetThingAssociation
from services.gcs_helper import (
    gcs_upload,
    get_storage_bucket,
    get_storage_client,
)
from transfers.logger import logger
from transfers.util import read_csv, filter_to_valid_point_ids
from transfers.well_transfer import WellChunkTransferer


class AssetTransferer(WellChunkTransferer):
    def __init__(self, *args, **kw):
        self.source_table = "WellPhotos"
        super().__init__(*args, **kw)
        self._client = get_storage_client()
        self._bucket = get_storage_bucket(self._client)
        logger.info(f"Using bucket {self._bucket.name}")

    def _get_dfs(self):
        input_df = read_csv(self.source_table)
        cleaned_df = filter_to_valid_point_ids(input_df)
        return input_df, cleaned_df

    def _chunk_step(self, session, df, i, row, db_item):
        photos = df[df["PointID"] == db_item.name]
        n = len(df)
        if photos.empty:
            photos = df[df["PointID"] == db_item.name.replace("-", "")]
            if photos.empty:
                logger.info(f"No photos found for PointID: {db_item.name}")
                return

        for j, row in enumerate(photos.itertuples()):
            photo_path = row.OLEPath
            srcblob = self._bucket.get_blob(f"nma-photos/{photo_path}")
            if not srcblob:
                logger.critical(
                    f"No photo found for PointID: {db_item.name}, {photo_path}"
                )
                continue

            head, filename = srcblob.name.split("/")
            f = srcblob.download_as_bytes()
            ff = UploadFile(file=io.BytesIO(f), filename=filename, size=len(f))

            uri, blob_name = gcs_upload(ff, self._bucket)
            asset = Asset(
                name=filename,
                label=filename,
                storage_path=blob_name,
                storage_service="gcs",
                mime_type="image/png",
                size=ff.size,
                uri=uri,
            )
            assoc = AssetThingAssociation()
            assoc.thing = db_item
            assoc.asset = asset
            session.add(assoc)
            session.add(asset)
            session.commit()
            logger.info(
                f"Added asset {i}-{j}/{n} thing.id={db_item.id} thing={db_item.name} uri: {uri}"
            )


# ============= EOF =============================================
