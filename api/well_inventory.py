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
from core.dependencies import session_dependency
from core.enums import ContactType, Role, ElevationMethod
from db import (
    Group,
    ThingIdLink,
    GroupThingAssociation,
    Location,
    LocationThingAssociation,
)
from db.thing import Thing
from services.util import transform_srid

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
async def well_inventory_csv(session: session_dependency, file: UploadFile = File(...)):
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
            models.append(model.model_dump())

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
        sorted(models, key=lambda x: x["project"]), key=lambda x: x["project"]
    ):
        # get project and add if does not exist
        sql = select(Group).where(Group.name == project)
        group = session.scalars(sql).one_or_none()
        if not group:
            group = Group(name=project)
            session.add(group)

        for model in items:
            name = model.get("well_name_point_id")
            site_name = model.get("site_name")
            date_time = model.get("date_time")

            # field_staff: str

            point = Point(model.get("utm_easting"), model.get("utm_northing"))
            if model.get("utm_zone") == 13:
                source_srid = SRID_UTM_ZONE_13N
            else:
                source_srid = SRID_UTM_ZONE_12N

            # Convert the point to a WGS84 coordinate system
            transformed_point = transform_srid(
                point, source_srid=source_srid, target_srid=SRID_WGS84
            )
            elevation_ft = float(model.get("elevation_ft"))
            elevation_m = convert_f_to_m(elevation_ft)
            elevation_method = model.get("elevation_method")
            measuring_point_height_ft = model.get("measuring_point_height_ft")

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
