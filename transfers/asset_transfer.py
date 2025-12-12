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

from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from db import Thing
from services.asset_helper import upload_and_associate
from services.gcs_helper import (
    get_storage_bucket,
    get_storage_client,
)
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv, filter_to_valid_point_ids


class AssetTransferer(Transferer):
    def __init__(self, *args, **kw):
        self.source_table = "WellPhotos"
        super().__init__(*args, **kw)
        self._client = get_storage_client()
        self._bucket = get_storage_bucket(self._client)
        logger.info(f"Using bucket {self._bucket.name}")
        self.chunk_size = 20

    def _get_dfs(self):
        input_df = read_csv(self.source_table)
        cleaned_df = filter_to_valid_point_ids(input_df)
        return input_df, cleaned_df

    def _transfer_hook(self, session: Session):
        added_pointid = []
        for i, row in enumerate(self.cleaned_df.itertuples()):
            if row.PointID in added_pointid:
                continue

            added_pointid.append(row.PointID)
            well = (
                session.query(Thing)
                .filter(Thing.name == row.PointID, Thing.thing_type == "water well")
                .one_or_none()
            )
            self._asset_step(session, i, well)
            session.commit()

    def _asset_step(self, session, i, db_item):
        df = self.cleaned_df
        photos = df[df["PointID"] == db_item.name]
        if photos.empty:
            photos = df[df["PointID"] == db_item.name.replace("-", "")]
            if photos.empty:
                logger.info(f"No photos found for PointID: {db_item.name}")
                return

        n = len(photos)
        for j, row in enumerate(photos.itertuples()):
            photo_path = row.OLEPath
            srcblob = self._bucket.get_blob(f"nma-photos/{photo_path}")
            if not srcblob:
                self._capture_error(
                    db_item.name, f"No photo found for {photo_path}", "OLEPath"
                )
                continue

            head, filename = srcblob.name.split("/")
            f = srcblob.download_as_bytes()
            ff = UploadFile(file=io.BytesIO(f), filename=filename, size=len(f))

            uri = upload_and_associate(
                session,
                ff,
                self._bucket,
                db_item,
                filename,
                **{"label": filename, "mime_type": "image/png"},
            )

            logger.info(
                f"Added asset {i}-{j}/{n} thing.id={db_item.id} thing={db_item.name} uri: {uri}"
            )


# ============= EOF =============================================
