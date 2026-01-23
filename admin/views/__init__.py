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

from admin.views.asset import AssetAdmin
from admin.views.aquifer_system import AquiferSystemAdmin
from admin.views.aquifer_type import AquiferTypeAdmin
from admin.views.chemistry_sampleinfo import ChemistrySampleInfoAdmin
from admin.views.contact import ContactAdmin
from admin.views.data_provenance import DataProvenanceAdmin
from admin.views.deployment import DeploymentAdmin
from admin.views.field import (
    FieldActivityAdmin,
    FieldEventAdmin,
    FieldEventParticipantAdmin,
)
from admin.views.geologic_formation import GeologicFormationAdmin
from admin.views.group import GroupAdmin
from admin.views.hydraulicsdata import HydraulicsDataAdmin
from admin.views.lexicon import LexiconCategoryAdmin, LexiconTermAdmin
from admin.views.location import LocationAdmin
from admin.views.minor_trace_chemistry import MinorTraceChemistryAdmin
from admin.views.notes import NotesAdmin
from admin.views.observation import ObservationAdmin
from admin.views.parameter import ParameterAdmin
from admin.views.radionuclides import RadionuclidesAdmin
from admin.views.sample import SampleAdmin
from admin.views.sensor import SensorAdmin
from admin.views.stratigraphy import StratigraphyAdmin
from admin.views.surface_water import SurfaceWaterDataAdmin
from admin.views.thing import ThingAdmin
from admin.views.transducer_observation import TransducerObservationAdmin

__all__ = [
    "AssetAdmin",
    "AquiferSystemAdmin",
    "AquiferTypeAdmin",
    "ChemistrySampleInfoAdmin",
    "ContactAdmin",
    "DataProvenanceAdmin",
    "DeploymentAdmin",
    "FieldActivityAdmin",
    "FieldEventAdmin",
    "FieldEventParticipantAdmin",
    "GeologicFormationAdmin",
    "GroupAdmin",
    "HydraulicsDataAdmin",
    "LexiconCategoryAdmin",
    "LexiconTermAdmin",
    "LocationAdmin",
    "MinorTraceChemistryAdmin",
    "NotesAdmin",
    "ObservationAdmin",
    "ParameterAdmin",
    "RadionuclidesAdmin",
    "SampleAdmin",
    "SensorAdmin",
    "StratigraphyAdmin",
    "SurfaceWaterDataAdmin",
    "ThingAdmin",
    "TransducerObservationAdmin",
]
