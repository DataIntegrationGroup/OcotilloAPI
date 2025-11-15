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
from typing import Optional, Set

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, field_validator, model_validator

router = APIRouter(prefix="/well-inventory-csv")

REQUIRED_FIELDS = [
    "project",
    "well_name_point_id",
    "site_name",
    "date_time",
    "field_staff",
    "utm_easting",
    "utm_northing",
    "utm_zone",
    "elevation_ft",
    "elevation_method",
    "measuring_point_height_ft",
]

LEXICON_FIELDS = {
    "contact_role": {"owner", "manager"},
    "contact_type": {"owner", "manager"},
    "elevation_method": {"survey"},
    # Add other lexicon fields and their valid values as needed
}


class WellInventoryRow(BaseModel):
    project: str
    well_name_point_id: str
    site_name: str
    date_time: str
    field_staff: str
    utm_easting: float
    utm_northing: float
    utm_zone: int
    elevation_ft: float
    elevation_method: str
    measuring_point_height_ft: float

    # Optional lexicon fields
    contact_role: Optional[str] = None
    contact_type: Optional[str] = None

    @field_validator("date_time")
    def validate_date_time(cls, v):
        try:
            datetime.fromisoformat(v)
        except Exception:
            raise ValueError("Invalid date format")
        return v

    @field_validator("elevation_method")
    def validate_elevation_method(cls, v):
        if v is not None and v.lower() not in LEXICON_FIELDS["elevation_method"]:
            raise ValueError(f"Invalid lexicon value: {v}")
        return v

    @field_validator("contact_role")
    def validate_contact_role(cls, v):
        if v is not None and v.lower() not in LEXICON_FIELDS["contact_role"]:
            raise ValueError(f"Invalid lexicon value: {v}")
        return v

    @field_validator("contact_type")
    def validate_contact_type(cls, v):
        if v is not None and v.lower() not in LEXICON_FIELDS["contact_type"]:
            raise ValueError(f"Invalid lexicon value: {v}")
        return v

    @model_validator(mode="after")
    def check_required(cls, values):
        for field in REQUIRED_FIELDS:
            if getattr(values, field, None) in [None, ""]:
                raise ValueError(f"Field required: {field}")
        return values


@router.post("")
async def well_inventory_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
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
    seen_ids: Set[str] = set()
    for idx, row in enumerate(rows):
        row_errors = []
        # Check required fields before Pydantic validation
        for field in REQUIRED_FIELDS:
            if field not in row or row[field] in [None, ""]:
                row_errors.append(
                    {"row": idx + 1, "field": field, "error": "Field required"}
                )
        # Check uniqueness
        well_id = row.get("well_name_point_id")
        if well_id:
            if well_id in seen_ids:
                row_errors.append(
                    {
                        "row": idx + 1,
                        "field": "well_name_point_id",
                        "error": "Duplicate value for well_name_point_id",
                    }
                )
            else:
                seen_ids.add(well_id)
        # Only validate with Pydantic if required fields are present
        if not row_errors:
            try:
                model = WellInventoryRow(**row)
                wells.append({"well_name_point_id": model.well_name_point_id})
            except ValidationError as e:
                for err in e.errors():
                    row_errors.append(
                        {
                            "row": idx + 1,
                            "field": err["loc"][0],
                            "error": f"Value error, {err['msg']}",
                        }
                    )
            except ValueError as e:
                row_errors.append(
                    {"row": idx + 1, "field": "well_name_point_id", "error": str(e)}
                )
        validation_errors.extend(row_errors)
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
                "total_rows_imported": len(rows),
                "validation_errors_or_warnings": 0,
            },
            "wells": wells,
        },
    )


# ============= EOF =============================================
