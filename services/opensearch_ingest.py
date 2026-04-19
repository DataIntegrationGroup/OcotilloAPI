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
"""
services/opensearch_ingest.py

Service layer for ingesting OpenSearch Collections and Items.
Handles STAC-compliant data ingestion.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.opensearch import OpenSearchCollection, OpenSearchItem, OpenSearchAsset
from schemas.opensearch import (
    CreateOpenSearchCollectionSchema,
    CreateOpenSearchItemSchema,
    OpenSearchAssetSchema,
)

logger = logging.getLogger(__name__)


class OpenSearchIngestService:
    """Service for ingesting OpenSearch/STAC collections and items."""

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session

    def ingest_collection(
        self,
        schema: CreateOpenSearchCollectionSchema,
        created_by_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Ingest a single OpenSearch collection.

        Args:
            schema: Collection schema with metadata
            created_by_id: User ID for audit
            created_by_name: User name for audit

        Returns:
            Tuple of (success, collection_id, error_message)
        """
        try:
            # Check for duplicates
            existing = (
                self.session.query(OpenSearchCollection)
                .filter_by(collection_id=schema.collection_id)
                .first()
            )

            if existing:
                error = (
                    f"Collection {schema.collection_id} already exists "
                    f"(id={existing.id})"
                )
                logger.warning(error)
                return False, None, error

            # Create collection
            collection = OpenSearchCollection(
                stac_version="1.0.0",
                title=schema.title,
                description=schema.description,
                license=schema.license,
                collection_id=schema.collection_id,
                geoserver_workspace=schema.geoserver_workspace,
                geoserver_store=schema.geoserver_store,
                bbox_west=schema.bbox_west,
                bbox_south=schema.bbox_south,
                bbox_east=schema.bbox_east,
                bbox_north=schema.bbox_north,
                temporal_start=schema.temporal_start,
                temporal_end=schema.temporal_end,
                keywords=schema.keywords or [],
                providers=schema.providers or {},
                links=schema.links or [],
                extent=schema.extent or {},
                version=schema.version,
                properties=schema.properties or {},
                created_by_id=created_by_id,
                created_by_name=created_by_name,
            )

            self.session.add(collection)
            self.session.flush()

            logger.info(
                f"Ingested collection: {schema.collection_id} (id={collection.id})"
            )
            return True, collection.id, None

        except IntegrityError as e:
            self.session.rollback()
            error = f"Integrity error ingesting collection: {str(e)}"
            logger.error(error)
            return False, None, error
        except Exception as e:
            self.session.rollback()
            error = f"Error ingesting collection: {str(e)}"
            logger.error(error)
            return False, None, error

    def ingest_item(
        self,
        schema: CreateOpenSearchItemSchema,
        created_by_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Ingest a single OpenSearch item.

        Args:
            schema: Item schema with metadata
            created_by_id: User ID for audit
            created_by_name: User name for audit

        Returns:
            Tuple of (success, item_id, error_message)
        """
        try:
            # Verify collection exists
            collection = (
                self.session.query(OpenSearchCollection)
                .filter_by(id=schema.collection_id)
                .first()
            )

            if not collection:
                error = f"Collection {schema.collection_id} not found"
                logger.error(error)
                return False, None, error

            # Check for duplicates within collection
            existing = (
                self.session.query(OpenSearchItem)
                .filter_by(
                    item_id=schema.item_id,
                    collection_id=schema.collection_id,
                )
                .first()
            )

            if existing:
                error = f"Item {schema.item_id} already exists in collection"
                logger.warning(error)
                return False, None, error

            # Create item
            item = OpenSearchItem(
                stac_version="1.0.0",
                item_id=schema.item_id,
                collection_id=schema.collection_id,
                item_type="Feature",
                start_datetime=schema.start_datetime,
                end_datetime=schema.end_datetime,
                assets=schema.assets or {},
                links=schema.links or [],
                common_metadata=schema.common_metadata or {},
                processing_level=schema.processing_level,
                data_quality=schema.data_quality or {},
                properties=schema.properties or {},
                created_by_id=created_by_id,
                created_by_name=created_by_name,
            )

            # Add geometry if provided
            if schema.geometry:
                from geoalchemy2.shape import from_shape
                from shapely.geometry import shape

                try:
                    geom = shape(schema.geometry)
                    item.geometry = from_shape(geom, srid=4326)
                except Exception as e:
                    logger.warning(f"Could not parse geometry: {e}")

            self.session.add(item)
            self.session.flush()

            logger.info(
                f"Ingested item: {schema.item_id} (id={item.id}, "
                f"collection={schema.collection_id})"
            )
            return True, item.id, None

        except IntegrityError as e:
            self.session.rollback()
            error = f"Integrity error ingesting item: {str(e)}"
            logger.error(error)
            return False, None, error
        except Exception as e:
            self.session.rollback()
            error = f"Error ingesting item: {str(e)}"
            logger.error(error)
            return False, None, error

    def bulk_ingest_collections(
        self,
        schemas: List[CreateOpenSearchCollectionSchema],
        created_by_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bulk ingest multiple collections.

        Args:
            schemas: List of collection schemas
            created_by_id: User ID for audit
            created_by_name: User name for audit

        Returns:
            Result dict with counts and errors
        """
        result = {
            "success": True,
            "created": 0,
            "skipped": 0,
            "errors": [],
        }

        for schema in schemas:
            success, col_id, error = self.ingest_collection(
                schema,
                created_by_id=created_by_id,
                created_by_name=created_by_name,
            )

            if success:
                result["created"] += 1
            else:
                result["skipped"] += 1
                result["errors"].append(
                    {
                        "collection_id": schema.collection_id,
                        "error": error,
                    }
                )

        if result["errors"]:
            result["success"] = False

        return result

    def bulk_ingest_items(
        self,
        schemas: List[CreateOpenSearchItemSchema],
        created_by_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bulk ingest multiple items.

        Args:
            schemas: List of item schemas
            created_by_id: User ID for audit
            created_by_name: User name for audit

        Returns:
            Result dict with counts and errors
        """
        result = {
            "success": True,
            "created": 0,
            "skipped": 0,
            "errors": [],
        }

        for schema in schemas:
            success, item_id, error = self.ingest_item(
                schema,
                created_by_id=created_by_id,
                created_by_name=created_by_name,
            )

            if success:
                result["created"] += 1
            else:
                result["skipped"] += 1
                result["errors"].append(
                    {
                        "item_id": schema.item_id,
                        "collection_id": schema.collection_id,
                        "error": error,
                    }
                )

        if result["errors"]:
            result["success"] = False

        return result

    def add_item_assets(
        self,
        item_id: int,
        assets: List[OpenSearchAssetSchema],
    ) -> Dict[str, Any]:
        """
        Add assets to an item.

        Args:
            item_id: Item database ID
            assets: List of asset schemas

        Returns:
            Result dict
        """
        result = {
            "success": True,
            "created": 0,
            "errors": [],
        }

        try:
            item = self.session.query(OpenSearchItem).filter_by(id=item_id).first()

            if not item:
                result["success"] = False
                result["errors"].append({"error": f"Item {item_id} not found"})
                return result

            for asset_schema in assets:
                try:
                    asset = OpenSearchAsset(
                        asset_key=asset_schema.asset_key,
                        item_id=item_id,
                        title=asset_schema.title,
                        description=asset_schema.description,
                        href=asset_schema.href,
                        content_type=asset_schema.content_type,
                        file_size=asset_schema.file_size,
                        roles=asset_schema.roles,
                        asset_metadata=asset_schema.asset_metadata,
                    )
                    self.session.add(asset)
                    result["created"] += 1
                except Exception as e:
                    result["success"] = False
                    result["errors"].append(
                        {
                            "asset_key": asset_schema.asset_key,
                            "error": str(e),
                        }
                    )

            self.session.flush()

        except Exception as e:
            self.session.rollback()
            result["success"] = False
            result["errors"].append({"error": f"Failed to add assets: {str(e)}"})

        return result

    def get_collection(self, collection_id: int) -> Optional[OpenSearchCollection]:
        """Get collection by ID."""
        return (
            self.session.query(OpenSearchCollection).filter_by(id=collection_id).first()
        )

    def get_items_by_collection(
        self,
        collection_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[OpenSearchItem], int]:
        """
        Get items for a collection with pagination.

        Returns:
            Tuple of (items, total_count)
        """
        query = self.session.query(OpenSearchItem).filter_by(
            collection_id=collection_id
        )
        total = query.count()
        items = query.limit(limit).offset(offset).all()
        return items, total

    def commit(self) -> bool:
        """Commit all pending changes."""
        try:
            self.session.commit()
            logger.info("Committed all changes")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to commit: {e}")
            return False
