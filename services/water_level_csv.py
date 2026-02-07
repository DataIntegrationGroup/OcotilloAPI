# ==============================================================================
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
# ==============================================================================
from __future__ import annotations

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import (
    Thing,
    FieldEvent,
    FieldActivity,
    Sample,
    Observation,
    Parameter,
    Contact,
    FieldEventParticipant,
)
from db.engine import session_ctx
from schemas.water_level_csv import (
    WaterLevelCsvRow,
    WaterLevelBulkUploadRow,
    WaterLevelBulkUploadResponse,
    WaterLevelCreatedRow,
    WaterLevelBulkUploadSummary,
    WaterLevelBulkUploadPayload,
)

REQUIRED_FIELDS = [
    key
    for key in WaterLevelCsvRow.model_fields.keys()
    if WaterLevelCsvRow.model_fields[key].default is not None
]


def bulk_upload_water_levels(
    source_file: str | Path | bytes | BinaryIO, *, pretty_json: bool = False
) -> WaterLevelBulkUploadResponse:
    """Parse a CSV of water-level measurements and write database rows."""

    try:
        headers, csv_rows = _read_csv(source_file)
    except FileNotFoundError:
        msg = f"File not found: {source_file}"
        payload = WaterLevelBulkUploadPayload(
            summary=WaterLevelBulkUploadSummary(
                total_rows_processed=0,
                total_rows_imported=0,
                total_validation_errors_or_warnings=0,
            ),
            water_levels=[],
            validation_errors=[],
        )
        stdout = _serialize_payload(payload, pretty_json)
        return WaterLevelBulkUploadResponse(
            exit_code=1, stdout=stdout, stderr=msg, payload=payload
        )

    validation_errors: list[str] = []
    created_rows: list[dict[str, Any]] = []

    with session_ctx() as session:
        parameter_id = _get_groundwater_level_parameter_id(session)

        # Validate headers early so we can short-circuit without touching the DB.
        header_errors = _validate_headers(headers)
        if header_errors:
            validation_errors.extend(header_errors)
        else:
            valid_rows, row_errors = _validate_rows(session, csv_rows)
            validation_errors.extend(row_errors)

            if not validation_errors:
                try:
                    created_rows = _create_records(session, parameter_id, valid_rows)
                    session.commit()
                except Exception as exc:  # pragma: no cover - safety fallback
                    session.rollback()
                    validation_errors.append(str(exc))

        if validation_errors:
            session.rollback()

    summary = WaterLevelBulkUploadSummary(
        total_rows_processed=len(csv_rows),
        total_rows_imported=len(created_rows) if not validation_errors else 0,
        total_validation_errors_or_warnings=len(validation_errors),
    )

    payload = WaterLevelBulkUploadPayload(
        summary=summary,
        water_levels=created_rows,
        validation_errors=validation_errors,
    )

    stdout = _serialize_payload(payload, pretty_json)
    stderr = "\n".join(validation_errors)
    exit_code = 0 if not validation_errors else 1
    return WaterLevelBulkUploadResponse(
        exit_code=exit_code, stdout=stdout, stderr=stderr, payload=payload
    )


def _serialize_payload(payload: WaterLevelBulkUploadPayload, pretty: bool) -> str:
    return json.dumps(payload.model_dump(), indent=2 if pretty else None)


def _read_csv(
    source: str | Path | bytes | BinaryIO,
) -> tuple[list[str], list[dict[str, str]]]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        text = path.read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        text = source.decode("utf-8")
    elif hasattr(source, "read"):
        data = source.read()
        if isinstance(data, bytes):
            text = data.decode("utf-8")
        else:
            text = str(data)
    else:
        raise TypeError("Unsupported CSV source type")

    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    rows = [
        {
            k.strip(): (v.strip() if isinstance(v, str) else v or "")
            for k, v in row.items()
        }
        for row in reader
    ]
    headers = [h.strip() for h in reader.fieldnames or []]
    return headers, rows


def _validate_headers(headers: list[str]) -> list[str]:
    missing = [field for field in REQUIRED_FIELDS if field not in headers]
    return [f"CSV missing required column '{field}'" for field in missing]


def _validate_rows(
    session: Session, rows: list[dict[str, str]]
) -> tuple[list[WaterLevelBulkUploadRow], list[str]]:
    # Caches to avoid repeated DB lookups
    contacts_by_name_cache: dict[str, Contact] = {}
    wells_by_name_cache: dict[str, Thing] = {}

    valid_rows: list[WaterLevelBulkUploadRow] = []
    errors: list[str] = []
    for idx, raw_row in enumerate(rows, start=1):
        # Normalize whitespace in all fields
        normalized_row = {k: (v or "").strip() for k, v in raw_row.items()}

        # allow all errors for a row to be logged at once instead of just the first one encountered
        error_in_row = False

        """
        Developer's note

        Pydantic handles all of the validation logic, including type 
        conversions and required field checks. If a field is missing or has an
        invalid value, Pydantic will raise a ValidationError, which we catch
        and convert into a user-friendly error message.
        """
        try:
            model = WaterLevelCsvRow(**normalized_row)
            WaterLevelCsvRow.model_validate(model)
        except ValidationError as exc:
            for err in exc.errors():
                location = ".".join(str(part) for part in err["loc"])
                message = err["msg"]
                errors.append(f"Row {idx}: {location} - {message}")
            # the model needs valid data to be serialized and processed/validated against the database, so we skip to the next row if there are validation errors from Pydantic
            continue

        # Verify that the well exists in the database
        well_name = model.well_name_point_id
        well = wells_by_name_cache.get(well_name, None)
        if well is None:
            sql = select(Thing).where(Thing.name == well_name)
            well = session.scalars(sql).one_or_none()
            if well is None:
                errors.append(f"Row {idx}: Unknown well_name_point_id '{well_name}'")
                error_in_row = True
            else:
                wells_by_name_cache[well_name] = well

        # verify that the well depth is greater than the water level depth bgs
        if well and well.well_depth <= model.depth_to_water_ft - model.mp_height:
            errors.append(
                f"Row {idx}: well_depth ({well.well_depth} ft) must be greater than depth_to_water_ft ({model.depth_to_water_ft} ft) minus mp_height ({model.mp_height} ft)"
            )
            error_in_row = True

        # Verify that the field staff are in the database
        """
        Developer's note

        This has to be repeated for each field staff person not in a for loop because field_staff_2 and _3 can be None
        """
        field_staff_name = model.field_staff
        field_staff_contact = contacts_by_name_cache.get(field_staff_name, None)
        if field_staff_contact is None:
            sql = select(Contact).where(Contact.name == field_staff_name)
            field_staff_contact = session.scalars(sql).one_or_none()
            if field_staff_contact is None:
                errors.append(f"Row {idx}: Unknown field_staff '{field_staff_name}'")
                error_in_row = True
            else:
                contacts_by_name_cache[field_staff_name] = field_staff_contact

        if model.field_staff_2:
            field_staff_2_name = model.field_staff_2
            field_staff_2_contact = contacts_by_name_cache.get(field_staff_2_name, None)
            if field_staff_2_contact is None:
                sql = select(Contact).where(Contact.name == field_staff_2_name)
                field_staff_2_contact = session.scalars(sql).one_or_none()
                if field_staff_2_contact is None:
                    errors.append(
                        f"Row {idx}: Unknown field_staff_2 '{field_staff_2_name}'"
                    )
                    error_in_row = True
                else:
                    contacts_by_name_cache[field_staff_2_name] = field_staff_2_contact
        else:
            field_staff_2_contact = None

        if model.field_staff_3:
            field_staff_3_name = model.field_staff_3
            field_staff_3_contact = contacts_by_name_cache.get(field_staff_3_name, None)
            if field_staff_3_contact is None:
                sql = select(Contact).where(Contact.name == field_staff_3_name)
                field_staff_3_contact = session.scalars(sql).one_or_none()
                if field_staff_3_contact is None:
                    errors.append(
                        f"Row {idx}: Unknown field_staff_3 '{field_staff_3_name}'"
                    )
                    error_in_row = True
                else:
                    contacts_by_name_cache[field_staff_3_name] = field_staff_3_contact
        else:
            field_staff_3_contact = None

        if error_in_row:
            continue

        # The Pydantic schema ensures that measuring_person is one of the field staff
        if model.measuring_person == model.field_staff:
            measuring_person_field_staff_index = 1
        elif model.measuring_person == model.field_staff_2:
            measuring_person_field_staff_index = 2
        else:
            measuring_person_field_staff_index = 3

        valid_model = WaterLevelBulkUploadRow(
            **model.model_dump(),
            well=well,
            field_staff_contact=field_staff_contact,
            field_staff_2_contact=field_staff_2_contact,
            field_staff_3_contact=field_staff_3_contact,
            measuring_person_field_staff_index=measuring_person_field_staff_index,
        )

        valid_rows.append(valid_model)

    return valid_rows, errors


def _create_records(
    session: Session, parameter_id: int, rows: list[WaterLevelBulkUploadRow]
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []

    for row in rows:
        # FieldEvent
        field_event = FieldEvent(
            thing=row.well,
            event_date=row.field_event_date_time,
        )
        session.add(field_event)

        # FieldActivity, FieldEventParticipant, Sample, Observation
        field_activity = FieldActivity(
            field_event=field_event,
            activity_type="groundwater level",
        )
        session.add(field_activity)

        # FieldEventParticipants
        field_event_participant_1 = FieldEventParticipant(
            field_event=field_event,
            participant=row.field_staff_contact,
            participant_role="Lead",
        )
        if row.field_staff_2_contact:
            field_event_participant_2 = FieldEventParticipant(
                field_event=field_event,
                participant=row.field_staff_2_contact,
                participant_role="Participant",
            )
            session.add(field_event_participant_2)
        else:
            field_event_participant_2 = None
        if row.field_staff_3_contact:
            field_event_participant_3 = FieldEventParticipant(
                field_event=field_event,
                participant=row.field_staff_3_contact,
                participant_role="Participant",
            )
            session.add(field_event_participant_3)
        else:
            field_event_participant_3 = None

        # Sample
        if row.measuring_person_field_staff_index == 1:
            sample_field_event_participant = field_event_participant_1
        elif row.measuring_person_field_staff_index == 2:
            sample_field_event_participant = field_event_participant_2
        else:
            sample_field_event_participant = field_event_participant_3

        sample = Sample(
            field_activity=field_activity,
            field_event_participant=sample_field_event_participant,
            sample_date=row.water_level_date_time,
            sample_name=f"wl-{uuid.uuid4()}",
            sample_matrix="water",
            sample_method=row.sample_method,
            qc_type="Normal",
        )
        session.add(sample)

        # Observation
        observation = Observation(
            sample=sample,
            observation_datetime=row.water_level_date_time,
            parameter_id=parameter_id,
            value=row.depth_to_water_ft,
            unit="ft",
            measuring_point_height=row.mp_height,
            groundwater_level_reason=row.level_status,
            groundwater_level_accuracy=row.data_quality,
            notes=row.water_level_notes,
        )
        session.add(observation)
        session.flush()

        created.append(
            WaterLevelCreatedRow(
                well_name_point_id=row.well_name_point_id,
                field_event_id=field_event.id,
                field_activity_id=field_activity.id,
                field_event_participant_1_id=field_event_participant_1.id,
                field_event_participant_2_id=(
                    field_event_participant_2.id if field_event_participant_2 else None
                ),
                field_event_participant_3_id=(
                    field_event_participant_3.id if field_event_participant_3 else None
                ),
                sample_id=sample.id,
                observation_id=observation.id,
                water_level_date_time=row.water_level_date_time.isoformat(),
                groundwater_level_reason=row.level_status,
                groundwater_level_accuracy=row.data_quality,
            )
        )

    return created


def _get_groundwater_level_parameter_id(session: Session) -> int:
    sql = select(Parameter.id).where(Parameter.parameter_name == "groundwater level")
    parameter_id = session.scalars(sql).one_or_none()
    if parameter_id is None:
        raise RuntimeError("Groundwater level parameter is not initialized")
    return parameter_id


# ============= EOF =============================================
