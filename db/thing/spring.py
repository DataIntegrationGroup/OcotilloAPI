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
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from db.base import Base, AutoBaseMixin


class SpringThing(Base, AutoBaseMixin):
    description = Column(String(255), nullable=True)
    location_id = Column(
        Integer, ForeignKey("location.id", ondelete="CASCADE"), nullable=False
    )

    # Define a relationship to samplelocations if needed
    location = relationship("Location")


# ============= EOF =============================================
