# ===============================================================================
# Author:  Jake Ross
# Copyright 2025 New Mexico Bureau of Geology & Mineral Resources
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
# ===============================================================================
from typing import TYPE_CHECKING, BinaryIO

from sqlalchemy.orm import Session

from db import AssetThingAssociation, Thing, Asset
from services.gcs_helper import gcs_upload

if TYPE_CHECKING:
    from google.cloud.storage import Bucket


def upload_and_associate(
    session: Session,
    ff: BinaryIO,
    bucket: "Bucket",
    thing: Thing,
    name: str,
    **asset_args,
) -> tuple[str, str]:
    uri, blob_name = gcs_upload(ff, bucket)
    asset = Asset(
        name=name,
        storage_path=blob_name,
        storage_service="gcs",
        size=ff.size,
        uri=uri,
        **asset_args,
        # label=filename,
        # mime_type="image/png",
    )
    assoc = AssetThingAssociation()
    assoc.thing = thing
    assoc.asset = asset
    session.add(assoc)
    session.add(asset)
    return uri, blob_name


# ============= EOF =============================================
