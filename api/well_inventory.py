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
# import csv
# from datetime import date
# import logging
# import re
# from collections import Counter
# from io import StringIO
# from itertools import groupby
# from typing import Set
#
# from fastapi import APIRouter, UploadFile, File
# from fastapi.responses import JSONResponse
# from pydantic import ValidationError
# from shapely import Point
# from sqlalchemy import select, and_
# from sqlalchemy.exc import DatabaseError
# from sqlalchemy.orm import Session
# from starlette.status import (
#     HTTP_201_CREATED,
#     HTTP_422_UNPROCESSABLE_ENTITY,
#     HTTP_400_BAD_REQUEST,
# )
#
# from core.constants import SRID_UTM_ZONE_13N, SRID_UTM_ZONE_12N, SRID_WGS84
# from core.dependencies import session_dependency, amp_editor_dependency
# from db import (
#     Group,
#     Location,
#     DataProvenance,
#     FieldEvent,
#     FieldEventParticipant,
#     FieldActivity,
#     Contact,
#     PermissionHistory,
#     Thing,
# )
# from schemas.thing import CreateWell
# from schemas.well_inventory import WellInventoryRow
# from services.contact_helper import add_contact
# from services.exceptions_helper import PydanticStyleException
# from services.thing_helper import add_thing
# from services.util import transform_srid, convert_ft_to_m
#
# router = APIRouter(prefix="/well-inventory-csv")


# @router.post("")
# async def well_inventory_csv(
#     user: amp_editor_dependency,
#     session: session_dependency,
#     file: UploadFile = File(...),
# ):
# if not file.content_type.startswith("text/csv") or not file.filename.endswith(
#     ".csv"
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
#
# reader = csv.DictReader(StringIO(text))
# rows = list(reader)
#
# if not rows:
#     raise PydanticStyleException(
#         HTTP_400_BAD_REQUEST,
#         detail=[
#             {
#                 "loc": [],
#                 "msg": "No data rows found",
#                 "type": "No data rows found",
#                 "input": str(rows),
#             }
#         ],
#     )
#
# if len(rows) > 2000:
#     raise PydanticStyleException(
#         HTTP_400_BAD_REQUEST,
#         detail=[
#             {
#                 "loc": [],
#                 "msg": f"Too many rows {len(rows)}>2000",
#                 "type": "Too many rows",
#             }
#         ],
#     )
#
# try:
#     header = text.splitlines()[0]
#     dialect = csv.Sniffer().sniff(header)
# except csv.Error:
#     # raise an error if sniffing fails, which likely means the header is not parseable as CSV
#     raise PydanticStyleException(
#         HTTP_400_BAD_REQUEST,
#         detail=[
#             {
#                 "loc": [],
#                 "msg": "CSV parsing error",
#                 "type": "CSV parsing error",
#             }
#         ],
#     )
#
# if dialect.delimiter in (";", "\t"):
#     raise PydanticStyleException(
#         HTTP_400_BAD_REQUEST,
#         detail=[
#             {
#                 "loc": [],
#                 "msg": f"Unsupported delimiter '{dialect.delimiter}'",
#                 "type": "Unsupported delimiter",
#             }
#         ],
#     )
#
# header = header.split(dialect.delimiter)
# counts = Counter(header)
# duplicates = [col for col, count in counts.items() if count > 1]
#
# wells = []
# if duplicates:
#     validation_errors = [
#         {
#             "row": 0,
#             "field": f"{duplicates}",
#             "error": "Duplicate columns found",
#         }
#     ]
#
# else:
#     models, validation_errors = _make_row_models(rows, session)
#     if models and not validation_errors:
#         for project, items in groupby(
#             sorted(models, key=lambda x: x.project), key=lambda x: x.project
#         ):
#             # get project and add if does not exist
#             # BDMS-221 adds group_type
#             sql = select(Group).where(
#                 and_(Group.group_type == "Monitoring Plan", Group.name == project)
#             )
#             group = session.scalars(sql).one_or_none()
#             if not group:
#                 group = Group(name=project, group_type="Monitoring Plan")
#                 session.add(group)
#                 session.flush()
#
#             for model in items:
#                 try:
#                     added = _add_csv_row(session, group, model, user)
#                     if added:
#                         session.commit()
#                 except ValueError as e:
#                     validation_errors.append(
#                         {
#                             "row": model.well_name_point_id,
#                             "field": "Invalid value",
#                             "error": str(e),
#                         }
#                     )
#                     session.rollback()
#                     continue
#                 except DatabaseError as e:
#                     logging.error(
#                         f"Database error while importing row '{model.well_name_point_id}': {e}"
#                     )
#                     validation_errors.append(
#                         {
#                             "row": model.well_name_point_id,
#                             "field": "Database error",
#                             "error": "A database error occurred while importing this row.",
#                         }
#                     )
#                     session.rollback()
#                     continue
#
#                 wells.append(added)
#
# rows_imported = len(wells)
# rows_processed = len(rows)
# rows_with_validation_errors_or_warnings = len(validation_errors)
#
# status_code = HTTP_201_CREATED
# if validation_errors:
#     status_code = HTTP_422_UNPROCESSABLE_ENTITY
#
# return JSONResponse(
#     status_code=status_code,
#     content={
#         "validation_errors": validation_errors,
#         "summary": {
#             "total_rows_processed": rows_processed,
#             "total_rows_imported": rows_imported,
#             "validation_errors_or_warnings": rows_with_validation_errors_or_warnings,
#         },
#         "wells": wells,
#     },
# )


# def _add_field_staff(
#     session: Session, fs: str, field_event: FieldEvent, role: str, user: str
# ) -> None:
#     ct = "Field Event Participant"
#     org = "NMBGMR"
#     contact = session.scalars(
#         select(Contact)
#         .where(Contact.name == fs)
#         .where(Contact.organization == org)
#         .where(Contact.contact_type == ct)
#     ).first()
#
#     if not contact:
#         payload = dict(name=fs, role="Technician", organization=org, contact_type=ct)
#         contact = add_contact(session, payload, user)
#
#     fec = FieldEventParticipant(
#         field_event=field_event, contact_id=contact.id, participant_role=role
#     )
#     session.add(fec)
#
#
# def _add_csv_row(session: Session, group: Group, model: WellInventoryRow, user) -> str:
#     name = model.well_name_point_id
#     date_time = model.date_time
#
#     # --------------------
#     # Location and associated tables
#     # --------------------
#
#     # add Location
#     loc = _make_location(model)
#     session.add(loc)
#     session.flush()
#
#     # add location notes
#     if model.directions_to_site:
#         directions_note = loc.add_note(
#             content=model.directions_to_site, note_type="Directions"
#         )
#         session.add(directions_note)
#
#     # add data provenance records
#     dp = DataProvenance(
#         target_id=loc.id,
#         target_table="location",
#         field_name="elevation",
#         collection_method=model.elevation_method,
#     )
#     session.add(dp)
#
#     # --------------------
#     # Thing and associated tables
#     # --------------------
#
#     # add Thing
#     """
#     Developer's note
#
#     Laila said that the depth source is almost always the source for the historic depth to water.
#     She indicated that it would be acceptable to use the depth source for the historic depth to water source.
#     """
#     if model.depth_source:
#         historic_depth_to_water_source = model.depth_source.lower()
#     else:
#         historic_depth_to_water_source = "unknown"
#
#     if model.historic_depth_to_water_ft is not None:
#         historic_depth_note = f"historic depth to water: {model.historic_depth_to_water_ft} ft - source: {historic_depth_to_water_source}"
#     else:
#         historic_depth_note = None
#
#     well_notes = []
#     for note_content, note_type in (
#         (model.specific_location_of_well, "Access"),
#         (model.contact_special_requests_notes, "General"),
#         (model.well_measuring_notes, "Sampling Procedure"),
#         (model.sampling_scenario_notes, "Sampling Procedure"),
#         (historic_depth_note, "Historical"),
#     ):
#         if note_content is not None:
#             well_notes.append({"content": note_content, "note_type": note_type})
#
#     alternate_ids = []
#     for alternate_id, alternate_organization in (
#         (model.site_name, "NMBGMR"),
#         (model.ose_well_record_id, "NMOSE"),
#     ):
#         if alternate_id is not None:
#             alternate_ids.append(
#                 {
#                     "alternate_id": alternate_id,
#                     "alternate_organization": alternate_organization,
#                     "relation": "same_as",
#                 }
#             )
#
#     well_purposes = []
#     if model.well_purpose:
#         well_purposes.append(model.well_purpose)
#     if model.well_purpose_2:
#         well_purposes.append(model.well_purpose_2)
#
#     monitoring_frequencies = []
#     if model.monitoring_frequency:
#         monitoring_frequencies.append(
#             {
#                 "monitoring_frequency": model.monitoring_frequency,
#                 "start_date": date_time.date(),
#             }
#         )
#
#     data = CreateWell(
#         location_id=loc.id,
#         group_id=group.id,
#         name=name,
#         first_visit_date=date_time.date(),
#         well_depth=model.total_well_depth_ft,
#         well_depth_source=model.depth_source,
#         well_casing_diameter=model.casing_diameter_ft,
#         measuring_point_height=model.measuring_point_height_ft,
#         measuring_point_description=model.measuring_point_description,
#         well_completion_date=model.date_drilled,
#         well_completion_date_source=model.completion_source,
#         well_pump_type=model.well_pump_type,
#         well_pump_depth=model.well_pump_depth_ft,
#         is_suitable_for_datalogger=model.datalogger_possible,
#         is_open=model.is_open,
#         well_status=model.well_status,
#         notes=well_notes,
#         well_purposes=well_purposes,
#         monitoring_frequencies=monitoring_frequencies,
#     )
#     well_data = data.model_dump()
#
#     """
#     Developer's notes
#
#     the add_thing function also handles:
#     - MeasuringPointHistory
#     - GroupThingAssociation
#     - LocationThingAssociation
#     - DataProvenance for well_completion_date
#     - DataProvenance for well_depth
#     - Notes
#     - WellPurpose
#     - MonitoringFrequencyHistory
#     - StatusHistory for status_type 'Open Status'
#     - StatusHistory for status_type 'Datalogger Suitability Status'
#     - StatusHistory for status_type 'Well Status'
#     """
#     well = add_thing(
#         session=session, data=well_data, user=user, thing_type="water well"
#     )
#     session.refresh(well)
#
#     # ------------------
#     # Field Events and related tables
#     # ------------------
#     """
#     Developer's notes
#
#     These tables are not handled in add_thing because they are only relevant if
#     the well has been inventoried in the field, not if the well is added from
#     another source like a report, database, or map.
#     """
#
#     # add field event
#     fe = FieldEvent(
#         event_date=date_time,
#         notes="Initial field event from well inventory import",
#         thing_id=well.id,
#     )
#     session.add(fe)
#
#     # add field staff
#     for fsi, role in (
#         (model.field_staff, "Lead"),
#         (model.field_staff_2, "Participant"),
#         (model.field_staff_3, "Participant"),
#     ):
#         if not fsi:
#             continue
#
#         _add_field_staff(session, fsi, fe, role, user)
#
#     # add field activity
#     fa = FieldActivity(
#         field_event=fe,
#         activity_type="well inventory",
#         notes="Well inventory conducted during field event.",
#     )
#     session.add(fa)
#
#     # ------------------
#     # Contacts
#     # ------------------
#
#     # add contacts
#     contact_for_permissions = None
#     for idx in (1, 2):
#         contact_dict = _make_contact(model, well, idx)
#         if contact_dict:
#             contact = add_contact(session, contact_dict, user=user)
#
#             # Use the first created contact for permissions if available
#             if contact_for_permissions is None:
#                 contact_for_permissions = contact
#
#     # ------------------
#     # Permissions
#     # ------------------
#
#     # add permissions
#     for permission_type, permission_allowed in (
#         ("Water Level Sample", model.repeat_measurement_permission),
#         ("Water Chemistry Sample", model.sampling_permission),
#         ("Datalogger Installation", model.datalogger_installation_permission),
#     ):
#         if permission_allowed is not None:
#             permission = _make_well_permission(
#                 well=well,
#                 contact=contact_for_permissions,
#                 permission_type=permission_type,
#                 permission_allowed=permission_allowed,
#                 start_date=model.date_time.date(),
#             )
#             session.add(permission)
#
#     return model.well_name_point_id


# ============= EOF =============================================
