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

import logging
import time

from fastapi import APIRouter, Depends, Form, UploadFile, File
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from starlette.concurrency import run_in_threadpool
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_409_CONFLICT,
)

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    viewer_dependency,
    admin_dependency,
    editor_dependency,
)
from db import Thing
from db.asset import Asset, AssetThingAssociation
from schemas.asset import AssetResponse, CreateAsset, UpdateAsset
from services.audit_helper import audit_add
from services.crud_helper import model_patcher, model_deleter
from services.env import get_bool_env
from services.exceptions_helper import PydanticStyleException
from services.query_helper import simple_get_by_id

router = APIRouter(prefix="/asset", tags=["asset"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File upload constraints
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/tiff",
        "application/pdf",
        "text/plain",
    }
)

MAX_UPLOAD_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB


def is_debug_timing_enabled() -> bool:
    return bool(get_bool_env("API_DEBUG_TIMING", False))


def get_storage_bucket():
    from services.gcs_helper import (
        get_storage_bucket as get_gcs_storage_bucket,
    )

    started_at = time.perf_counter()
    try:
        return get_gcs_storage_bucket()
    finally:
        if is_debug_timing_enabled():
            logger.info(
                "asset storage bucket resolved",
                extra={
                    "event": "asset_storage_bucket_resolved",
                    "bucket_resolution_ms": round(
                        (time.perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )


def database_error_handler(payload: CreateAsset, error: ProgrammingError) -> None:
    """
    Handle errors raised by the database when adding or updating a asset.
    """

    error_message = error.orig.args[0]["M"]

    if (
        error_message == 'null value in column "thing_id" of relation '
        '"asset_thing_association" violates not-null constraint'
    ):
        """
        Developer's notes

        this error occurs because the thing_id is set by the Thing record that
        is retrieved, so if there is no Thing with thing_id it tries to set
        thing_id to None in the AssetThingAssociation table
        """
        detail = {
            "loc": ["body", "thing_id"],
            "msg": f"Thing with ID {payload.thing_id} not found.",
            "type": "value_error",
            "input": {"thing_id": payload.thing_id},
        }

    raise PydanticStyleException(
        status_code=HTTP_409_CONFLICT,
        detail=[detail],
    )


# POST =======================================================================
@router.post(
    "/upload",
    status_code=HTTP_201_CREATED,
)
async def upload_asset(
    user: admin_dependency,
    bucket=Depends(get_storage_bucket),
    file: UploadFile = File(...),
) -> dict:
    from services.gcs_helper import gcs_upload

    # GCS client calls are synchronous and can block for large uploads.
    request_started_at = time.perf_counter()
    uri, blob_name, _created = await run_in_threadpool(gcs_upload, file, bucket)
    if is_debug_timing_enabled():
        logger.info(
            "asset upload request completed",
            extra={
                "event": "asset_upload_request_completed",
                "upload_filename": file.filename,
                "content_type": file.content_type,
                "upload_request_ms": round(
                    (time.perf_counter() - request_started_at) * 1000,
                    2,
                ),
            },
        )
    return {
        "uri": uri,
        "storage_path": blob_name,
    }


@router.post("/upload-and-record", status_code=HTTP_201_CREATED)
async def upload_and_record_asset(
    user: admin_dependency,
    session: session_dependency,
    bucket=Depends(get_storage_bucket),
    file: UploadFile = File(...),
    thing_id: int = Form(...),
    label: str | None = Form(None),
    name: str | None = Form(None),
) -> AssetResponse:
    """
    Upload a digital asset to GCS and record it in the database in one step.

    Accepts a multipart/form-data request containing the file and optional
    metadata. Validates the file type and size before uploading. If the same
    file has already been uploaded for the same Thing, the existing record is
    returned instead of creating a duplicate.

    Args:
        user: Authenticated admin user performing the upload.
        session: Active database session.
        bucket: GCS storage bucket resolved via dependency injection.
        file: The file to upload. Accepted MIME types: JPEG, PNG, GIF, WebP,
            TIFF (images); PDF (documents); plain text. Max size: 250 MB.
        thing_id: ID of the Thing (e.g. a well) this asset belongs to.
        label: Optional human-readable label for the asset.
        name: Optional asset name. Defaults to the uploaded filename.

    Returns:
        AssetResponse: The newly created (or pre-existing duplicate) asset
            record, including its database ID, GCS URI, and storage path.

    Raises:
        400 Bad Request: File MIME type is not in the allowed set, or the
            file size exceeds 250 MB.
        409 Conflict: No Thing with the given thing_id exists.
    """
    from services.gcs_helper import gcs_upload, check_asset_exists

    # ── 1. Validate file type ────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise PydanticStyleException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": ["file"],
                    "msg": (
                        f"Unsupported file type '{file.content_type}'. "
                        f"Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}."
                    ),
                    "type": "value_error",
                    "input": {"content_type": file.content_type},
                }
            ],
        )

    # ── 2. Validate file size ────────────────────────────────────────────────
    # file.size is set by FastAPI during multipart parsing.
    # Fall back to seeking when unavailable (e.g. streaming clients).
    file_size = file.size
    if file_size is None:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise PydanticStyleException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": ["file"],
                    "msg": (
                        f"File size {file_size} bytes exceeds the maximum "
                        f"upload size of {MAX_UPLOAD_SIZE_BYTES} bytes (250 MB)."
                    ),
                    "type": "value_error",
                    "input": {"size": file_size},
                }
            ],
        )

    # ── 3. Validate the Thing exists (before upload to avoid orphaned blobs) ─
    thing = session.get(Thing, thing_id)
    if thing is None:
        raise PydanticStyleException(
            status_code=HTTP_409_CONFLICT,
            detail=[
                {
                    "loc": ["body", "thing_id"],
                    "msg": f"Thing with ID {thing_id} not found.",
                    "type": "value_error",
                    "input": {"thing_id": thing_id},
                }
            ],
        )

    # ── 4. Upload file to GCS (blocking I/O — run in thread pool) ────────────
    # `created` is True only when this request actually wrote the blob — when
    # gcs_upload deduplicates against an existing hash-named object it is
    # False, meaning the blob is potentially shared by other Assets.
    uri, blob_name, blob_created_by_request = await run_in_threadpool(
        gcs_upload, file, bucket
    )

    # ── 5. Return existing record for duplicate file + thing combinations ─────
    existing = check_asset_exists(session, blob_name, thing_id=thing_id)
    if existing:
        return existing

    # ── 6. Persist the Asset record ───────────────────────────────────────────
    asset = Asset(
        name=name or file.filename,
        label=label,
        storage_path=blob_name,
        storage_service="gcs",
        mime_type=file.content_type,
        size=file_size,
        uri=uri,
    )
    audit_add(user, asset)

    # ── 7. Link the Asset to the Thing ───────────────────────────────────────
    assoc = AssetThingAssociation()
    audit_add(user, assoc)
    assoc.thing = thing
    assoc.asset = asset

    # If the write fails BEFORE commit, roll back. Only delete the blob if
    # this request actually created it AND no Asset row references it after
    # rollback; otherwise we would orphan another Thing's Asset that shares
    # the same hash-named blob (gcs_upload deduplicates by content hash).
    # session.refresh() is intentionally outside the cleanup block: it runs
    # AFTER the commit succeeded, so a refresh failure must not delete the
    # blob — the committed Asset row would then point at a missing object.
    try:
        session.add(asset)
        session.add(assoc)
        session.commit()
    except Exception:
        # Best-effort rollback. If rollback itself raises, log and continue
        # so the original DB exception still propagates as the request error.
        try:
            session.rollback()
        except Exception:
            logger.exception(
                "session.rollback() failed after asset commit failure; "
                "original exception will still be re-raised"
            )
        if blob_created_by_request:
            # Reference check is itself best-effort: if it raises, do NOT
            # delete the blob (we cannot confirm it is unreferenced), just
            # log and leave it in place.
            try:
                still_referenced = session.scalars(
                    select(Asset).where(Asset.storage_path == blob_name)
                ).first()
            except Exception:
                logger.warning(
                    "Could not verify blob references; skipping cleanup for %s",
                    blob_name,
                    exc_info=True,
                )
                still_referenced = object()  # sentinel: assume referenced
            if still_referenced is None:
                try:
                    await run_in_threadpool(bucket.blob(blob_name).delete)
                except Exception:
                    logger.warning(
                        "Failed to clean up uploaded blob after DB failure: %s",
                        blob_name,
                        exc_info=True,
                    )
            else:
                logger.info(
                    "Skipping blob cleanup; another Asset still references %s",
                    blob_name,
                )
        raise

    session.refresh(asset)
    return asset


@router.post("", status_code=HTTP_201_CREATED)
async def add_asset(
    user: admin_dependency,
    session: session_dependency,
    asset_data: CreateAsset,
) -> AssetResponse:

    try:
        data = asset_data.model_dump()
        thing_id = data.pop("thing_id", None)

        storage_path = data["storage_path"]

        # check to see if an asset entry already exists for
        # this storage path and thing_id
        from services.gcs_helper import check_asset_exists

        existing_asset = check_asset_exists(
            session,
            storage_path,
            thing_id=thing_id,
        )
        if existing_asset:
            # If an asset already exists, return it
            return existing_asset

        data["storage_service"] = "gcs"
        asset = Asset(**data)
        audit_add(user, asset)

        if thing_id:
            assoc = AssetThingAssociation()
            audit_add(user, assoc)
            thing = session.get(Thing, thing_id)
            assoc.thing = thing
            assoc.asset = asset
            session.add(assoc)

        session.add(asset)
        session.commit()
        session.refresh(asset)

        return asset
    except ProgrammingError as e:
        database_error_handler(asset_data, e)


# GET ========================================================================

"""
Developer's notes

Do not generate signed urls when listing ALL assets. There is a reason to
generate signed urls when listing assets for a given `thing_id` because this
is used by the front end to display a gallery of images all at once. This is
the only case in which signed urls should be generated for a list of assets. A
signed url is always generated when retrieving assets individually
"""


@router.get("")
async def list_assets(
    user: viewer_dependency,
    session: session_dependency,
    thing_id: int = None,
) -> CustomPage[AssetResponse]:
    """
    List all assets or assets associated with a specific thing.
    """
    sql = select(Asset)
    if thing_id:
        sql = sql.join(AssetThingAssociation).where(
            AssetThingAssociation.thing_id == thing_id
        )

    def transformer(records: list[Asset]):
        if thing_id is not None:
            from services.gcs_helper import add_signed_url

            bucket = get_storage_bucket()
            records = [add_signed_url(ai, bucket) for ai in records]
        return records

    return paginate(query=sql, conn=session, transformer=transformer)


@router.get("/{asset_id}")
async def get_asset(
    user: viewer_dependency,
    asset_id: int,
    session: session_dependency,
    bucket=Depends(get_storage_bucket),
) -> AssetResponse:
    """
    Retrieve an asset by its ID.
    """
    from services.gcs_helper import add_signed_url

    asset = simple_get_by_id(session, Asset, asset_id)

    asset = await run_in_threadpool(add_signed_url, asset, bucket)
    return asset


# PATCH ======================================================================
@router.patch("/{asset_id}")
async def update_asset(
    asset_id: int,
    session: session_dependency,
    asset_data: UpdateAsset,
    user: editor_dependency,
):
    """
    Update an existing asset.
    """
    return model_patcher(session, Asset, asset_id, asset_data, user=user)


# DELETE =====================================================================


@router.delete("/{asset_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: int, session: session_dependency, user: admin_dependency
):

    # TODO: Interesting issue here. We don't have a way of tracking
    # who deleted a record.
    return model_deleter(session, Asset, asset_id)


@router.delete(
    "/{asset_id}/remove",
    status_code=HTTP_204_NO_CONTENT,
)
async def remove_asset(
    user: admin_dependency,
    asset_id: int,
    session: session_dependency,
    bucket=Depends(get_storage_bucket),
):
    from services.gcs_helper import gcs_remove

    asset = simple_get_by_id(session, Asset, asset_id)
    gcs_remove(asset.uri, bucket)


# ============= EOF =============================================
