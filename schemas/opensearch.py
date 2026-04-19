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
schemas/opensearch.py

Pydantic schemas for OpenSearch Collections and Items (STAC-compliant).
Used for request/response validation in the REST API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class OpenSearchAssetSchema(BaseModel):
    """Schema for STAC Asset."""

    asset_key: str = Field(..., description="Unique key for the asset")
    title: Optional[str] = Field(None, description="Asset title")
    description: Optional[str] = Field(None, description="Asset description")
    href: str = Field(..., description="URL/path to asset file")
    content_type: str = Field(..., description="MIME type of asset")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    roles: List[str] = Field(
        default=[], description="Asset roles (data, thumbnail, etc)"
    )
    asset_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )

    class Config:
        from_attributes = True


class CreateOpenSearchItemSchema(BaseModel):
    """Schema for creating/ingesting an OpenSearch Item."""

    item_id: str = Field(..., description="Unique item identifier")
    collection_id: int = Field(..., description="Parent collection ID")
    start_datetime: Optional[datetime] = Field(None, description="Item start datetime")
    end_datetime: Optional[datetime] = Field(None, description="Item end datetime")
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON geometry")
    assets: Optional[Dict[str, Any]] = Field(None, description="Asset definitions")
    links: Optional[Dict[str, Any]] = Field(None, description="STAC links")
    common_metadata: Optional[Dict[str, Any]] = Field(None, description="EO metadata")
    processing_level: Optional[str] = Field(None, description="Processing level")
    data_quality: Optional[Dict[str, Any]] = Field(None, description="Quality metrics")
    properties: Optional[Dict[str, Any]] = Field(
        None, description="Additional properties"
    )


class OpenSearchItemSchema(CreateOpenSearchItemSchema):
    """Schema for OpenSearch Item response."""

    id: int = Field(..., description="Database ID")
    item_type: str = Field("Feature", description="Item type")
    geoserver_layer_name: Optional[str] = None
    geoserver_feature_type: Optional[str] = None
    published: bool = Field(False, description="Published to GeoServer")
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_name: Optional[str] = None
    updated_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class CreateOpenSearchCollectionSchema(BaseModel):
    """Schema for creating/ingesting an OpenSearch Collection."""

    collection_id: str = Field(..., description="Unique collection identifier")
    title: str = Field(..., description="Collection title")
    description: Optional[str] = Field(None, description="Collection description")
    license: str = Field("proprietary", description="License SPDX identifier")

    # Spatial extent
    bbox_west: float = Field(..., description="Bounding box west")
    bbox_south: float = Field(..., description="Bounding box south")
    bbox_east: float = Field(..., description="Bounding box east")
    bbox_north: float = Field(..., description="Bounding box north")

    # Temporal extent
    temporal_start: Optional[datetime] = Field(None, description="Temporal start")
    temporal_end: Optional[datetime] = Field(None, description="Temporal end")

    # Metadata
    keywords: Optional[List[str]] = Field(None, description="Keywords")
    providers: Optional[List[Dict[str, Any]]] = Field(None, description="Providers")
    links: Optional[List[Dict[str, Any]]] = Field(None, description="Links")
    extent: Optional[Dict[str, Any]] = Field(None, description="STAC extent")
    version: Optional[str] = Field(None, description="Collection version")
    properties: Optional[Dict[str, Any]] = Field(
        None, description="Additional properties"
    )

    # GeoServer integration
    geoserver_workspace: Optional[str] = Field(None, description="GeoServer workspace")
    geoserver_store: Optional[str] = Field(None, description="GeoServer datastore")


class OpenSearchCollectionSchema(CreateOpenSearchCollectionSchema):
    """Schema for OpenSearch Collection response."""

    id: int = Field(..., description="Database ID")
    stac_version: str = Field("1.0.0", description="STAC version")
    released: bool = Field(False, description="Released status")
    deprecated: bool = Field(False, description="Deprecated status")
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_name: Optional[str] = None
    updated_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class BulkIngestSchema(BaseModel):
    """Schema for bulk ingesting collections and items."""

    collections: List[CreateOpenSearchCollectionSchema] = Field(
        default=[], description="Collections to ingest"
    )
    items: List[CreateOpenSearchItemSchema] = Field(
        default=[], description="Items to ingest"
    )
    validate_only: bool = Field(False, description="Only validate, don't persist")


class IngestResultSchema(BaseModel):
    """Response schema for ingest operations."""

    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Result message")
    collections_created: int = Field(0, description="Number of collections created")
    items_created: int = Field(0, description="Number of items created")
    errors: List[Dict[str, Any]] = Field(default=[], description="List of errors")
    warnings: List[Dict[str, Any]] = Field(default=[], description="List of warnings")


class PublishToGeoServerSchema(BaseModel):
    """Schema for publishing collection/items to GeoServer."""

    collection_ids: List[int] = Field(..., description="Collection IDs to publish")
    workspace: str = Field(..., description="GeoServer workspace")
    store: Optional[str] = Field(None, description="GeoServer datastore")
    create_workspace: bool = Field(False, description="Create workspace if missing")
