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


class CreateLocation(BaseModel):
    """
    Schema for creating a sample location.
    """

    notes: str | None = None
    point: str = "POINT(0 0)"  # Default to a point at the origin
    release_status: str | None = "draft"


class CreateGroup(BaseModel):
    """
    Schema for creating a group.
    """

    name: str


class CreateGroupThing(BaseModel):
    """
    Schema for creating a group location.
    """

    group_id: int
    thing_id: int


# ============= EOF =============================================
