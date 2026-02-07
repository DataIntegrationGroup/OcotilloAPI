# ===============================================================================
# Copyright 2026 ross
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
from datetime import date
from io import StringIO
from itertools import groupby
from typing import Set

from pydantic import ValidationError
from shapely import Point
from sqlalchemy import select, and_
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session
from starlette.status import HTTP_400_BAD_REQUEST

from core.constants import SRID_UTM_ZONE_13N, SRID_UTM_ZONE_12N, SRID_WGS84
from db import (
    Group,
    Location,
    DataProvenance,
    FieldEvent,
    FieldEventParticipant,
    FieldActivity,
    Contact,
    PermissionHistory,
    Thing,
)
from db.engine import session_ctx
from schemas.thing import CreateWell
from schemas.well_inventory import WellInventoryRow
from services.contact_helper import add_contact
from services.exceptions_helper import PydanticStyleException
from services.thing_helper import add_thing
from services.util import transform_srid, convert_ft_to_m

AUTOGEN_REGEX = re.compile(r"^[A-Za-z]{2}-$")


def import_well_inventory_csv(*args, **kw) -> dict:
    with session_ctx() as session:
        return _import_well_inventory_csv(session, *args, **kw)


def _import_well_inventory_csv(session: Session, text: str, user: str):
    # if not file.content_type.startswith("text/csv") or not file.filename.endswith(
    #         ".csv"
    # ):
    #     raise PydanticStyleException(
    #         HTTP_400_BAD_REQUEST,
    #         detail=[
    #             {
    #                 "loc": [],
    #                 "msg": "Unsupported file type",
    #                 "type": "Unsupported file type",
    #                 "input": f"file.content_type {file.content_type} name={file.filename}",
    #             }
    #         ],
    #     )
    #
    # content = await file.read()
    # if not content:
    #     raise PydanticStyleException(
    #         HTTP_400_BAD_REQUEST,
    #         detail=[
    #             {"loc": [], "msg": "Empty file", "type": "Empty file", "input": ""}
    #         ],
    #     )
    #
    # try:
    #     text = content.decode("utf-8")
    # except UnicodeDecodeError:
    #     raise PydanticStyleException(
    #         HTTP_400_BAD_REQUEST,
    #         detail=[
    #             {
    #                 "loc": [],
    #                 "msg": "File encoding error",
    #                 "type": "File encoding error",
    #                 "input": "",
    #             }
    #         ],
    #     )

    reader = csv.DictReader(StringIO(text))
    rows = list(reader)

    if not rows:
        raise ValueError("No data rows found")
    if len(rows) > 2000:
        raise ValueError(f"Too many rows {len(rows)}>2000")

    try:
        header = text.splitlines()[0]
        dialect = csv.Sniffer().sniff(header)
    except csv.Error:
        # raise an error if sniffing fails, which likely means the header is not parseable as CSV
        raise ValueError("Unable to parse CSV header")

    if dialect.delimiter != ",":
        raise ValueError(f"Unsupported delimiter '{dialect.delimiter}'")

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
            current_row_id = None
            try:
                for project, items in groupby(
                    sorted(models, key=lambda x: x.project), key=lambda x: x.project
                ):
                    # get project and add if does not exist
                    # BDMS-221 adds group_type
                    sql = select(Group).where(
                        and_(
                            Group.group_type == "Monitoring Plan", Group.name == project
                        )
                    )
                    group = session.scalars(sql).one_or_none()
                    if not group:
                        group = Group(name=project, group_type="Monitoring Plan")
                        session.add(group)
                        session.flush()

                    for model in items:
                        current_row_id = model.well_name_point_id
                        added = _add_csv_row(session, group, model, user)
                        wells.append(added)
            except ValueError as e:
                validation_errors.append(
                    {
                        "row": current_row_id or "unknown",
                        "field": "Invalid value",
                        "error": str(e),
                    }
                )
                session.rollback()
                wells = []
            except DatabaseError as e:
                logging.error(
                    f"Database error while importing row '{current_row_id or 'unknown'}': {e}"
                )
                validation_errors.append(
                    {
                        "row": current_row_id or "unknown",
                        "field": "Database error",
                        "error": "A database error occurred while importing this row.",
                    }
                )
                session.rollback()
                wells = []
            else:
                session.commit()

    rows_imported = len(wells)
    rows_processed = len(rows)
    rows_with_validation_errors_or_warnings = len(validation_errors)

    return {
        "validation_errors": validation_errors,
        "summary": {
            "total_rows_processed": rows_processed,
            "total_rows_imported": rows_imported,
            "validation_errors_or_warnings": rows_with_validation_errors_or_warnings,
        },
        "wells": wells,
    }


def _make_location(model) -> Location:
    point = Point(model.utm_easting, model.utm_northing)

    # TODO: this needs to be more sophisticated in the future. Likely more than 13N and 12N will be used
    if model.utm_zone == "13N":
        source_srid = SRID_UTM_ZONE_13N
    elif model.utm_zone == "12N":
        source_srid = SRID_UTM_ZONE_12N
    else:
        raise ValueError(f"Unsupported UTM zone: {model.utm_zone}")

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

    return loc


def _make_contact(model: WellInventoryRow, well: Thing, idx) -> dict:
    # add contact
    notes = []
    for content, note_type in (
        (model.result_communication_preference, "Communication"),
        (model.contact_special_requests_notes, "General"),
    ):
        if content is not None:
            notes.append({"content": content, "note_type": note_type})

    emails = []
    phones = []
    addresses = []
    name = getattr(model, f"contact_{idx}_name")
    if name:
        for i in (1, 2):
            email = getattr(model, f"contact_{idx}_email_{i}")
            etype = getattr(model, f"contact_{idx}_email_{i}_type")
            if email and etype:
                emails.append({"email": email, "email_type": etype})
            phone = getattr(model, f"contact_{idx}_phone_{i}")
            ptype = getattr(model, f"contact_{idx}_phone_{i}_type")
            if phone and ptype:
                phones.append({"phone_number": phone, "phone_type": ptype})

            address_line_1 = getattr(model, f"contact_{idx}_address_{i}_line_1")
            address_line_2 = getattr(model, f"contact_{idx}_address_{i}_line_2")
            city = getattr(model, f"contact_{idx}_address_{i}_city")
            state = getattr(model, f"contact_{idx}_address_{i}_state")
            postal_code = getattr(model, f"contact_{idx}_address_{i}_postal_code")
            address_type = getattr(model, f"contact_{idx}_address_{i}_type")
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
            "notes": notes,
        }


def _make_well_permission(
    well: Thing,
    contact: Contact | None,
    permission_type: str,
    permission_allowed: bool,
    start_date: date,
) -> PermissionHistory:
    """
    Makes a PermissionHistory record for the given well and contact.
    If the contact has not been provided, but a permission is to be created,
    no PermissionHistory record is created and a 400 error is raised.
    """
    if contact is None:
        raise PydanticStyleException(
            HTTP_400_BAD_REQUEST,
            detail=[
                {
                    "loc": [],
                    "msg": f"Permission of type '{permission_type}' cannot be created without a contact.",
                    "type": "Missing contact",
                    "input": {"permission_type": permission_type},
                }
            ],
        )

    permission = PermissionHistory(
        target_table="thing",
        target_id=well.id,
        contact=contact,
        permission_type=permission_type,
        permission_allowed=permission_allowed,
        start_date=start_date,
        end_date=None,
    )
    return permission


def _generate_autogen_well_id(session, prefix: str, offset: int = 0) -> tuple[str, int]:
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
            if AUTOGEN_REGEX.match(well_id):
                well_id, offset = _generate_autogen_well_id(session, well_id, offset)
                row["well_name_point_id"] = well_id

            if well_id in seen_ids:
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

    # --------------------
    # Location and associated tables
    # --------------------

    # add Location
    loc = _make_location(model)
    session.add(loc)
    session.flush()

    # add location notes
    if model.directions_to_site:
        directions_note = loc.add_note(
            content=model.directions_to_site, note_type="Directions"
        )
        session.add(directions_note)

    # add data provenance records
    dp = DataProvenance(
        target_id=loc.id,
        target_table="location",
        field_name="elevation",
        collection_method=model.elevation_method,
    )
    session.add(dp)

    # --------------------
    # Thing and associated tables
    # --------------------

    # add Thing
    """
    Developer's note

    Laila said that the depth source is almost always the source for the historic depth to water.
    She indicated that it would be acceptable to use the depth source for the historic depth to water source.
    """
    if model.depth_source:
        historic_depth_to_water_source = model.depth_source.lower()
    else:
        historic_depth_to_water_source = "unknown"

    if model.historic_depth_to_water_ft is not None:
        historic_depth_note = f"historic depth to water: {model.historic_depth_to_water_ft} ft - source: {historic_depth_to_water_source}"
    else:
        historic_depth_note = None

    well_notes = []
    for note_content, note_type in (
        (model.specific_location_of_well, "Access"),
        (model.contact_special_requests_notes, "General"),
        (model.well_measuring_notes, "Sampling Procedure"),
        (model.sampling_scenario_notes, "Sampling Procedure"),
        (historic_depth_note, "Historical"),
    ):
        if note_content is not None:
            well_notes.append({"content": note_content, "note_type": note_type})

    alternate_ids = []
    for alternate_id, alternate_organization in (
        (model.site_name, "NMBGMR"),
        (model.ose_well_record_id, "NMOSE"),
    ):
        if alternate_id is not None:
            alternate_ids.append(
                {
                    "alternate_id": alternate_id,
                    "alternate_organization": alternate_organization,
                    "relation": "same_as",
                }
            )

    well_purposes = []
    if model.well_purpose:
        well_purposes.append(model.well_purpose)
    if model.well_purpose_2:
        well_purposes.append(model.well_purpose_2)

    monitoring_frequencies = []
    if model.monitoring_frequency:
        monitoring_frequencies.append(
            {
                "monitoring_frequency": model.monitoring_frequency,
                "start_date": date_time.date(),
            }
        )

    data = CreateWell(
        location_id=loc.id,
        group_id=group.id,
        name=name,
        first_visit_date=date_time.date(),
        well_depth=model.total_well_depth_ft,
        well_depth_source=model.depth_source,
        well_casing_diameter=model.casing_diameter_ft,
        measuring_point_height=model.measuring_point_height_ft,
        measuring_point_description=model.measuring_point_description,
        well_completion_date=model.date_drilled,
        well_completion_date_source=model.completion_source,
        well_pump_type=model.well_pump_type,
        well_pump_depth=model.well_pump_depth_ft,
        is_suitable_for_datalogger=model.datalogger_possible,
        is_open=model.is_open,
        well_status=model.well_hole_status,
        notes=well_notes,
        well_purposes=well_purposes,
        monitoring_frequencies=monitoring_frequencies,
        alternate_ids=alternate_ids,
    )
    well_data = data.model_dump()

    """
    Developer's notes

    the add_thing function also handles:
    - MeasuringPointHistory
    - GroupThingAssociation
    - LocationThingAssociation
    - DataProvenance for well_completion_date
    - DataProvenance for well_depth
    - Notes
    - WellPurpose
    - MonitoringFrequencyHistory
    - StatusHistory for status_type 'Open Status'
    - StatusHistory for status_type 'Datalogger Suitability Status'
    - StatusHistory for status_type 'Well Status'
    """
    well = add_thing(
        session=session,
        data=well_data,
        user=user,
        thing_type="water well",
        commit=False,
    )
    session.refresh(well)

    # ------------------
    # Field Events and related tables
    # ------------------
    """
    Developer's notes

    These tables are not handled in add_thing because they are only relevant if
    the well has been inventoried in the field, not if the well is added from
    another source like a report, database, or map.
    """

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

    # add field activity
    fa = FieldActivity(
        field_event=fe,
        activity_type="well inventory",
        notes="Well inventory conducted during field event.",
    )
    session.add(fa)

    # ------------------
    # Contacts
    # ------------------

    # add contacts
    contact_for_permissions = None
    for idx in (1, 2):
        contact_dict = _make_contact(model, well, idx)
        if contact_dict:
            contact = add_contact(session, contact_dict, user=user, commit=False)

            # Use the first created contact for permissions if available
            if contact_for_permissions is None:
                contact_for_permissions = contact

    # ------------------
    # Permissions
    # ------------------

    # add permissions
    for permission_type, permission_allowed in (
        ("Water Level Sample", model.repeat_measurement_permission),
        ("Water Chemistry Sample", model.sampling_permission),
        ("Datalogger Installation", model.datalogger_installation_permission),
    ):
        if permission_allowed is not None:
            permission = _make_well_permission(
                well=well,
                contact=contact_for_permissions,
                permission_type=permission_type,
                permission_allowed=permission_allowed,
                start_date=model.date_time.date(),
            )
            session.add(permission)

    return model.well_name_point_id


# ============= EOF =============================================
