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
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import requests
from db import Asset

logger = logging.getLogger(__name__)
DEFAULT_WORKSPACE = "nmbgmr"
DEFAULT_TIMEOUT_SECS = float(os.environ.get("GEOSERVER_TIMEOUT_SECS", "30"))
URL_PREFIXES = ("http://", "https://")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "raster"


def _asset_stem(asset: Asset) -> str:
    return os.path.splitext(asset.name or asset.storage_path)[0]


def make_geoserver_store_name(asset: Asset, survey_id: str) -> str:
    return _slugify(f"{survey_id}_{_asset_stem(asset)}")


def make_geoserver_layer_name(asset: Asset, survey_id: str) -> str:
    return _slugify(f"{survey_id}_{_asset_stem(asset)}")


@dataclass(slots=True)
class PublishResult:
    target: str
    status: str
    workspace: str
    store_name: str | None = None
    layer_name: str | None = None
    http_status: int | None = None
    detail: str | None = None


class GeoServerPublisher:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
        geoserver_client=None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("GEOSERVER_URL", "")).rstrip("/")
        self.username = username or os.environ.get("GEOSERVER_USERNAME")
        self.password = password or os.environ.get("GEOSERVER_PASSWORD")
        self.timeout = timeout or DEFAULT_TIMEOUT_SECS
        self._geoserver_client = geoserver_client

    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def _get_client(self):
        if self._geoserver_client is not None:
            return self._geoserver_client

        try:
            from geo.Geoserver import Geoserver
        except ImportError as exc:
            message = (
                "geoserver-rest is not installed. Add it to the "
                "environment to enable GeoServer publishing."
            )
            raise RuntimeError(message) from exc

        return Geoserver(
            self.base_url,
            username=self.username,
            password=self.password,
        )

    def _resolve_source_path(self, asset: Asset) -> str:
        source_root = os.environ.get("GEOSERVER_RASTER_SOURCE_ROOT", "").rstrip("/")
        if source_root:
            return os.path.join(source_root, asset.storage_path.lstrip("/"))

        if asset.uri and not asset.uri.startswith(URL_PREFIXES):
            return asset.uri

        if os.path.isabs(asset.storage_path):
            return asset.storage_path

        raise RuntimeError(
            "GeoServer raster publishing requires a local or mounted "
            "raster path. Set GEOSERVER_RASTER_SOURCE_ROOT to the "
            "filesystem root that contains the uploaded rasters."
        )

    def publish_geotiff_asset(
        self, asset: Asset, survey_id: str, workspace: str = DEFAULT_WORKSPACE
    ) -> PublishResult:
        store_name = make_geoserver_store_name(asset, survey_id)
        layer_name = make_geoserver_layer_name(asset, survey_id)
        if not self.is_configured():
            logger.info(
                (
                    "GeoServer publish skipped for asset_id=%s "
                    "store=%s layer=%s because GeoServer "
                    "configuration is incomplete."
                ),
                getattr(asset, "id", None),
                store_name,
                layer_name,
            )
            return PublishResult(
                target="geoserver",
                status="disabled",
                workspace=workspace,
                store_name=store_name,
                layer_name=layer_name,
                detail="GeoServer configuration is incomplete.",
            )

        client = self._get_client()
        try:
            logger.info(
                (
                    "Ensuring GeoServer workspace=%s exists before "
                    "publishing store=%s layer=%s."
                ),
                workspace,
                store_name,
                layer_name,
            )
            self._ensure_workspace(client, workspace)
            store_created = self._ensure_coverage_store(
                client, workspace, store_name, asset
            )
            detail = None
            status = "success"
            http_status = 200
            if not store_created:
                detail = "GeoServer layer already exists."
                logger.info(
                    (
                        "GeoServer publish reused existing coverage "
                        "store for asset_id=%s workspace=%s "
                        "store=%s layer=%s."
                    ),
                    getattr(asset, "id", None),
                    workspace,
                    store_name,
                    layer_name,
                )
            else:
                logger.info(
                    (
                        "GeoServer publish created coverage store "
                        "for asset_id=%s workspace=%s store=%s "
                        "layer=%s from %s."
                    ),
                    getattr(asset, "id", None),
                    workspace,
                    store_name,
                    layer_name,
                    self._resolve_source_path(asset),
                )
            return PublishResult(
                target="geoserver",
                status=status,
                workspace=workspace,
                store_name=store_name,
                layer_name=layer_name,
                http_status=http_status,
                detail=detail,
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            logger.warning(
                (
                    "GeoServer publish failed for asset_id=%s "
                    "workspace=%s store=%s layer=%s: %s"
                ),
                getattr(asset, "id", None),
                workspace,
                store_name,
                layer_name,
                exc,
            )
            return PublishResult(
                target="geoserver",
                status="failed",
                workspace=workspace,
                store_name=store_name,
                layer_name=layer_name,
                http_status=status_code,
                detail=str(exc),
            )

    def _ensure_workspace(self, client, workspace: str) -> None:
        try:
            client.get_workspace(workspace=workspace)
            logger.info("GeoServer workspace %s already exists.", workspace)
        except Exception:
            logger.info(
                "GeoServer workspace %s does not exist; creating it.",
                workspace,
            )
            client.create_workspace(workspace=workspace)
            logger.info("GeoServer workspace %s created.", workspace)

    def _ensure_coverage_store(
        self,
        client,
        workspace: str,
        store_name: str,
        asset: Asset,
    ) -> bool:
        existing_store = None
        try:
            existing_store = client.get_coveragestore(
                coveragestore_name=store_name,
                workspace=workspace,
            )
        except Exception:
            existing_store = None

        if existing_store:
            logger.info(
                "GeoServer coverage store %s already exists in workspace %s.",
                store_name,
                workspace,
            )
            return False

        # Inference from geoserver-rest docs: create_coveragestore handles
        # upload-style publication, but for mounted rasters already present
        # on the GeoServer host we must register them through the external
        # GeoTIFF REST endpoint instead.
        source_path = self._resolve_source_path(asset)
        logger.info(
            (
                "Registering external GeoTIFF coverage store %s in "
                "workspace %s from %s."
            ),
            store_name,
            workspace,
            source_path,
        )
        self._register_external_geotiff(
            workspace=workspace,
            store_name=store_name,
            source_path=source_path,
        )
        logger.info(
            "GeoServer coverage store %s registered in workspace %s.",
            store_name,
            workspace,
        )
        return True

    def _register_external_geotiff(
        self,
        workspace: str,
        store_name: str,
        source_path: str,
    ) -> None:
        response = requests.put(
            (
                f"{self.base_url}/rest/workspaces/{workspace}/"
                f"coveragestores/{store_name}/external.geotiff"
            ),
            data=source_path,
            headers={"Content-Type": "text/plain"},
            auth=(self.username, self.password),
            timeout=self.timeout,
        )
        if response.status_code not in {200, 201, 202}:
            raise RuntimeError(
                "GeoServer external GeoTIFF registration failed with "
                f"status {response.status_code}: {response.text}"
            )


def publish_geotiff_asset(
    asset: Asset,
    survey_id: str,
    workspace: str = DEFAULT_WORKSPACE,
    publisher: GeoServerPublisher | None = None,
) -> PublishResult:
    publisher = publisher or GeoServerPublisher()
    store_name = make_geoserver_store_name(asset, survey_id)
    layer_name = make_geoserver_layer_name(asset, survey_id)
    logger.info(
        (
            "Starting GeoServer publish for asset_id=%s workspace=%s "
            "store=%s layer=%s storage_path=%s."
        ),
        getattr(asset, "id", None),
        workspace,
        store_name,
        layer_name,
        getattr(asset, "storage_path", None),
        extra={
            "event": "geoserver_publish_start",
            "asset_id": getattr(asset, "id", None),
            "survey_id": survey_id,
            "workspace": workspace,
            "store_name": store_name,
            "layer_name": layer_name,
        },
    )
    result = publisher.publish_geotiff_asset(asset, survey_id, workspace=workspace)
    log_fn = logger.info if result.status in {"success", "disabled"} else logger.warning
    log_fn(
        (
            "Finished GeoServer publish for asset_id=%s workspace=%s "
            "store=%s layer=%s with status=%s detail=%s."
        ),
        getattr(asset, "id", None),
        result.workspace,
        result.store_name,
        result.layer_name,
        result.status,
        result.detail,
        extra={
            "event": "geoserver_publish_finished",
            "asset_id": getattr(asset, "id", None),
            "survey_id": survey_id,
            "workspace": result.workspace,
            "store_name": result.store_name,
            "layer_name": result.layer_name,
            "publish_status": result.status,
            "http_status": result.http_status,
            "detail": result.detail,
        },
    )
    return result


def mark_asset_publish_result(asset: Asset, result: PublishResult) -> None:
    asset.publish_target = result.target
    asset.publish_status = result.status
    asset.publish_workspace = result.workspace
    asset.publish_store_name = result.store_name
    asset.publish_layer_name = result.layer_name
    asset.publish_last_attempt_at = datetime.now(UTC)
    asset.publish_last_error = result.detail if result.status != "success" else None
