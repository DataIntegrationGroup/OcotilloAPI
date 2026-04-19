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
services/opensearch_aem.py

Integration between AEM ingest pipeline and OpenSearch STAC service.
Generates OpenSearch collections and items for AEM survey data.
"""

import logging
from typing import Optional, Dict, Any

from geoalchemy2.elements import WKBElement
from sqlalchemy.orm import Session

from db.aem import AemSounding
from schemas.opensearch import (
    CreateOpenSearchCollectionSchema,
    CreateOpenSearchItemSchema,
)
from services.opensearch_ingest import OpenSearchIngestService

logger = logging.getLogger(__name__)


class OpenSearchAEMService:
    """Service for integrating AEM survey data with OpenSearch STAC catalog."""

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
        self.ingest_service = OpenSearchIngestService(session)

    def create_aem_survey_collection(
        self,
        survey_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        contractor: Optional[str] = None,
        processing_stage: Optional[str] = None,
        created_by_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
    ) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Create an OpenSearch collection for an AEM survey.

        Args:
            survey_id: Unique survey identifier
            title: Human-readable survey title
            description: Survey description
            contractor: Contractor/operator name
            processing_stage: Processing stage (preliminary_inversion, final_inversion, etc.)
            created_by_id: Creator user ID
            created_by_name: Creator user name

        Returns:
            Tuple of (success, collection_id, error_message)
        """
        # Query for spatial/temporal extents from AEM soundings
        soundings = (
            self.session.query(AemSounding)
            .filter(AemSounding.survey_id == survey_id)
            .all()
        )

        if not soundings:
            return False, None, f"No soundings found for survey: {survey_id}"

        # Calculate extents
        geometries = [s.geom for s in soundings if s.geom is not None]
        if not geometries:
            return False, None, f"No geometries found for survey: {survey_id}"

        # Get bounding box from geometries
        bbox_values = self._extract_bbox_from_geometries(geometries)
        if not bbox_values:
            return False, None, "Could not extract bounding box from geometries"

        bbox_west, bbox_south, bbox_east, bbox_north = bbox_values

        # Get temporal extent from date_acquired
        dates = [s.date_acquired for s in soundings if s.date_acquired is not None]
        temporal_start = min(dates) if dates else None
        temporal_end = max(dates) if dates else None

        # Build collection schema
        collection_id = f"aem-{survey_id.lower()}"
        schema = CreateOpenSearchCollectionSchema(
            collection_id=collection_id,
            title=title or f"AEM Survey: {survey_id}",
            description=description or f"Airborne Electromagnetic survey {survey_id}",
            license="CC-BY-4.0",
            bbox_west=bbox_west,
            bbox_south=bbox_south,
            bbox_east=bbox_east,
            bbox_north=bbox_north,
            temporal_start=temporal_start,
            temporal_end=temporal_end,
            keywords=["aem", "electromagnetic", "geophysics", survey_id.lower()],
            providers={
                "name": contractor or "NMBGMR",
                "roles": ["producer"],
            },
            properties={
                "survey_id": survey_id,
                "processing_stage": processing_stage,
            },
        )

        # Ingest collection
        success, collection_id_result, error = self.ingest_service.ingest_collection(
            schema,
            created_by_id=created_by_id,
            created_by_name=created_by_name,
        )

        return success, collection_id_result, error

    def ingest_aem_soundings_as_items(
        self,
        survey_id: str,
        collection_id: int,
        created_by_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
        limit: Optional[int] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest AEM soundings as OpenSearch items.

        Args:
            survey_id: Survey identifier
            collection_id: Parent collection ID
            created_by_id: Creator user ID
            created_by_name: Creator user name
            limit: Maximum number of soundings to ingest (for testing)
            validate_only: If True, validate without committing

        Returns:
            Dict with ingest results (items_created, errors, etc.)
        """
        query = self.session.query(AemSounding).filter(
            AemSounding.survey_id == survey_id
        )

        if limit:
            query = query.limit(limit)

        soundings = query.all()

        if not soundings:
            return {
                "success": False,
                "items_created": 0,
                "errors": [{"survey_id": survey_id, "error": "No soundings found"}],
            }

        # Build item schemas
        item_schemas = []
        for sounding in soundings:
            try:
                item_schema = CreateOpenSearchItemSchema(
                    item_id=f"aem-{survey_id}-{sounding.id}",
                    collection_id=collection_id,
                    start_datetime=sounding.date_acquired,
                    end_datetime=sounding.date_acquired,
                    geometry=sounding.geom,
                    properties={
                        "line_id": sounding.line_id,
                        "record_id": sounding.record_id,
                        "layer_no": sounding.layer_no,
                        "elevation": sounding.elevation,
                        "sensor_altitude": sounding.sensor_alt,
                        "terrain_clearance": sounding.terrain_clear,
                        "resistivity": sounding.resistivity,
                        "conductivity": sounding.conductivity,
                    },
                )
                item_schemas.append(item_schema)
            except Exception as e:
                logger.warning(
                    f"Failed to create item schema for sounding {sounding.id}: {e}"
                )
                continue

        if not item_schemas:
            return {
                "success": False,
                "items_created": 0,
                "errors": [
                    {
                        "survey_id": survey_id,
                        "error": "Could not create any valid item schemas",
                    }
                ],
            }

        # Bulk ingest items
        result = self.ingest_service.bulk_ingest_items(
            item_schemas,
            created_by_id=created_by_id,
            created_by_name=created_by_name,
            validate_only=validate_only,
        )

        if not validate_only:
            self.ingest_service.commit()

        return result

    def _extract_bbox_from_geometries(
        self, geometries: list
    ) -> Optional[tuple[float, float, float, float]]:
        """
        Extract bounding box from WKBElement geometries.

        Returns:
            Tuple of (west, south, east, north) or None
        """
        try:
            lons = []
            lats = []

            for geom in geometries:
                if isinstance(geom, WKBElement):
                    # Convert WKB to Shapely geometry
                    from shapely import wkb

                    shape_geom = wkb.loads(geom.data)
                    coords = list(shape_geom.coords)
                    for lon, lat in coords:
                        lons.append(lon)
                        lats.append(lat)

            if lons and lats:
                return (min(lons), min(lats), max(lons), max(lats))

            return None
        except Exception as e:
            logger.error(f"Error extracting bbox from geometries: {e}")
            return None
