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
    LexiconTermAdmin,
    LexiconCategoryAdmin,
    AssetAdmin,
    AquiferTypeAdmin,
    AquiferSystemAdmin,
    GroupAdmin,
    NotesAdmin,
    SampleAdmin,
    HydraulicsDataAdmin,
    ChemistrySampleInfoAdmin,
    GeologicFormationAdmin,
    DataProvenanceAdmin,
    TransducerObservationAdmin,
    FieldEventAdmin,
    FieldActivityAdmin,
    ParameterAdmin,
    SurfaceWaterDataAdmin,
)

from db.engine import engine
from db.location import Location
from db.thing import Thing
from db.observation import Observation
from db.contact import Contact
from db.sensor import Sensor
from db.deployment import Deployment
from db.lexicon import (
    LexiconTerm,
    LexiconCategory,
)
from db.asset import Asset
from db.aquifer_type import AquiferType
from db.aquifer_system import AquiferSystem
from db.group import Group
from db.notes import Notes
from db.sample import Sample
from db.nma_legacy import ChemistrySampleInfo, NMAHydraulicsData, SurfaceWaterData
from db.geologic_formation import GeologicFormation
from db.data_provenance import DataProvenance
from db.transducer import TransducerObservation
from db.field import FieldEvent, FieldActivity
from db.parameter import Parameter


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
        title="Ocotillod Admin",
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

    # Assets
    admin.add_view(AssetAdmin(Asset))

    # Aquifer
    admin.add_view(AquiferSystemAdmin(AquiferSystem))
    admin.add_view(AquiferTypeAdmin(AquiferType))

    # Groups
    admin.add_view(GroupAdmin(Group))

    # Notes
    admin.add_view(NotesAdmin(Notes))

    # Samples
    admin.add_view(SampleAdmin(Sample))
    admin.add_view(ChemistrySampleInfoAdmin(ChemistrySampleInfo))
    admin.add_view(SurfaceWaterDataAdmin(SurfaceWaterData))

    # Hydraulics
    admin.add_view(HydraulicsDataAdmin(NMAHydraulicsData))

    # Field
    admin.add_view(FieldEventAdmin(FieldEvent))
    admin.add_view(FieldActivityAdmin(FieldActivity))

    # Parameters
    admin.add_view(ParameterAdmin(Parameter))

    # Geology
    admin.add_view(GeologicFormationAdmin(GeologicFormation))

    # Data provenance
    admin.add_view(DataProvenanceAdmin(DataProvenance))

    # Transducer observations
    admin.add_view(TransducerObservationAdmin(TransducerObservation))

    # Lexicon
    admin.add_view(LexiconTermAdmin(LexiconTerm))
    admin.add_view(LexiconCategoryAdmin(LexiconCategory))

    # Future: Add more views here as they are implemented
    # admin.add_view(SampleAdmin)
    # admin.add_view(GroupAdmin)

    # Mount admin to app
    admin.mount_to(app)

    return admin
