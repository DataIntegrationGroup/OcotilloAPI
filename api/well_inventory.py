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
from pydantic import BaseModel, ValidationError

from core.enums import ContactType, Role, ElevationMethod

router = APIRouter(prefix="/well-inventory-csv")


class WellInventoryRow(BaseModel):
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

    # Optional lexicon fields
    contact_role: Optional[Role] = None
    contact_type: Optional[ContactType] = None


@router.post("")
async def well_inventory_csv(file: UploadFile = File(...)):
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
            wells.append({"well_name_point_id": model.well_name_point_id})
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
