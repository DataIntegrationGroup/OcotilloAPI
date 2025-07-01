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
from typing import Any
from geoalchemy2.shape import to_shape
from fastadmin import register, SqlAlchemyModelAdmin, WidgetType

from db import async_database_sessionmaker
from db.base import SampleLocation, Well


@register(SampleLocation, sqlalchemy_sessionmaker=async_database_sessionmaker)
class SampleLocationsAdmin(SqlAlchemyModelAdmin):
    """
    Admin interface for SampleLocations.
    This class is a placeholder for future implementation.
    """

    list_display = ("name",)
    async def serialize_obj(self, obj: Any, list_view: bool = False) -> dict:
        """
        Serialize the SampleLocation object for display.
        This method can be customized to include additional fields or formatting.
        """
        print(f"Serializing SampleLocation object: {obj}")
        return {
            "id": obj.id,
            "name": obj.name,
            "description": obj.description,
            "point": to_shape(obj.point).wkt if obj.point else None,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
        }


@register(Well, sqlalchemy_sessionmaker=async_database_sessionmaker)
class WellAdmin(SqlAlchemyModelAdmin):
    """
    Admin interface for Well.
    This class is a placeholder for future implementation.
    """

    list_display = ("name", "location", "well_depth")
    list_display_links = ("name",)
    list_filter = ("location",)
    search_fields = ("name", "location")

    formfield_overrides = {
        "name": (WidgetType.SlugInput, {"required": True}),
        # "description": (WidgetType.Textarea, {"required": False}),
        # "well_depth": (WidgetType.NumberInput, {"required": True}),
    }


# ============= EOF =============================================
