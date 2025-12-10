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
from typing import List

from pydantic import BaseModel, model_validator, Field, field_validator

from core.enums import (
    WellPurpose,
    CasingMaterial,
    SpringType,
    ScreenType,
    Organization,
    MonitoringFrequency,
    WellConstructionMethod,
    WellPumpType,
    FormationCode,
)
from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel, PastOrTodayDate
from schemas.group import GroupResponse
from schemas.location import LocationGeoJSONResponse
from schemas.notes import NoteResponse, CreateNote
from schemas.permission_history import PermissionHistoryResponse


# -------- VALIDATE ----------


class ValidateWell(BaseModel):
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_casing_depth: float | None = None  # in feet
    measuring_point_height: float | None = None

    @model_validator(mode="after")
    def validate_values(self):
        if self.hole_depth is not None:
            if self.well_depth is not None and self.well_depth > self.hole_depth:
                raise ValueError(
                    "well depth must be less than than or equal to hole depth"
                )
            elif (
                self.well_casing_depth is not None
                and self.well_casing_depth > self.hole_depth
            ):
                raise ValueError(
                    "well casing depth must be less than or equal to hole depth"
                )

        # if self.measuring_point_height is not None:
        #     if (
        #         self.hole_depth is not None
        #         and self.measuring_point_height >= self.hole_depth
        #     ):
        #         raise ValueError("measuring point height must be less than hole depth")
        #     elif (
        #         self.well_casing_depth is not None
        #         and self.measuring_point_height >= self.well_casing_depth
        #     ):
        #         raise ValueError(
        #             "measuring point height must be less than well casing depth"
        #         )
        #     elif (
        #         self.well_depth is not None
        #         and self.measuring_point_height >= self.well_depth
        #     ):
        #         raise ValueError("measuring point height must be less than well depth")

        return self


# -------- CREATE ----------
class CreateThingIdLink(BaseModel):
    """
    Schema for creating a link between a thing and its ID.
    """

    thing_id: int
    relation: str
    alternate_id: str
    alternate_organization: str


class CreateBaseThing(BaseCreateModel):
    """
    Developer's notes

    thing_type does not need to be set by the user, this is determined by the
    POST endpoint

    e.g. POST /thing/water-well, POST /thing/spring determines the thing_type
    """

    location_id: int | None
    group_id: int | None = None  # Optional group ID for the thing
    name: str  # Name of the thing
    first_visit_date: PastOrTodayDate | None = None  # Date of NMBGMR's first visit


class CreateWell(CreateBaseThing, ValidateWell):
    """
    Schema for creating a well.
    """

    well_purposes: list[WellPurpose] | None = None
    well_depth: float | None = Field(
        default=None, gt=0, description="Well depth in feet"
    )
    hole_depth: float | None = Field(
        default=None, gt=0, description="Hole depth in feet"
    )
    well_casing_diameter: float | None = Field(
        default=None, gt=0, description="Well casing diameter in inches"
    )
    well_casing_depth: float | None = Field(
        default=None, gt=0, description="Well casing depth in feet"
    )
    well_casing_materials: list[CasingMaterial] | None = None

    measuring_point_height: float = Field(description="Measuring point height in feet")
    measuring_point_description: str | None = None
    notes: list[CreateNote] | None = None
    well_completion_date: PastOrTodayDate | None = None
    well_completion_date_source: str | None = None
    well_driller_name: str | None = None
    well_construction_method: WellConstructionMethod | None = None
    well_construction_method_source: str | None = None
    well_pump_type: WellPumpType | None = None
    is_suitable_for_datalogger: bool | None
    formation_completion_code: FormationCode | None = None


class CreateSpring(CreateBaseThing):
    """
    Schema for creating a spring.
    """

    spring_type: SpringType | None = None


class CreateWellScreen(BaseCreateModel):
    """
    Schema for creating a well screen.
    """

    thing_id: int
    aquifer_system_id: int | None = None
    geologic_formation_id: int | None = None
    screen_depth_bottom: float = Field(gt=0, description="Screen depth bottom in feet")
    screen_depth_top: float = Field(gt=0, description="Screen depth top in feet")
    screen_type: ScreenType | None = None
    screen_description: str | None = None

    # validate that screen depth bottom is greater than top
    @model_validator(mode="after")
    def check_depths(self):
        if self.screen_depth_bottom < self.screen_depth_top:
            raise ValueError(
                "screen_depth_bottom must be greater than screen_depth_top"
            )
        return self


# ------ RESPONSE ----------
class ThingIdLinkResponse(BaseResponseModel):
    thing_id: int
    relation: str
    alternate_id: str
    alternate_organization: Organization


class MonitoringFrequencyResponse(BaseModel):
    monitoring_frequency: MonitoringFrequency
    start_date: PastOrTodayDate
    end_date: PastOrTodayDate | None


class BaseThingResponse(BaseResponseModel):
    name: str
    thing_type: str
    current_location: LocationGeoJSONResponse
    first_visit_date: PastOrTodayDate | None
    groups: list[GroupResponse] = []
    monitoring_status: str | None
    links: list[ThingIdLinkResponse] = Field(default=[], alias="alternate_ids")
    monitoring_frequencies: list[MonitoringFrequencyResponse] = []
    general_notes: list[NoteResponse] | None = None

    @field_validator("monitoring_frequencies", mode="before")
    def remove_records_with_end_date(cls, monitoring_frequencies):
        if monitoring_frequencies is not None:
            active_frequencies = [
                {
                    "monitoring_frequency": freq.monitoring_frequency,
                    "start_date": freq.start_date.isoformat(),
                    "end_date": None,
                }
                for freq in monitoring_frequencies
                if freq.end_date is None
            ]
        return active_frequencies


class WellResponse(BaseThingResponse):
    """
    Response schema for well details.
    """

    well_purposes: list[WellPurpose] = []
    well_depth: float | None = None
    well_depth_unit: str = "ft"
    well_depth_source: str | None
    hole_depth: float | None = None
    hole_depth_unit: str = "ft"
    well_casing_diameter: float | None = None  # in inches
    well_casing_diameter_unit: str = "in"
    well_casing_depth: float | None = None
    well_casing_depth_unit: str = "ft"
    well_casing_materials: list[CasingMaterial] = []
    well_completion_date: PastOrTodayDate | None
    well_completion_date_source: str | None
    well_driller_name: str | None
    well_construction_method: WellConstructionMethod | None
    well_construction_method_source: str | None
    well_pump_type: WellPumpType | None
    well_pump_depth: float | None
    well_pump_depth_unit: str = "ft"
    is_suitable_for_datalogger: bool | None
    well_status: str | None
    measuring_point_height: float
    measuring_point_height_unit: str = "ft"
    measuring_point_description: str | None
    aquifers: list[dict] = []
    water_notes: list[NoteResponse] | None = None
    sampling_procedure_notes: list[NoteResponse] | None = None

    construction_notes: list[NoteResponse] | None = None
    permissions: list[PermissionHistoryResponse]
    formation_completion_code: FormationCode | None

    @field_validator("well_purposes", mode="before")
    def populate_well_purposes_with_strings(cls, well_purposes):
        if well_purposes is not None:
            purposes = [well_purpose.purpose for well_purpose in well_purposes]
        else:
            purposes = []
        return purposes

    @field_validator("well_casing_materials", mode="before")
    def populate_well_casing_materials_with_strings(cls, well_casing_materials):
        if well_casing_materials is not None:
            materials = [
                well_casing_material.material
                for well_casing_material in well_casing_materials
            ]
        else:
            materials = []
        return materials

    @field_validator("permissions", mode="before")
    def populate_permission_history_with_latest_records(cls, permissions):
        """
        Populate the permission history with the latest records for each
        type of permission. If multiple records exist for the same permission type
        only the most recent one is included. If there are no records
        the permission_allowed will be None
        """
        permissions_to_return = []
        for permission_type in [
            "Water Level Sample",
            "Water Chemistry Sample",
            "Datalogger Installation",
        ]:
            # Filter records for the current permission type
            filtered_records = [
                record
                for record in permissions
                if record.permission_type == permission_type and record.end_date is None
            ]
            if filtered_records:
                # Get the most recent record based on start_date
                latest_record = max(
                    filtered_records, key=lambda record: record.start_date
                )
                permissions_to_return.append(latest_record)
            else:
                permissions_to_return.append(
                    PermissionHistoryResponse(
                        permission_type=permission_type,
                        permission_allowed=None,
                        start_date=None,
                        end_date=None,
                    )
                )
        return permissions_to_return


class SpringResponse(BaseThingResponse):
    """
    Response schema for spring details.
    """

    spring_type: str | None = None  # e.g., "Natural", "Artifical", etc.


class ThingResponse(WellResponse, SpringResponse):
    # required fields for wells that don't apply to other thing types
    measuring_point_height: float | None


class WellScreenResponse(BaseResponseModel):
    """
    Response schema for well screen details.
    """

    thing_id: int
    thing: WellResponse
    aquifer_system_id: int | None = None
    aquifer_system: str | None = None
    aquifer_type: str | None = None
    geologic_formation_id: int | None = None
    geologic_formation: str | None = None
    screen_depth_bottom: float
    screen_depth_bottom_unit: str = "ft"
    screen_depth_top: float
    screen_depth_top_unit: str = "ft"
    screen_type: str | None = None
    screen_description: str | None = None

    @field_validator("aquifer_system", mode="before")
    def populate_aquifer_system_with_name(cls, aquifer_system):
        if aquifer_system is not None:
            return aquifer_system.name
        return None

    @field_validator("aquifer_type", mode="before")
    def populate_aquifer_type_with_name(cls, aquifer_type):
        if aquifer_type is not None:
            return aquifer_type.name
        return None

    @field_validator("geologic_formation", mode="before")
    def populate_geologic_formation_with_code(cls, geologic_formation):
        if geologic_formation is not None:
            return geologic_formation.formation_code
        return None


class GeoJSONGeometry(BaseModel):
    """
    Geometry schema for GeoJSON response.
    """

    type: str
    coordinates: (
        List[float]
        | List[List[float]]
        | List[List[List[float]]]
        | List[List[List[List[float]]]]
    )  # Supports Point, LineString, Polygon, MultiPolygon


class Feature(BaseModel):
    """
    Feature schema for GeoJSON response.
    """

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: dict = {}


class FeatureCollectionResponse(BaseModel):
    """
    Response schema for GeoJSON FeatureCollection.
    """

    type: str = "FeatureCollection"
    features: List[Feature] = []


# -------- UPDATE ------------
class UpdateThing(BaseUpdateModel):
    """
    Schema for updating a thing.
    """

    name: str | None = None  # Optional name for the thing
    first_visit_date: PastOrTodayDate | None = None  # Date of NMBGMR's first visit


class UpdateWell(UpdateThing, ValidateWell):

    well_purposes: list[str] | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_construction_notes: str | None = None
    well_casing_diameter: float | None = None  # in inches
    well_casing_depth: float | None = None  # in feet
    well_casing_materials: list[str] | None = None


class UpdateSpring(UpdateThing):
    spring_type: str | None = None


class UpdateThingIdLink(BaseUpdateModel):
    alternate_organization: str | None = None
    alternate_id: str | None = None
    relation: str | None = None


class UpdateWellScreen(BaseUpdateModel):
    aquifer_system_id: int | None = None
    geologic_formation_id: int | None = None
    screen_depth_bottom: float | None = None
    screen_depth_top: float | None = None
    screen_description: str | None = None
    screen_type: str | None = None


# ============= EOF =============================================
