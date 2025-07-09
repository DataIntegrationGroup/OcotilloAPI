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
from sqlalchemy import ForeignKey, Integer, DateTime
from sqlalchemy.orm import declared_attr, mapped_column

from db import AutoBaseMixin, Base
from db.base import ReleaseMixin


class ObservationMixin:
    @declared_attr
    def observation_id(self):
        return mapped_column(
            Integer, ForeignKey("observation.id", ondelete="CASCADE"), nullable=False
        )


class Observation(Base, AutoBaseMixin, ReleaseMixin):

    series_id = mapped_column(
        Integer,
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
    )

    observation_timestamp = mapped_column(
        DateTime, nullable=False, index=True, doc="Timestamp of the observation"
    )


# ============= EOF =============================================
