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
Starlette Admin configuration and initialization.

This module creates and configures the admin interface for NMSampleLocations.
"""
from starlette_admin.contrib.sqla import Admin

from admin.auth import NMSampleLocationsAuthProvider
from admin.views import (
    LocationAdmin,
    ThingAdmin,
    ObservationAdmin,
    ContactAdmin,
    SensorAdmin,
    DeploymentAdmin,
)
from db.engine import engine
from db.location import Location
from db.thing import Thing
from db.observation import Observation
from db.contact import Contact
from db.sensor import Sensor
from db.deployment import Deployment


def create_admin(app):
    """
    Create and configure Starlette Admin instance.

    This function sets up the admin interface and mounts it to the FastAPI app
    at the /admin route.

    For MS Access users: This replaces the Access database file with a web-based
    admin interface. Instead of opening a .accdb file, staff will navigate to
    https://your-domain.com/admin in their web browser.

    Args:
        app: FastAPI application instance

    Returns:
        Admin: Configured Starlette Admin instance
    """
    # Create admin instance
    admin = Admin(
        engine=engine,
        title="NM Sample Locations Admin",
        base_url="/admin",
        logo_url=None,  # TODO: Add NMBGMR logo
        auth_provider=NMSampleLocationsAuthProvider(),
        middlewares=[],  # Add custom middlewares here if needed
    )

    # Register model views
    # Geography
    admin.add_view(LocationAdmin(Location))

    # Things (Wells, Springs, etc.)
    admin.add_view(ThingAdmin(Thing))

    # Observations (Water Levels)
    admin.add_view(ObservationAdmin(Observation))

    # Contacts (Owners)
    admin.add_view(ContactAdmin(Contact))

    # Equipment
    admin.add_view(SensorAdmin(Sensor))
    admin.add_view(DeploymentAdmin(Deployment))

    # Future: Add more views here as they are implemented
    # admin.add_view(SampleAdmin)
    # admin.add_view(GroupAdmin)

    # Mount admin to app
    admin.mount_to(app)

    return admin
