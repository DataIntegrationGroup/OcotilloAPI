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
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Iterable, List

from db import Thing, FieldEvent, FieldActivity, Sample, Observation, Parameter
from db.engine import session_ctx
from pydantic import ValidationError
from schemas.water_level_csv import (
    WaterLevelCsvRow,
    WATER_LEVEL_REQUIRED_FIELDS,
    WATER_LEVEL_HEADER_ALIASES,
    WATER_LEVEL_IGNORED_FIELDS,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

REQUIRED_FIELDS: List[str] = list(WATER_LEVEL_REQUIRED_FIELDS)
HEADER_ALIASES: dict[str, str] = dict(WATER_LEVEL_HEADER_ALIASES)
IGNORED_FIELDS: set[str] = set(WATER_LEVEL_IGNORED_FIELDS)


@dataclass
class BulkUploadResult:
    exit_code: int
    stdout: str
    stderr: str
    payload: dict[str, Any]


@dataclass
class _ValidatedRow:
    row_index: int
    raw: dict[str, str]
    well: Thing
    field_staff: str
    sampler: str
    sample_method_term: str
    field_event_dt: datetime
    measurement_dt: datetime
    mp_height: float | None
    depth_to_water_ft: float | None
    level_status: str | None
    data_quality: str | None
    water_level_notes: str | None


def bulk_upload_water_levels(
    source_file: str | Path | bytes | BinaryIO, *, pretty_json: bool = False
) -> BulkUploadResult:
    """Parse a CSV of water-level measurements and write database rows."""

    try:
        headers, csv_rows = _read_csv(source_file)
    except FileNotFoundError:
        msg = f"File not found: {source_file}"
        payload = _build_payload([], [], 0, 0, 1, errors=[msg])
        stdout = _serialize_payload(payload, pretty_json)
        return BulkUploadResult(
            exit_code=1,
            stdout=stdout,
            stderr=msg,
            payload=payload,
        )

    validation_errors: list[str] = []
    created_rows: list[dict[str, Any]] = []

    with session_ctx() as session:
        parameter_id = _get_groundwater_level_parameter_id(session)

        # Validate headers early so we can short-circuit
        # without touching the DB.
        header_errors = _validate_headers(headers)
        if header_errors:
            validation_errors.extend(header_errors)
        else:
            valid_rows, row_errors = _validate_rows(session, csv_rows)
            validation_errors.extend(row_errors)

            if not validation_errors:
                try:
                    created_rows = _create_records(
                        session,
                        parameter_id,
                        valid_rows,
                    )
                    session.commit()
                except Exception as exc:  # pragma: no cover - safety fallback
                    session.rollback()
                    validation_errors.append(str(exc))

        if validation_errors:
            session.rollback()

    summary = {
        "total_rows_processed": len(csv_rows),
        "total_rows_imported": (len(created_rows) if not validation_errors else 0),
        "validation_errors_or_warnings": _count_rows_with_issues(validation_errors),
    }
    payload = _build_payload(
        csv_rows, created_rows, **summary, errors=validation_errors
    )
    stdout = _serialize_payload(payload, pretty_json)
    stderr = "\n".join(validation_errors)
    exit_code = 0 if not validation_errors else 1
    return BulkUploadResult(
        exit_code=exit_code, stdout=stdout, stderr=stderr, payload=payload
    )


def _serialize_payload(payload: dict[str, Any], pretty: bool) -> str:
    return json.dumps(payload, indent=2 if pretty else None)


def _count_rows_with_issues(errors: list[str]) -> int:
    """
    Count unique row numbers represented in validation errors.
    Falls back to total error count when row numbers are unavailable.
    """
    row_ids: set[int] = set()
    for err in errors:
        match = re.match(r"^Row\s+(\d+):", str(err))
        if match:
            row_ids.add(int(match.group(1)))

    if row_ids:
        return len(row_ids)
    return len(errors)


def _build_payload(
    csv_rows: Iterable[dict[str, Any]],
    created_rows: list[dict[str, Any]],
    total_rows_processed: int,
    total_rows_imported: int,
    validation_errors_or_warnings: int,
    *,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "summary": {
            "total_rows_processed": total_rows_processed,
            "total_rows_imported": total_rows_imported,
            "validation_errors_or_warnings": validation_errors_or_warnings,
        },
        "water_levels": created_rows,
        "validation_errors": errors,
    }


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
    rows: list[dict[str, str]] = []
    for row in reader:
        normalized_row: dict[str, str] = {}
        for k, v in row.items():
            if k is None:
                continue
            stripped_key = k.strip()
            if stripped_key in IGNORED_FIELDS:
                continue
            key = HEADER_ALIASES.get(stripped_key, stripped_key)
            value = v.strip() if isinstance(v, str) else v or ""
            # If both alias and canonical header are present,
            # preserve the first non-empty value.
            if key in normalized_row and normalized_row[key] and not value:
                continue
            normalized_row[key] = value
        rows.append(normalized_row)

    headers = [
        HEADER_ALIASES.get(h.strip(), h.strip())
        for h in (reader.fieldnames or [])
        if h is not None and h.strip() not in IGNORED_FIELDS
    ]
    return headers, rows


def _validate_headers(headers: list[str]) -> list[str]:
    missing = [field for field in REQUIRED_FIELDS if field not in headers]
    return [f"CSV missing required column '{field}'" for field in missing]


def _validate_rows(
    session: Session, rows: list[dict[str, str]]
) -> tuple[list[_ValidatedRow], list[str]]:
    valid_rows: list[_ValidatedRow] = []
    errors: list[str] = []

    wells_by_name: dict[str, Thing] = {}

    for idx, raw_row in enumerate(rows, start=1):
        normalized = {k: (v or "").strip() for k, v in raw_row.items() if k is not None}

        missing = [field for field in REQUIRED_FIELDS if not normalized.get(field)]
        if missing:
            errors.extend(
                [f"Row {idx}: Missing required field '{field}'" for field in missing]
            )
            continue

        try:
            model = WaterLevelCsvRow(**normalized)
        except ValidationError as exc:
            for err in exc.errors():
                location = ".".join(str(part) for part in err["loc"])
                message = err["msg"]
                errors.append(f"Row {idx}: {location} - {message}")
            continue

        well_name = model.well_name_point_id
        well = wells_by_name.get(well_name)
        if well is None:
            sql = select(Thing).where(Thing.name == well_name)
            well = session.scalars(sql).one_or_none()
            if well is None:
                errors.append(f"Row {idx}: Unknown well_name_point_id '{well_name}'")
                continue
            wells_by_name[well_name] = well

        valid_rows.append(
            _ValidatedRow(
                row_index=idx,
                raw={**normalized},
                well=well,
                field_staff=model.field_staff,
                sampler=model.measuring_person,
                sample_method_term=model.sample_method,
                field_event_dt=model.field_event_date_time,
                measurement_dt=model.water_level_date_time,
                mp_height=model.mp_height,
                depth_to_water_ft=model.depth_to_water_ft,
                level_status=model.level_status,
                data_quality=model.data_quality,
                water_level_notes=model.water_level_notes,
            )
        )

    return valid_rows, errors


def _create_records(
    session: Session, parameter_id: int, rows: list[_ValidatedRow]
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []

    for row in rows:
        field_event = FieldEvent(
            thing=row.well,
            event_date=row.field_event_dt,
            notes=_build_field_event_notes(row),
        )
        field_activity = FieldActivity(
            field_event=field_event,
            activity_type="groundwater level",
            notes=f"Sampler: {row.sampler}",
        )
        sample = Sample(
            field_activity=field_activity,
            sample_date=row.measurement_dt,
            sample_name=f"wl-{uuid.uuid4()}",
            sample_matrix="water",
            sample_method=row.sample_method_term,
            qc_type="Normal",
            notes=row.water_level_notes,
        )
        observation = Observation(
            sample=sample,
            observation_datetime=row.measurement_dt,
            parameter_id=parameter_id,
            value=row.depth_to_water_ft,
            unit="ft",
            measuring_point_height=row.mp_height,
            groundwater_level_reason=None,
            notes=_build_observation_notes(row),
        )
        session.add(field_event)
        session.add(field_activity)
        session.add(sample)
        session.add(observation)
        session.flush()

        created.append(
            {
                "well_name_point_id": row.raw["well_name_point_id"],
                "field_event_id": field_event.id,
                "field_activity_id": field_activity.id,
                "sample_id": sample.id,
                "observation_id": observation.id,
                "measurement_date_time": row.raw.get("water_level_date_time")
                or row.raw.get("measurement_date_time"),
                "level_status": row.level_status,
                "data_quality": row.data_quality,
            }
        )

    return created


def _build_field_event_notes(row: _ValidatedRow) -> str | None:
    parts = [f"Field staff: {row.field_staff}"]
    if row.water_level_notes:
        parts.append(row.water_level_notes)
    notes = " | ".join(part for part in parts if part)
    return notes or None


def _build_observation_notes(row: _ValidatedRow) -> str | None:
    parts = []
    if row.level_status is not None:
        parts.append(f"Level status: {row.level_status}")
    if row.data_quality is not None:
        parts.append(f"Data quality: {row.data_quality}")
    notes = " | ".join(parts)
    return notes or None


def _get_groundwater_level_parameter_id(session: Session) -> int:
    sql = select(Parameter.id).where(Parameter.parameter_name == "groundwater level")
    parameter_id = session.scalars(sql).one_or_none()
    if parameter_id is None:
        raise RuntimeError("Groundwater level parameter is not initialized")
    return parameter_id


# ============= EOF =============================================
