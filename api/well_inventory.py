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
import csv
from datetime import datetime
from io import StringIO
from itertools import groupby
from typing import Optional, Set

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from shapely import Point
from sqlalchemy import select

from constants import SRID_UTM_ZONE_13N, SRID_UTM_ZONE_12N, SRID_WGS84
from core.dependencies import session_dependency, amp_editor_dependency
from core.enums import (
    ContactType,
    Role,
    ElevationMethod,
    WellPurpose as WellPurposeEnum,
    PhoneType,
    EmailType,
    AddressType,
)
from db import (
    Group,
    ThingIdLink,
    GroupThingAssociation,
    Location,
    LocationThingAssociation,
)
from db.thing import Thing, WellPurpose
from services.contact_helper import add_contact
from services.util import transform_srid

router = APIRouter(prefix="/well-inventory-csv")


class WellInventoryRow(BaseModel):
    # Required fields
    project: str
    well_name_point_id: str
    site_name: str
    date_time: datetime
    field_staff: str
    utm_easting: float
    utm_northing: float
    utm_zone: int
    elevation_ft: float
    elevation_method: ElevationMethod
    measuring_point_height_ft: float

    # Optional fields
    field_staff_2: Optional[str] = None
    field_staff_3: Optional[str] = None
    contact_name: Optional[str] = None
    contact_organization: Optional[str] = None
    contact_role: Optional[Role] = None
    contact_type: Optional[ContactType] = "Primary"
    contact_phone_1: Optional[str] = None
    contact_phone_1_type: Optional[PhoneType] = None
    contact_phone_2: Optional[str] = None
    contact_phone_2_type: Optional[PhoneType] = None
    contact_email_1: Optional[str] = None
    contact_email_1_type: Optional[EmailType] = None
    contact_email_2: Optional[str] = None
    contact_email_2_type: Optional[EmailType] = None
    contact_address_1_line_1: Optional[str] = None
    contact_address_1_line_2: Optional[str] = None
    contact_address_1_type: Optional[AddressType] = None
    contact_address_1_state: Optional[str] = None
    contact_address_1_city: Optional[str] = None
    contact_address_1_postal_code: Optional[str] = None
    contact_address_2_line_1: Optional[str] = None
    contact_address_2_line_2: Optional[str] = None
    contact_address_2_type: Optional[AddressType] = None
    contact_address_2_state: Optional[str] = None
    contact_address_2_city: Optional[str] = None
    contact_address_2_postal_code: Optional[str] = None
    directions_to_site: Optional[str] = None
    specific_location_of_well: Optional[str] = None
    repeat_measurement_permission: Optional[bool] = None
    sampling_permission: Optional[bool] = None
    datalogger_installation_permission: Optional[bool] = None
    public_availability_acknowledgement: Optional[bool] = None
    special_requests: Optional[str] = None
    ose_well_record_id: Optional[str] = None
    date_drilled: Optional[datetime] = None
    completion_source: Optional[str] = None
    total_well_depth_ft: Optional[float] = None
    historic_depth_to_water_ft: Optional[float] = None
    depth_source: Optional[str] = None
    well_pump_type: Optional[str] = None
    well_pump_depth_ft: Optional[float] = None
    is_open: Optional[bool] = None
    datalogger_possible: Optional[bool] = None
    casing_diameter_ft: Optional[float] = None
    measuring_point_description: Optional[str] = None
    well_purpose: Optional[WellPurposeEnum] = None
    well_hole_status: Optional[str] = None
    monitoring_frequency: Optional[str] = None


@router.post("")
async def well_inventory_csv(
    user: amp_editor_dependency,
    session: session_dependency,
    file: UploadFile = File(...),
):
    if not file.content_type.startswith("text/csv") or not file.filename.endswith(
        ".csv"
    ):
        return JSONResponse(status_code=400, content={"error": "Unsupported file type"})

    content = await file.read()
    if not content:
        return JSONResponse(status_code=400, content={"error": "Empty file"})
    try:
        text = content.decode("utf-8")
    except Exception:
        return JSONResponse(status_code=400, content={"error": "File encoding error"})
    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    if not rows:
        return JSONResponse(status_code=400, content={"error": "No data rows found"})
    validation_errors = []
    wells = []
    models = []
    seen_ids: Set[str] = set()
    for idx, row in enumerate(rows):
        try:
            well_id = row.get("well_name_point_id")
            if not well_id:
                raise ValueError("Field required")
            if well_id in seen_ids:
                raise ValueError("Duplicate value for well_name_point_id")
            seen_ids.add(well_id)
            model = WellInventoryRow(**row)
            models.append(model)

        except ValidationError as e:
            for err in e.errors():
                validation_errors.append(
                    {
                        "row": idx + 1,
                        "field": err["loc"][0],
                        "error": f"Value error, {err['msg']}",
                    }
                )
        except ValueError as e:
            validation_errors.append(
                {"row": idx + 1, "field": "well_name_point_id", "error": str(e)}
            )

    def convert_f_to_m(r):
        return r * 0.3048

    for project, items in groupby(
        sorted(models, key=lambda x: x.project), key=lambda x: x.project
    ):
        # get project and add if does not exist
        sql = select(Group).where(Group.name == project)
        group = session.scalars(sql).one_or_none()
        if not group:
            group = Group(name=project)
            session.add(group)

        for model in items:
            name = model.well_name_point_id
            site_name = model.site_name
            date_time = model.date_time

            # add field staff

            point = Point(model.utm_easting, model.utm_northing)
            if model.utm_zone == 13:
                source_srid = SRID_UTM_ZONE_13N
            else:
                source_srid = SRID_UTM_ZONE_12N

            # Convert the point to a WGS84 coordinate system
            transformed_point = transform_srid(
                point, source_srid=source_srid, target_srid=SRID_WGS84
            )
            elevation_ft = float(model.elevation_ft)
            elevation_m = convert_f_to_m(elevation_ft)
            elevation_method = model.elevation_method
            measuring_point_height_ft = model.measuring_point_height_ft

            loc = Location(
                point=transformed_point.wkt,
                elevation=elevation_m,
                elevation_method=elevation_method,
            )
            session.add(loc)

            wells.append(name)
            well = Thing(
                name=name,
                thing_type="water well",
                first_visit_date=date_time.date(),
            )
            session.add(well)
            if model.well_purpose:
                well_purpose = WellPurpose(purpose=model.well_purpose, thing=well)
                session.add(well_purpose)

            assoc = LocationThingAssociation(location=loc, thing=well)
            assoc.effective_start = date_time
            session.add(assoc)

            gta = GroupThingAssociation(group=group, thing=well)
            session.add(gta)
            group.thing_associations.append(gta)

            well.links.append(
                ThingIdLink(
                    alternate_id=site_name,
                    alternate_organization="NMBGMR",
                    relation="same_as",
                )
            )
            session.flush()

            # add contact
            emails = []
            phones = []
            addresses = []
            for i in (1, 2):
                email = getattr(model, f"contact_email_{i}")
                etype = getattr(model, f"contact_email_{i}_type")
                if email and etype:
                    emails.append({"email": email, "email_type": etype})
                phone = getattr(model, f"contact_phone_{i}")
                ptype = getattr(model, f"contact_phone_{i}_type")
                if phone and ptype:
                    phones.append({"phone_number": phone, "phone_type": ptype})

                address_line_1 = getattr(model, f"contact_address_{i}_line_1")
                address_line_2 = getattr(model, f"contact_address_{i}_line_2")
                city = getattr(model, f"contact_address_{i}_city")
                state = getattr(model, f"contact_address_{i}_state")
                postal_code = getattr(model, f"contact_address_{i}_postal_code")
                address_type = getattr(model, f"contact_address_{i}_type")
                if address_line_1 and city and state and postal_code and address_type:
                    addresses.append(
                        {
                            "address": {
                                "address_line_1": address_line_1,
                                "address_line_2": address_line_2,
                                "city": city,
                                "state": state,
                                "postal_code": postal_code,
                                "address_type": address_type,
                            }
                        }
                    )

            add_contact(
                session,
                {
                    "thing_id": well.id,
                    "name": model.contact_name,
                    "organization": model.contact_organization,
                    "role": model.contact_role,
                    "contact_type": model.contact_type,
                    "emails": emails,
                    "phones": phones,
                    "addresses": addresses,
                },
                user,
            )

        session.commit()

    if validation_errors:
        return JSONResponse(
            status_code=422,
            content={
                "validation_errors": validation_errors,
                "summary": {
                    "total_rows_processed": len(rows),
                    "total_rows_imported": 0,
                    "validation_errors_or_warnings": len(validation_errors),
                },
                "wells": [],
            },
        )

    return JSONResponse(
        status_code=201,
        content={
            "summary": {
                "total_rows_processed": len(rows),
                "total_rows_imported": len(wells),
                "validation_errors_or_warnings": 0,
            },
            "wells": wells,
        },
    )


# ============= EOF =============================================
