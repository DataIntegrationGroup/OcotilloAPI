# ===============================================================================
# Copyright 2026 ross
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
from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from db import Asset
from services.gcs_helper import gcs_upload_to_blob_name
from services.geoserver_helper import (
    DEFAULT_WORKSPACE,
    PublishResult,
    mark_asset_publish_result,
    publish_geotiff_asset,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AEMIngestRecord:
    survey_id: str
    file_name: str
    proposed_gcs_path: str
    action: str
    normalization_needed: bool
    detected_type: str
    processing_stage: str


@dataclass(slots=True)
class AEMIngestResult:
    asset: Asset
    published: bool
    publish_result: PublishResult | None


def is_validated_aem_geotiff(record: AEMIngestRecord) -> bool:
    if record.action != "MOVE":
        return False
    if record.detected_type.lower() != "geotiff":
        return False
    expected_prefix = f"surveys/{record.survey_id}/aem/"
    return record.proposed_gcs_path.startswith(expected_prefix)


def ingest_validated_aem_asset(
    session: Session | None,
    upload: UploadFile,
    record: AEMIngestRecord,
    bucket=None,
    workspace: str = DEFAULT_WORKSPACE,
    persist_asset_metadata: bool = True,
) -> AEMIngestResult:
    mime_type = upload.content_type or mimetypes.guess_type(record.file_name)[0]
    uri, blob_name = gcs_upload_to_blob_name(
        upload, record.proposed_gcs_path, bucket=bucket
    )

    asset = _get_or_build_asset(
        session=session,
        record=record,
        blob_name=blob_name,
        mime_type=mime_type,
        uri=uri,
        size=upload.size or 0,
        persist_asset_metadata=persist_asset_metadata,
    )

    if not is_validated_aem_geotiff(record):
        result = PublishResult(
            target="geoserver",
            status="skipped",
            workspace=workspace,
            detail="Asset is not a validated AEM GeoTIFF.",
        )
        if persist_asset_metadata:
            mark_asset_publish_result(asset, result)
            assert session is not None
            session.flush()
        logger.info(
            "aem geotiff publish skipped",
            extra={
                "event": "aem_geotiff_publish_skipped",
                "asset_id": asset.id,
                "survey_id": record.survey_id,
                "workspace": workspace,
                "storage_path": asset.storage_path,
            },
        )
        return AEMIngestResult(
            asset=asset,
            published=False,
            publish_result=result,
        )

    result = publish_geotiff_asset(
        asset,
        record.survey_id,
        workspace=workspace,
    )
    if persist_asset_metadata:
        mark_asset_publish_result(asset, result)
        assert session is not None
        session.flush()
    return AEMIngestResult(
        asset=asset,
        published=result.status == "success",
        publish_result=result,
    )


def _get_or_build_asset(
    session: Session | None,
    record: AEMIngestRecord,
    blob_name: str,
    mime_type: str | None,
    uri: str,
    size: int,
    persist_asset_metadata: bool,
) -> Asset:
    if not persist_asset_metadata:
        return Asset(
            name=record.file_name,
            label=record.file_name,
            storage_path=blob_name,
            storage_service="gcs",
            mime_type=mime_type or "image/tiff",
            size=size,
            uri=uri,
            publish_target="geoserver",
        )

    if session is None:
        raise ValueError("session is required when persist_asset_metadata=True")

    asset = session.scalars(
        select(Asset).where(Asset.storage_path == blob_name)
    ).one_or_none()
    if asset is None:
        asset = Asset(
            name=record.file_name,
            label=record.file_name,
            storage_path=blob_name,
            storage_service="gcs",
            mime_type=mime_type or "image/tiff",
            size=size,
            uri=uri,
            publish_target="geoserver",
        )
        session.add(asset)
        session.flush()
        return asset

    asset.name = record.file_name
    asset.label = record.file_name
    asset.mime_type = mime_type or asset.mime_type
    asset.size = size or asset.size
    asset.uri = uri
    asset.publish_target = "geoserver"
    return asset
