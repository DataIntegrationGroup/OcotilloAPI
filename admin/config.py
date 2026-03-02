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
    AquiferSystemAdmin,
    AquiferTypeAdmin,
    AssetAdmin,
    AssociatedDataAdmin,
    ChemistrySampleInfoAdmin,
    ContactAdmin,
    DataProvenanceAdmin,
    DeploymentAdmin,
    FieldActivityAdmin,
    FieldEventAdmin,
    GeologicFormationAdmin,
    GroupAdmin,
    HydraulicsDataAdmin,
    LexiconCategoryAdmin,
    LexiconTermAdmin,
    LocationAdmin,
    MajorChemistryAdmin,
    MinorTraceChemistryAdmin,
    NotesAdmin,
    ObservationAdmin,
    ParameterAdmin,
    RadionuclidesAdmin,
    SampleAdmin,
    SensorAdmin,
    SoilRockResultsAdmin,
    StratigraphyAdmin,
    SurfaceWaterDataAdmin,
    SurfaceWaterPhotosAdmin,
    ThingAdmin,
    TransducerObservationAdmin,
    WaterLevelsContinuousPressureDailyAdmin,
    WeatherPhotosAdmin,
    WeatherDataAdmin,
    FieldParametersAdmin,
)
from db import NMA_FieldParameters
from db.aquifer_system import AquiferSystem
from db.aquifer_type import AquiferType
from db.asset import Asset
from db.contact import Contact
from db.data_provenance import DataProvenance
from db.deployment import Deployment
from db.engine import engine
from db.field import FieldActivity, FieldEvent
from db.geologic_formation import GeologicFormation
from db.group import Group
from db.lexicon import LexiconCategory, LexiconTerm
from db.location import Location
from db.nma_legacy import (
    NMA_AssociatedData,
    NMA_Chemistry_SampleInfo,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
    NMA_Radionuclides,
    NMA_HydraulicsData,
    NMA_Soil_Rock_Results,
    NMA_Stratigraphy,
    NMA_SurfaceWaterData,
    NMA_WaterLevelsContinuous_Pressure_Daily,
    NMA_WeatherPhotos,
    NMA_SurfaceWaterPhotos,
    NMA_WeatherData,
)
from db.notes import Notes
from db.observation import Observation
from db.parameter import Parameter
from db.sample import Sample
from db.sensor import Sensor
from db.thing import Thing
from db.transducer import TransducerObservation


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
    # Assets
    admin.add_view(AssetAdmin(Asset))

    # Aquifer
    admin.add_view(AquiferSystemAdmin(AquiferSystem))
    admin.add_view(AquiferTypeAdmin(AquiferType))

    # Contacts
    admin.add_view(ContactAdmin(Contact))

    # Data provenance
    admin.add_view(DataProvenanceAdmin(DataProvenance))

    # Deployment / Equipment
    admin.add_view(DeploymentAdmin(Deployment))
    admin.add_view(SensorAdmin(Sensor))

    # Field
    admin.add_view(FieldActivityAdmin(FieldActivity))
    admin.add_view(FieldEventAdmin(FieldEvent))

    # Geology
    admin.add_view(GeologicFormationAdmin(GeologicFormation))

    # Geography
    admin.add_view(LocationAdmin(Location))
    # Associated data
    admin.add_view(AssociatedDataAdmin(NMA_AssociatedData))

    # Aquifer
    admin.add_view(AquiferSystemAdmin(AquiferSystem))
    admin.add_view(AquiferTypeAdmin(AquiferType))

    # Groups
    admin.add_view(GroupAdmin(Group))

    # Hydraulics
    admin.add_view(HydraulicsDataAdmin(NMA_HydraulicsData))
    admin.add_view(MinorTraceChemistryAdmin(NMA_MinorTraceChemistry))
    admin.add_view(RadionuclidesAdmin(NMA_Radionuclides))
    admin.add_view(MajorChemistryAdmin(NMA_MajorChemistry))

    # Lexicon
    admin.add_view(LexiconCategoryAdmin(LexiconCategory))
    admin.add_view(LexiconTermAdmin(LexiconTerm))

    # Notes
    admin.add_view(NotesAdmin(Notes))

    # Observations
    admin.add_view(ObservationAdmin(Observation))

    # Parameters
    admin.add_view(ParameterAdmin(Parameter))
    admin.add_view(FieldParametersAdmin(NMA_FieldParameters))

    # Samples
    admin.add_view(ChemistrySampleInfoAdmin(NMA_Chemistry_SampleInfo))
    admin.add_view(SampleAdmin(Sample))
    admin.add_view(SurfaceWaterDataAdmin(NMA_SurfaceWaterData))

    # Soil & Stratigraphy
    admin.add_view(SoilRockResultsAdmin(NMA_Soil_Rock_Results))
    admin.add_view(StratigraphyAdmin(NMA_Stratigraphy))

    # Things (Wells, Springs, etc.)
    admin.add_view(ThingAdmin(Thing))

    # Transducer observations
    admin.add_view(TransducerObservationAdmin(TransducerObservation))

    # Water Levels - Continuous (legacy)
    admin.add_view(
        WaterLevelsContinuousPressureDailyAdmin(
            NMA_WaterLevelsContinuous_Pressure_Daily
        )
    )

    # Weather
    admin.add_view(WeatherPhotosAdmin(NMA_WeatherPhotos))

    # Surface Water Photos
    admin.add_view(SurfaceWaterPhotosAdmin(NMA_SurfaceWaterPhotos))
    # Weather
    admin.add_view(WeatherDataAdmin(NMA_WeatherData))

    # Future: Add more views here as they are implemented
    # admin.add_view(SampleAdmin)
    # admin.add_view(GroupAdmin)

    # Mount admin to app
    admin.mount_to(app)

    return admin
