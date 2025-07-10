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


class SensorResponse(BaseModel):
    id: int
    name: str
    model: str | None  # = Column(String(50))
    serial_no: str | None  # = Column(String(50))
    date_installed: datetime | None  # = Column(DateTime)
    date_removed: datetime | None  # = Column(DateTime)
    recording_interval: int | None  # = Column(Integer)
    notes: str | None  # = Column(String(50))


# ============= EOF =============================================
