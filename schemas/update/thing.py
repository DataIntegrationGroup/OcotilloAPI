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
from pydantic import BaseModel


class UpdateThing(BaseModel):
    """
    Schema for updating a thing.
    """
    # location_id: int | None = None  # Optional location ID for the thing
    name: str | None = None  # Optional name for the thing
    # group: str | None = None  # Optional group for the thing
    # description: str | None = None  # Optional description of the thing
    # tags: list[str] | None = None  # Optional tags associated with the thing


class UpdateWell(BaseModel):
    # location_id: int | None = None  # Optional location ID for the well
    # name: str | None = None  # Optional name for the well
    # api_id: str | None = None
    # ose_pod_id: str | None = None
    well_type: str | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    construction_notes: str | None = None

    # group: str | None = None  # Optional group for the well
# ============= EOF =============================================
