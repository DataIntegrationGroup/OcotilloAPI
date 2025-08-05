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
from datetime import datetime

from pydantic import BaseModel


class BaseAsset(BaseModel):
    name: str
    label: str | None = None
    storage_path: str
    mime_type: str
    size: int
    url: str
    thing_id: int | None = None


# -------- CREATE ----------
class CreateAsset(BaseAsset):
    pass


# -------- RESPONSE --------
class AssetResponse(BaseAsset):
    id: int
    # name: str
    # label: str
    # storage_service: str
    # storage_path: str
    # mime_type: str
    # size: int
    created_at: datetime
    storage_service: str


# -------- UPDATE ----------
class UpdateAsset(BaseAsset):
    pass


# ============= EOF =============================================
