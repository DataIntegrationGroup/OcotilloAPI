# ===============================================================================
# Copyright 2025
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
"""
Admin views package for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on database models.
"""
from admin.views.location import LocationAdmin
from admin.views.thing import ThingAdmin
from admin.views.observation import ObservationAdmin
from admin.views.contact import ContactAdmin
from admin.views.sensor import SensorAdmin
from admin.views.deployment import DeploymentAdmin

__all__ = [
    "LocationAdmin",
    "ThingAdmin",
    "ObservationAdmin",
    "ContactAdmin",
    "SensorAdmin",
    "DeploymentAdmin",
]
