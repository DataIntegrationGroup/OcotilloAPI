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

from schemas import ORMBaseModel


class BaseAsset(BaseModel):
    name: str
    label: str | None = None
    storage_path: str
    mime_type: str
    size: int
    uri: str


# -------- CREATE ----------
class CreateAsset(BaseAsset):
    thing_id: int | None = None


# -------- RESPONSE --------
class AssetResponse(ORMBaseModel, BaseAsset):
    storage_service: str
    signed_url: str | None = None


# -------- UPDATE ----------
class UpdateAsset(BaseAsset):
    pass


# ============= EOF =============================================
