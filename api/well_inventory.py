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
import logging
import re
from collections import Counter
from io import StringIO
from itertools import groupby
from typing import Set

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from shapely import Point
from sqlalchemy import select, and_
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_400_BAD_REQUEST,
)

from constants import SRID_UTM_ZONE_13N, SRID_UTM_ZONE_12N, SRID_WGS84
from core.dependencies import session_dependency, amp_editor_dependency
from db import (
    Group,
    ThingIdLink,
    GroupThingAssociation,
    Location,
    LocationThingAssociation,
    MeasuringPointHistory,
    DataProvenance,
    FieldEvent,
    FieldEventParticipant,
    Contact,
)
from db.thing import Thing, WellPurpose, MonitoringFrequencyHistory
from schemas.thing import CreateWell
from schemas.well_inventory import WellInventoryRow
from services.contact_helper import add_contact
from services.exceptions_helper import PydanticStyleException
from services.thing_helper import add_thing, modify_well_descriptor_tables
from services.util import transform_srid, convert_ft_to_m

router = APIRouter(prefix="/well-inventory-csv")


def _add_location(model, well) -> Location:
    point = Point(model.utm_easting, model.utm_northing)

    # TODO: this needs to be more sophisticated in the future. Likely more than 13N and 12N will be used
    if model.utm_zone == "13N":
        source_srid = SRID_UTM_ZONE_13N
    else:
        source_srid = SRID_UTM_ZONE_12N

    # Convert the point to a WGS84 coordinate system
    transformed_point = transform_srid(
        point, source_srid=source_srid, target_srid=SRID_WGS84
    )
    elevation_ft = float(model.elevation_ft)
    elevation_m = convert_ft_to_m(elevation_ft)

    loc = Location(
        point=transformed_point.wkt,
        elevation=elevation_m,
    )
    date_time = model.date_time
    assoc = LocationThingAssociation(location=loc, thing=well)
    assoc.effective_start = date_time

    return loc, assoc


def _make_contact(model: WellInventoryRow, well: Thing, idx) -> dict:
    # add contact
    emails = []
    phones = []
    addresses = []
    name = getattr(model, f"contact_{idx}_name")
    if name:
        for j in (1, 2):
            for i in (1, 2):
                email = getattr(model, f"contact_{j}_email_{i}")
                etype = getattr(model, f"contact_{j}_email_{i}_type")
                if email and etype:
                    emails.append({"email": email, "email_type": etype})
                phone = getattr(model, f"contact_{j}_phone_{i}")
                ptype = getattr(model, f"contact_{j}_phone_{i}_type")
                if phone and ptype:
                    phones.append({"phone_number": phone, "phone_type": ptype})

                address_line_1 = getattr(model, f"contact_{j}_address_{i}_line_1")
                address_line_2 = getattr(model, f"contact_{j}_address_{i}_line_2")
                city = getattr(model, f"contact_{j}_address_{i}_city")
                state = getattr(model, f"contact_{j}_address_{i}_state")
                postal_code = getattr(model, f"contact_{j}_address_{i}_postal_code")
                address_type = getattr(model, f"contact_{j}_address_{i}_type")
                if address_line_1 and city and state and postal_code and address_type:
                    addresses.append(
                        {
                            "address_line_1": address_line_1,
                            "address_line_2": address_line_2,
                            "city": city,
                            "state": state,
                            "postal_code": postal_code,
                            "address_type": address_type,
                        }
                    )

        return {
            "thing_id": well.id,
            "name": name,
            "organization": getattr(model, f"contact_{idx}_organization"),
            "role": getattr(model, f"contact_{idx}_role"),
            "contact_type": getattr(model, f"contact_{idx}_type"),
            "emails": emails,
            "phones": phones,
            "addresses": addresses,
        }


AUTOGEN_REGEX = re.compile(r"^[A-Za-z]{2}-$")


def generate_autogen_well_id(session, prefix: str, offset: int = 0) -> str:
    # get the latest well_name_point_id that starts with the same prefix
    if not offset:
        latest_well = session.scalars(
            select(Thing)
            .where(Thing.name.like(f"{prefix}%"))
            .order_by(Thing.name.desc())
        ).first()

        if latest_well:
            latest_id = latest_well.name
            # extract the numeric part and increment it
            number_part = latest_id.replace(prefix, "")
            if number_part.isdigit():
                new_number = int(number_part) + 1
            else:
                new_number = 1
        else:
            new_number = 1
    else:
        new_number = offset + 1

    return f"{prefix}{new_number:04d}", new_number


def _make_row_models(rows, session):
    models = []
    validation_errors = []
    seen_ids: Set[str] = set()
    offset = 0
    for idx, row in enumerate(rows):
        try:
            if all(key == row.get(key) for key in row.keys()):
                raise ValueError("Duplicate header row")

            well_id = row.get("well_name_point_id")
            if not well_id:
                raise ValueError("Field required")
            print(f"Processing well_name_point_id: {well_id}")
            if AUTOGEN_REGEX.match(well_id):
                well_id, offset = generate_autogen_well_id(session, well_id, offset)
                row["well_name_point_id"] = well_id

            if well_id in seen_ids:
                print(seen_ids)
                raise ValueError("Duplicate value for well_name_point_id")
            seen_ids.add(well_id)

            model = WellInventoryRow(**row)
            models.append(model)

        except ValidationError as e:
            for err in e.errors():
                loc = err["loc"]

                field = loc[0] if loc else "composite field error"
                value = row.get(field) if loc else None
                validation_errors.append(
                    {
                        "row": idx + 1,
                        "error": err["msg"],
                        "field": field,
                        "value": value,
                    }
                )
        except ValueError as e:
            field = "well_name_point_id"
            # Map specific controlled errors to safe, non-revealing messages
            if str(e) == "Field required":
                error_msg = "Field required"
            elif str(e) == "Duplicate value for well_name_point_id":
                error_msg = "Duplicate value for well_name_point_id"
            elif str(e) == "Duplicate header row":
                error_msg = "Duplicate header row"
                field = "header"
            else:
                error_msg = "Invalid value"

            validation_errors.append(
                {"row": idx + 1, "field": field, "error": error_msg}
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
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": [],
                    "msg": "Unsupported file type",
                    "type": "Unsupported file type",
                    "input": f"file.content_type {file.content_type} name={file.filename}",
                }
            ],
        )

    content = await file.read()
    if not content:
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {"loc": [], "msg": "Empty file", "type": "Empty file", "input": ""}
            ],
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": [],
                    "msg": "File encoding error",
                    "type": "File encoding error",
                    "input": "",
                }
            ],
        )

    reader = csv.DictReader(StringIO(text))
    rows = list(reader)

    if not rows:
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": [],
                    "msg": "No data rows found",
                    "type": "No data rows found",
                    "input": str(rows),
                }
            ],
        )

    if len(rows) > 2000:
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": [],
                    "msg": f"Too many rows {len(rows)}>2000",
                    "type": "Too many rows",
                }
            ],
        )

    header = text.splitlines()[0]
    dialect = csv.Sniffer().sniff(header)

    if dialect.delimiter in (";", "\t"):
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": [],
                    "msg": f"Unsupported delimiter '{dialect.delimiter}'",
                    "type": "Unsupported delimiter",
                }
            ],
        )

    header = header.split(dialect.delimiter)
    counts = Counter(header)
    duplicates = [col for col, count in counts.items() if count > 1]

    wells = []
    if duplicates:
        validation_errors = [
            {
                "row": 0,
                "field": f"{duplicates}",
                "error": "Duplicate columns found",
            }
        ]

    else:
        models, validation_errors = _make_row_models(rows, session)
        if models and not validation_errors:
            for project, items in groupby(
                sorted(models, key=lambda x: x.project), key=lambda x: x.project
            ):
                # get project and add if does not exist
                # BDMS-221 adds group_type
                sql = select(Group).where(
                    and_(Group.group_type == "Monitoring Plan", Group.name == project)
                )
                group = session.scalars(sql).one_or_none()
                if not group:
                    group = Group(name=project, group_type="Monitoring Plan")
                    session.add(group)

                for model in items:
                    try:
                        added = _add_csv_row(session, group, model, user)
                        if added:
                            session.commit()
                    except ValueError as e:
                        validation_errors.append(
                            {
                                "row": model.well_name_point_id,
                                "field": "Invalid value",
                                "error": str(e),
                            }
                        )
                        continue
                    except DatabaseError as e:
                        logging.error(
                            f"Database error while importing row '{model.well_name_point_id}': {e}"
                        )
                        validation_errors.append(
                            {
                                "row": model.well_name_point_id,
                                "field": "Database error",
                                "error": "A database error occurred while importing this row.",
                            }
                        )
                        continue

                    wells.append(added)

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


def _add_field_staff(
    session: Session, fs: str, field_event: FieldEvent, role: str, user: str
) -> None:
    ct = "Field Event Participant"
    org = "NMBGMR"
    contact = session.scalars(
        select(Contact)
        .where(Contact.name == fs)
        .where(Contact.organization == org)
        .where(Contact.contact_type == ct)
    ).first()

    if not contact:
        payload = dict(name=fs, role="Technician", organization=org, contact_type=ct)
        contact = add_contact(session, payload, user)

    fec = FieldEventParticipant(
        field_event=field_event, contact_id=contact.id, participant_role=role
    )
    session.add(fec)


def _add_csv_row(session: Session, group: Group, model: WellInventoryRow, user) -> str:
    name = model.well_name_point_id
    date_time = model.date_time
    site_name = model.site_name

    # add Thing
    data = CreateWell(
        name=name,
        first_visit_date=date_time.date(),
        well_depth=model.total_well_depth_ft,
        well_casing_diameter=model.casing_diameter_ft,
        measuring_point_height=model.measuring_point_height_ft,
        measuring_point_description=model.measuring_point_description,
    )
    well_data = data.model_dump(
        exclude=[
            "location_id",
            "group_id",
            "well_purposes",
            "well_casing_materials",
            "measuring_point_height",
            "measuring_point_description",
        ]
    )
    well = add_thing(
        session=session, data=well_data, user=user, thing_type="water well"
    )
    modify_well_descriptor_tables(session, well, data, user)
    session.refresh(well)

    # add field event
    fe = FieldEvent(
        event_date=date_time,
        notes="Initial field event from well inventory import",
        thing_id=well.id,
    )
    session.add(fe)

    # add field staff
    for fsi, role in (
        (model.field_staff, "Lead"),
        (model.field_staff_2, "Participant"),
        (model.field_staff_3, "Participant"),
    ):
        if not fsi:
            continue

        _add_field_staff(session, fsi, fe, role, user)

    # add MonitoringFrequency
    if model.monitoring_frequency:
        mfh = MonitoringFrequencyHistory(
            thing=well,
            monitoring_frequency=model.monitoring_frequency,
            start_date=date_time.date(),
        )
        session.add(mfh)

    # add WellPurpose
    for p in (model.well_purpose, model.well_purpose_2):
        if not p:
            continue
        wp = WellPurpose(purpose=p, thing=well)
        session.add(wp)

    # BDMS-221 adds MeasuringPointHistory model
    measuring_point_height_ft = model.measuring_point_height_ft
    if measuring_point_height_ft:
        mph = MeasuringPointHistory(
            thing=well,
            measuring_point_height=measuring_point_height_ft,
            measuring_point_description=model.measuring_point_description,
            start_date=date_time.date(),
        )
        session.add(mph)

    # add Location
    loc, assoc = _add_location(model, well)
    session.add(loc)
    session.add(assoc)
    session.flush()

    dp = DataProvenance(
        target_id=loc.id,
        target_table="location",
        field_name="elevation",
        collection_method=model.elevation_method,
    )
    session.add(dp)

    gta = GroupThingAssociation(group=group, thing=well)
    session.add(gta)
    group.thing_associations.append(gta)

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

    return model.well_name_point_id


# ============= EOF =============================================
