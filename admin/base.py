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
import uuid
from typing import Any


import bcrypt
from fastadmin import register, SqlAlchemyModelAdmin, WidgetType
from sqlalchemy import Integer, Boolean, Text, String, update, select
from sqlalchemy.orm import Mapped, mapped_column

from models import sqlalchemy_sessionmaker, Base
from models.base import SampleLocation, Well


@register(SampleLocation, sqlalchemy_sessionmaker=sqlalchemy_sessionmaker)
class SampleLocationsAdmin(SqlAlchemyModelAdmin):
    """
    Admin interface for SampleLocations.
    This class is a placeholder for future implementation.
    """

    list_display = ("name",)


@register(Well, sqlalchemy_sessionmaker=sqlalchemy_sessionmaker)
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
