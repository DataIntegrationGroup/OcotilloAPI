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
db/opensearch.py

Database models for OpenSearch Collections and Items (STAC-compliant).
These models support ingestion and management of Earth Observation (EO) data
through GeoServer's OpenSearch REST admin API.
"""

from geoalchemy2 import Geometry
from sqlalchemy import String, JSON, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import AutoBaseMixin, PropertiesMixin, Base


class OpenSearchCollection(AutoBaseMixin, PropertiesMixin, Base):
    """
    Represents a STAC Collection for OpenSearch/GeoServer.
    Maps to GeoServer feature collection workspace.
    """

    __tablename__ = "opensearch_collection"

    # Collection metadata (STAC Collection specification)
    stac_version: Mapped[str] = mapped_column(
        String(50), default="1.0.0", nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    license: Mapped[str] = mapped_column(
        String(100), default="proprietary", nullable=False
    )

    # Collection identifiers
    collection_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # GeoServer integration
    geoserver_workspace: Mapped[str] = mapped_column(String(255), nullable=True)
    geoserver_store: Mapped[str] = mapped_column(String(255), nullable=True)

    # Spatial extent (bounding box)
    bbox_west: Mapped[float] = mapped_column(nullable=False)
    bbox_south: Mapped[float] = mapped_column(nullable=False)
    bbox_east: Mapped[float] = mapped_column(nullable=False)
    bbox_north: Mapped[float] = mapped_column(nullable=False)

    # Temporal extent
    temporal_start: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    temporal_end: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Keywords and provider info
    keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    providers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Links and extent (STAC metadata)
    links: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extent: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status and versioning
    released: Mapped[bool] = mapped_column(default=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deprecated: Mapped[bool] = mapped_column(default=False)

    # Relationship to items
    items: Mapped[list["OpenSearchItem"]] = relationship(
        "OpenSearchItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self):
        return (
            f"<OpenSearchCollection(id={self.id}, collection_id={self.collection_id})>"
        )


class OpenSearchItem(AutoBaseMixin, PropertiesMixin, Base):
    """
    Represents a STAC Item for OpenSearch/GeoServer.
    Maps to GeoServer feature (item) within a collection.
    """

    __tablename__ = "opensearch_item"

    # Item metadata (STAC Item specification)
    stac_version: Mapped[str] = mapped_column(
        String(50), default="1.0.0", nullable=False
    )

    # Item identifiers
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    collection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("opensearch_collection.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Item type and geometry
    item_type: Mapped[str] = mapped_column(
        String(100), default="Feature", nullable=False
    )
    geometry: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True
    )

    # Temporal information
    start_datetime: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_datetime: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Asset information (bands, files, etc.)
    assets: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Links (related items, parent collection, etc.)
    links: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Common metadata (eo:bands, eo:off_nadir, gsd, etc.)
    common_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # GeoServer integration
    geoserver_layer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    geoserver_feature_type: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Processing and quality metadata
    processing_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    published: Mapped[bool] = mapped_column(default=False)

    # Relationship to collection
    collection: Mapped[OpenSearchCollection] = relationship(
        "OpenSearchCollection", back_populates="items", lazy="selectin"
    )

    def __repr__(self):
        return f"<OpenSearchItem(id={self.id}, item_id={self.item_id})>"


class OpenSearchAsset(AutoBaseMixin, Base):
    """
    Represents a STAC Asset within an Item.
    Assets are individual files/resources (COG, thumbnail, metadata, etc).
    """

    __tablename__ = "opensearch_asset"

    # Asset identifiers
    asset_key: Mapped[str] = mapped_column(String(255), nullable=False)
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("opensearch_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Asset metadata
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    href: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Asset roles (e.g., 'data', 'thumbnail', 'metadata')
    roles: Mapped[list[str]] = mapped_column(JSON, default=[], nullable=False)

    # Additional asset attributes
    asset_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self):
        return f"<OpenSearchAsset(id={self.id}, asset_key={self.asset_key})>"
