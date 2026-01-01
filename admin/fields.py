# ===============================================================================
# Copyright 2025
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
Custom fields for Starlette Admin.

Provides field handlers for complex data types like PostGIS geometry.
"""
from typing import Any

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from starlette.requests import Request
from starlette_admin import StringField

from core.constants import SRID_WGS84


class WKTField(StringField):
    """
    Custom field for GeoAlchemy2 Geometry columns.

    This field converts between PostGIS geometry (WKBElement) and human-readable
    WKT (Well-Known Text) format for display and editing in the admin interface.

    For MS Access users: Instead of entering Easting/Northing/UTM Zone in separate
    fields, you'll enter coordinates in WKT format, for example:
        POINT(-106.123 35.456)

    Note: Longitude comes first, then latitude (POINT(lon lat), not POINT(lat lon))
    """

    def serialize_value(self, request: Request, value: Any, action: str) -> str:
        """
        Convert WKBElement (PostGIS geometry) to WKT string for display in form.

        This is called when rendering the edit/create form to show the current
        value in a text input.

        Args:
            request: Starlette request object
            value: WKBElement from database (PostGIS geometry)
            action: 'list', 'detail', 'edit', or 'create'

        Returns:
            WKT string representation of geometry (e.g., "POINT(-106.123 35.456)")
        """
        if value is None:
            return ""

        try:
            # Convert WKBElement to Shapely geometry, then to WKT
            shape = to_shape(value)
            return shape.wkt
        except Exception:
            # If conversion fails, return string representation
            return str(value)

    async def parse_form_data(
        self, request: Request, form_data: dict, action: str
    ) -> Any:
        """
        Convert WKT string from form input to WKTElement for database storage.

        This is called when saving the form to convert the user's input into
        a format that can be stored in the PostGIS database.

        Args:
            request: Starlette request object
            form_data: Dictionary of form data
            action: 'edit' or 'create'

        Returns:
            WKTElement with SRID for PostGIS storage, or None if empty

        Raises:
            ValueError: If WKT string is invalid
        """
        wkt_string = form_data.get(self.name)

        if not wkt_string or wkt_string.strip() == "":
            return None

        try:
            # Parse and validate WKT string
            from shapely.wkt import loads as wkt_loads

            shape = wkt_loads(wkt_string.strip())

            # Convert to WKTElement with SRID (spatial reference identifier)
            return WKTElement(shape.wkt, srid=SRID_WGS84)
        except Exception as e:
            raise ValueError(
                f"Invalid WKT geometry: {e}. "
                f"Expected format: POINT(longitude latitude), e.g., POINT(-106.123 35.456). "
                f"Note: Longitude comes first, then latitude."
            )


class CoordinateHelpField(WKTField):
    """
    Extended WKT field with detailed help text for coordinate entry.

    This version includes comprehensive help text for users transitioning
    from MS Access UTM coordinate entry to WKT format.
    """

    def __init__(self, *args, **kwargs):
        # Add detailed help text if not provided
        if "help_text" not in kwargs:
            kwargs["help_text"] = (
                "Enter coordinates in WKT (Well-Known Text) format.\n\n"
                "Format: POINT(longitude latitude)\n"
                "Example: POINT(-106.65082 35.08352)\n\n"
                "Important:\n"
                "  * Longitude comes FIRST (negative for western hemisphere)\n"
                "  * Latitude comes SECOND\n"
                "  * No comma between values\n"
                "  * Use decimal degrees (not degrees-minutes-seconds)\n"
                "  * Coordinate system: WGS84 (SRID 4326)\n\n"
                "If you have UTM coordinates:\n"
                "  1. Use an online converter (e.g., https://www.latlong.net/utm-to-lat-long)\n"
                "  2. Enter your Easting, Northing, and UTM Zone\n"
                "  3. Convert to WGS84 lat/lon\n"
                "  4. Enter here as POINT(lon lat)"
            )

        super().__init__(*args, **kwargs)
