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
from services.lexicon_helper import build_enum_from_lexicon_category

ActivityType = build_enum_from_lexicon_category("activity_type")
AddressType = build_enum_from_lexicon_category("address_type")
AnalysisMethodType = build_enum_from_lexicon_category("analysis_method_type")
CasingMaterial = build_enum_from_lexicon_category("casing_material")
CollectionMethod = build_enum_from_lexicon_category("collection_method")
ConstructionMethod = build_enum_from_lexicon_category("construction_method")
ContactType = build_enum_from_lexicon_category("contact_type")
CoordinateMethod = build_enum_from_lexicon_category("coordinate_method")
WellPurpose = build_enum_from_lexicon_category("well_purpose")
DataQuality = build_enum_from_lexicon_category("data_quality")
DataSource = build_enum_from_lexicon_category("data_source")
DepthCompletionSource = build_enum_from_lexicon_category("depth_completion_source")
DischargeSource = build_enum_from_lexicon_category("discharge_source")
DrillingFluid = build_enum_from_lexicon_category("drilling_fluid")
ElevationMethod = build_enum_from_lexicon_category("elevation_method")
EmailType = build_enum_from_lexicon_category("email_type")
ParticipantRole = build_enum_from_lexicon_category("participant_role")
Geochronology = build_enum_from_lexicon_category("geochronology")
HorizontalDatum = build_enum_from_lexicon_category("horizontal_datum")
GroundwaterLevelReason = build_enum_from_lexicon_category("groundwater_level_reason")
LimitType = build_enum_from_lexicon_category("limit_type")
MeasurementMethod = build_enum_from_lexicon_category("measurement_method")
MonitoringStatus = build_enum_from_lexicon_category("monitoring_status")
ParameterName = build_enum_from_lexicon_category("parameter_name")
Organization = build_enum_from_lexicon_category("organization")
ParameterType = build_enum_from_lexicon_category("parameter_type")
PhoneType = build_enum_from_lexicon_category("phone_type")
PublicationType = build_enum_from_lexicon_category("publication_type")
SampleQcType = build_enum_from_lexicon_category("qc_type")
QualityFlag = build_enum_from_lexicon_category("quality_flag")
Relation = build_enum_from_lexicon_category("relation")
ReleaseStatus = build_enum_from_lexicon_category("release_status")
ReviewStatus = build_enum_from_lexicon_category("review_status")
Role = build_enum_from_lexicon_category("role")
SampleMatrix = build_enum_from_lexicon_category("sample_matrix")
SampleMethod = build_enum_from_lexicon_category("sample_method")
SampleType = build_enum_from_lexicon_category("sample_type")
SpringType = build_enum_from_lexicon_category("spring_type")
Status = build_enum_from_lexicon_category("status")
ThingType = build_enum_from_lexicon_category("thing_type")
Unit = build_enum_from_lexicon_category("unit")
Vertical_datum = build_enum_from_lexicon_category("vertical_datum")
ScreenType = build_enum_from_lexicon_category("screen_type")
# ============= EOF =============================================
