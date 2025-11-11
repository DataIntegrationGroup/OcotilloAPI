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
from enum import Enum

from services.lexicon_helper import build_enum_from_lexicon_category

ActivityType: type[Enum] = build_enum_from_lexicon_category("activity_type")
AddressType: type[Enum] = build_enum_from_lexicon_category("address_type")
AnalysisMethodType: type[Enum] = build_enum_from_lexicon_category(
    "analysis_method_type"
)
CasingMaterial: type[Enum] = build_enum_from_lexicon_category("casing_material")
CollectionMethod: type[Enum] = build_enum_from_lexicon_category("collection_method")
WellConstructionMethod: type[Enum] = build_enum_from_lexicon_category(
    "well_construction_method"
)
ContactType: type[Enum] = build_enum_from_lexicon_category("contact_type")
CoordinateMethod: type[Enum] = build_enum_from_lexicon_category("coordinate_method")
WellPurpose: type[Enum] = build_enum_from_lexicon_category("well_purpose")
DataQuality: type[Enum] = build_enum_from_lexicon_category("data_quality")
DataSource: type[Enum] = build_enum_from_lexicon_category("data_source")
DepthCompletionSource: type[Enum] = build_enum_from_lexicon_category(
    "depth_completion_source"
)
DischargeSource: type[Enum] = build_enum_from_lexicon_category("discharge_source")
DrillingFluid: type[Enum] = build_enum_from_lexicon_category("drilling_fluid")
ElevationMethod: type[Enum] = build_enum_from_lexicon_category("elevation_method")
EmailType: type[Enum] = build_enum_from_lexicon_category("email_type")
ParticipantRole: type[Enum] = build_enum_from_lexicon_category("participant_role")
Geochronology: type[Enum] = build_enum_from_lexicon_category("geochronology")
HorizontalDatum: type[Enum] = build_enum_from_lexicon_category("horizontal_datum")
GroundwaterLevelReason: type[Enum] = build_enum_from_lexicon_category(
    "groundwater_level_reason"
)
LimitType: type[Enum] = build_enum_from_lexicon_category("limit_type")
MeasurementMethod: type[Enum] = build_enum_from_lexicon_category("measurement_method")
MonitoringStatus: type[Enum] = build_enum_from_lexicon_category("monitoring_status")
ParameterName: type[Enum] = build_enum_from_lexicon_category("parameter_name")
Organization: type[Enum] = build_enum_from_lexicon_category("organization")
ParameterType: type[Enum] = build_enum_from_lexicon_category("parameter_type")
PhoneType: type[Enum] = build_enum_from_lexicon_category("phone_type")
PublicationType: type[Enum] = build_enum_from_lexicon_category("publication_type")
SampleQcType: type[Enum] = build_enum_from_lexicon_category("qc_type")
QualityFlag: type[Enum] = build_enum_from_lexicon_category("quality_flag")
Relation: type[Enum] = build_enum_from_lexicon_category("relation")
ReleaseStatus: type[Enum] = build_enum_from_lexicon_category("release_status")
ReviewStatus: type[Enum] = build_enum_from_lexicon_category("review_status")
Role: type[Enum] = build_enum_from_lexicon_category("role")
SampleMatrix: type[Enum] = build_enum_from_lexicon_category("sample_matrix")
SampleMethod: type[Enum] = build_enum_from_lexicon_category("sample_method")
SampleType: type[Enum] = build_enum_from_lexicon_category("sample_type")
SpringType: type[Enum] = build_enum_from_lexicon_category("spring_type")
Status: type[Enum] = build_enum_from_lexicon_category("status")
ThingType: type[Enum] = build_enum_from_lexicon_category("thing_type")
Unit: type[Enum] = build_enum_from_lexicon_category("unit")
Vertical_datum: type[Enum] = build_enum_from_lexicon_category("vertical_datum")
ScreenType: type[Enum] = build_enum_from_lexicon_category("screen_type")
SensorType: type[Enum] = build_enum_from_lexicon_category("sensor_type")
WellPumpType: type[Enum] = build_enum_from_lexicon_category("well_pump_type")
# ============= EOF =============================================
