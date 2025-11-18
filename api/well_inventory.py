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
from io import StringIO
from itertools import groupby
from typing import Set

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from shapely import Point
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED, HTTP_422_UNPROCESSABLE_ENTITY

from constants import SRID_UTM_ZONE_13N, SRID_UTM_ZONE_12N, SRID_WGS84
from core.dependencies import session_dependency, amp_editor_dependency
from db import (
    Group,
    ThingIdLink,
    GroupThingAssociation,
    Location,
    LocationThingAssociation,
)
from db.thing import Thing, WellPurpose
from schemas.well_inventory import WellInventoryRow
from services.contact_helper import add_contact
from services.util import transform_srid

router = APIRouter(prefix="/well-inventory-csv")


def _add_location(model, well) -> Location:

    def convert_f_to_m(r):
        return round(r * 0.3048, 6)

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

    loc = Location(
        point=transformed_point.wkt,
        elevation=elevation_m,
        elevation_method=elevation_method,
    )
    date_time = model.date_time
    assoc = LocationThingAssociation(location=loc, thing=well)
    assoc.effective_start = date_time
    return loc


def _add_group_association(group, well) -> GroupThingAssociation:
    gta = GroupThingAssociation(group=group, thing=well)
    group.thing_associations.append(gta)
    return gta


def _make_contact(model: WellInventoryRow, well: Thing, idx) -> dict:
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

    return {
        "thing_id": well.id,
        "name": model.contact_name,
        "organization": model.contact_organization,
        "role": model.contact_role,
        "contact_type": model.contact_type,
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
    }


def _make_row_models(rows):
    models = []
    validation_errors = []
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
            # Map specific controlled errors to safe, non-revealing messages
            if str(e) == "Field required":
                error_msg = "Field required"
            elif str(e) == "Duplicate value for well_name_point_id":
                error_msg = "Duplicate value for well_name_point_id"
            else:
                error_msg = "Invalid value"

            validation_errors.append(
                {"row": idx + 1, "field": "well_name_point_id", "error": error_msg}
            )
    return models, validation_errors


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

    wells = []
    models, validation_errors = _make_row_models(rows)

    for project, items in groupby(
        sorted(models, key=lambda x: x.project), key=lambda x: x.project
    ):
        # get project and add if does not exist
        # BDMS-221 adds group_type
        # .where(Group.group_type == "Monitoring Plan", Group.name == project)
        sql = select(Group).where(Group.name == project)
        group = session.scalars(sql).one_or_none()
        if not group:
            group = Group(name=project)
            session.add(group)

        for model in items:
            name = model.well_name_point_id
            date_time = model.date_time
            site_name = model.site_name

            # add field staff

            # add Thing
            well = Thing(
                name=name,
                thing_type="water well",
                first_visit_date=date_time.date(),
            )
            wells.append(name)
            session.add(well)
            session.commit()
            session.refresh(well)

            # add WellPurpose
            if model.well_purpose:
                well_purpose = WellPurpose(purpose=model.well_purpose, thing=well)
                session.add(well_purpose)

            # BDMS-221 adds MeasuringPointHistory model
            # measuring_point_height_ft = model.measuring_point_height_ft
            # if measuring_point_height_ft:
            #     mph = MeasuringPointHistory(well=well,
            #                                 height=measuring_point_height_ft)
            #     session.add(mph)

            # add Location
            assoc = _add_location(model, well)
            session.add(assoc)

            gta = _add_group_association(group, well)
            session.add(gta)

            # add alternate ids
            well.links.append(
                ThingIdLink(
                    alternate_id=site_name,
                    alternate_organization="NMBGMR",
                    relation="same_as",
                )
            )

            for idx in (1, 2):
                contact = _make_contact(model, well, idx)
                if contact:
                    add_contact(session, contact, user=user)

        session.commit()

    rows_imported = len(wells)
    rows_processed = len(rows)
    rows_with_validation_errors_or_warnings = len(validation_errors)

    status_code = HTTP_201_CREATED
    if validation_errors:
        status_code = HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=status_code,
        content={
            "validation_errors": validation_errors,
            "summary": {
                "total_rows_processed": rows_processed,
                "total_rows_imported": rows_imported,
                "validation_errors_or_warnings": rows_with_validation_errors_or_warnings,
            },
            "wells": wells,
        },
    )


# ============= EOF =============================================
