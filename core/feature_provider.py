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
"""Feature provider that publishes field-level prose alongside the columns.

pygeoapi's PostgreSQL provider reflects a table and reports each column's
JSON Schema type and format. It does not read column comments, and there is
no hook for documentation, so /collections/{id}/schema publishes bare column
names. This subclass annotates the reflected fields from
core/ogc-field-descriptions.yml on the way out.

Read docs/ogc-field-descriptions.md before changing this.
"""

import logging

from geoalchemy2.functions import (
    ST_Intersects,
    ST_MakeEnvelope,
    ST_MakePoint,
    ST_SetSRID,
)
from pygeoapi.provider.sql import PostgreSQLProvider
from shapely.geometry import Point, mapping

from core.ogc_field_metadata import describe_fields

LOGGER = logging.getLogger(__name__)


class DescribedPostgreSQLProvider(PostgreSQLProvider):
    """PostgreSQLProvider that annotates reflected columns with prose."""

    def __init__(self, provider_def):
        self.x_field = provider_def.get("x_field")
        self.y_field = provider_def.get("y_field")
        super().__init__(provider_def)

    def _select_properties_clause(self, select_properties, skip_geometry):
        if self.geom is None:
            # Include coordinates even when the caller selects other properties.
            if select_properties and not skip_geometry:
                select_properties = list(
                    dict.fromkeys([*select_properties, self.x_field, self.y_field])
                )
            skip_geometry = True
        return super()._select_properties_clause(select_properties, skip_geometry)

    def _sqlalchemy_to_feature(
        self, item, crs_transform_out=None, select_properties=None
    ):
        feature = super()._sqlalchemy_to_feature(
            item, crs_transform_out, select_properties
        )
        if self.geom is None:
            x = item.__dict__.get(self.x_field)
            y = item.__dict__.get(self.y_field)
            if x is not None and y is not None:
                point = Point(x, y)
                if crs_transform_out is not None:
                    point = crs_transform_out(point)
                feature["geometry"] = mapping(point)
        return feature

    def _get_bbox_filter(self, bbox):
        if self.geom is not None or not bbox:
            return super()._get_bbox_filter(bbox)
        point = ST_SetSRID(
            ST_MakePoint(
                getattr(self.table_model, self.x_field),
                getattr(self.table_model, self.y_field),
            ),
            4326,
        )
        return ST_Intersects(ST_MakeEnvelope(*bbox, 4326), point)

    def get_fields(self):
        """Reflect the table, then annotate the result.

        The write back into ``self._fields`` is the point of this method, not
        an optimisation. ``BaseProvider.fields`` -- which is what
        ``get_collection_schema`` and ``get_collection_queryables`` actually
        read -- returns ``self._fields`` directly and never calls
        ``get_fields()``. A subclass that only returned an annotated copy
        would be silently ignored, since ``GenericSQLProvider.__init__``
        populates ``_fields`` with the raw reflection at construction.
        """
        fields = super().get_fields()
        if fields and not getattr(self, "_fields_described", False):
            self._fields = describe_fields(self.table, fields)
            # super().get_fields() short-circuits on a populated _fields, so
            # without this flag a later call would re-describe the annotated
            # dict. Harmless today (describe_fields is idempotent) but it
            # would quietly depend on that staying true.
            self._fields_described = True
        return self._fields
