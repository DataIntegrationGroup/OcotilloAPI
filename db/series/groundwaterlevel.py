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
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.testing.schema import mapped_column

from db.base import Base, AutoBaseMixin
from db.series.series import SeriesMixin


class GroundwaterLevelSeries(Base, AutoBaseMixin, SeriesMixin):
    """
    Represents a series of groundwater level measurements.
    """

    # Define the columns for the groundwater level series

    # Relationships can be defined here if needed
    # e.g., relationship to Location model if it exists
    pass
# ============= EOF =============================================
