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
import logging
import time
from datetime import datetime
from typing import Any, Optional, Sequence
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from shapely import wkb
from shapely.geometry import mapping
from sqlalchemy import Text, cast, desc, func, or_, select
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.orm import Session, aliased, selectinload
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from api.pagination import CustomPage
from db import (
    Contact,
    DataProvenance,
    GroupThingAssociation,
    Location,
    LocationThingAssociation,
    MeasuringPointHistory,
    MonitoringFrequencyHistory,
    StatusHistory,
    Thing,
    ThingAquiferAssociation,
    ThingContactAssociation,
    ThingIdLink,
    WellCasingMaterial,
    WellPurpose,
    WellScreen,
)
from schemas.thing import WellResponse
from services.audit_helper import audit_add
from services.crud_helper import model_patcher
from services.env import get_bool_env
from services.exceptions_helper import PydanticStyleException
from services.geospatial_helper import make_within_wkt
from services.query_helper import order_sort_filter, simple_get_by_id

logger = logging.getLogger(__name__)


def is_debug_timing_enabled() -> bool:
    return bool(get_bool_env("API_DEBUG_TIMING", False))


WELL_DESCRIPTOR_MODEL_MAP = {
    "well_purposes": (WellPurpose, "purpose"),
    "well_casing_materials": (WellCasingMaterial, "material"),
}

WATER_WELL_LOADER_OPTIONS = [
    selectinload(Thing.location_associations).selectinload(
        LocationThingAssociation.location
    ),
    selectinload(Thing.contact_associations).selectinload(
        ThingContactAssociation.contact
    ),
    selectinload(Thing.well_purposes),
    selectinload(Thing.well_casing_materials),
    selectinload(Thing.links),
    selectinload(Thing.measuring_points),
    selectinload(Thing.monitoring_frequencies),
    selectinload(Thing.aquifer_associations).selectinload(
        ThingAquiferAssociation.aquifer_system
    ),
]

WATER_WELL_THING_TYPE = "water well"


def find_water_wells_by_name(
    session: Session,
    name: str,
    *,
    options: Sequence | None = None,
) -> list[Thing]:
    sql = (
        select(Thing)
        .where(
            Thing.name == name,
            Thing.thing_type == WATER_WELL_THING_TYPE,
        )
        .order_by(Thing.id.asc())
    )
    if options:
        sql = sql.options(*options)

    return session.scalars(sql).all()


def wkb_to_geojson(wkb_element):
    if wkb_element is None:
        return None
    geom = wkb.loads(bytes(wkb_element.data))
    return mapping(geom)


def get_db_things(
    filter_,
    order,
    query,
    session,
    sort,
    thing_type: Optional[str] = None,
    within: Optional[str] = None,
    name: Optional[str] = None,
    include_contacts: bool = False,
    filters: Optional[list[str]] = None,
) -> CustomPage[Any]:
    sql = select(Thing)

    # Querying logic
    #
    # We combine multiple search strategies:
    #
    # 1. Full-text search (tsvector)
    #    - Good for word-based and multi-word searches
    #    - Uses indexed search_vector column
    #
    # 2. Trigram fuzzy matching (% operator from pg_trgm)
    #    - Handles typos (e.g. "Aron" vs "Aaron")
    #
    # OR is used so any matching strategy can return a result.
    if query and query.strip():
        clean_query = query.strip()

        # Similarity scores (used ONLY for ranking, not filtering)
        #
        # These use pg_trgm's similarity() to compute how close each field
        # is to the search query. Higher = more similar.
        name_sim = func.similarity(Thing.name, clean_query)
        type_sim = func.similarity(Thing.thing_type, clean_query)

        search_conditions = [
            Thing.search_vector.op("@@")(
                func.parse_websearch(
                    cast("english", REGCONFIG),
                    cast(clean_query, Text),
                )
            ),
            Thing.name.op("%")(clean_query),
            Thing.thing_type.op("%")(clean_query),
        ]

        rank_expressions = [
            name_sim,
            type_sim,
        ]

        if include_contacts:
            contact_sim = func.coalesce(func.similarity(Contact.name, clean_query), 0)

            sql = sql.outerjoin(Thing.contact_associations).outerjoin(
                ThingContactAssociation.contact
            )

            search_conditions.append(Contact.name.op("%")(clean_query))
            rank_expressions.append(contact_sim)

        sql = (
            sql.where(or_(*search_conditions))
            .order_by(desc(func.greatest(*rank_expressions)))
            .distinct(Thing.id)
        )

        if include_contacts:
            sql = sql.options(
                selectinload(Thing.contact_associations).selectinload(
                    ThingContactAssociation.contact
                )
            )

    if thing_type:
        sql = sql.where(Thing.thing_type == thing_type)

        if thing_type == WATER_WELL_THING_TYPE:
            sql = sql.options(*WATER_WELL_LOADER_OPTIONS)
    else:
        # add all eager loads for generic thing query until/unless GET /thing is deprecated
        sql = sql.options(*WATER_WELL_LOADER_OPTIONS)

    if include_contacts:
        sql = sql.options(
            selectinload(Thing.contact_associations).selectinload(
                ThingContactAssociation.contact
            )
        )

    if name:
        sql = sql.where(Thing.name == name)

    if within:
        latest_assoc = (
            select(
                LocationThingAssociation.thing_id,
                func.max(LocationThingAssociation.effective_start).label("max_start"),
            )
            .group_by(LocationThingAssociation.thing_id)
            .subquery()
        )

        lta_alias = aliased(LocationThingAssociation)
        sql = (
            sql.join(lta_alias, Thing.id == lta_alias.thing_id)
            .join(Location, lta_alias.location_id == Location.id)
            .join(
                latest_assoc,
                (latest_assoc.c.thing_id == lta_alias.thing_id)
                & (latest_assoc.c.max_start == lta_alias.effective_start),
            )
        )
        sql = make_within_wkt(sql, within)

    merged_filters: list[str] | None = None
    if filters:
        merged_filters = list(filters)
    elif filter_:
        merged_filters = [filter_]

    sql = order_sort_filter(sql, Thing, sort, order, filters=merged_filters)

    return paginate(query=sql, conn=session)


def get_thing_type_from_request(request: Request) -> str:
    path = request.url.path
    path_components = path.split("/")
    if len(path_components) == 2:
        # no thing type specified in path
        thing_type_in_path = path_components[1]
    if len(path_components) >= 3:
        # thing type specified in path
        thing_type_in_path = path_components[2]

    thing_type = thing_type_in_path.replace("-", " ")
    return thing_type


def verify_thing_type_correspondence(thing: Thing, thing_type: str):
    if thing.thing_type != thing_type:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "thing_id"],
                    "type": "value_error",
                    "input": {"thing_id": thing.id},
                    "msg": f"Thing with ID {thing.id} is not a {thing_type} Thing. It is a {thing.thing_type} Thing.",
                }
            ],
        )


def get_thing_of_a_thing_type_by_id(session: Session, request: Request, thing_id: int):
    started_at = time.perf_counter()
    thing_type = get_thing_type_from_request(request)
    sql = select(Thing).where(Thing.id == thing_id)

    if thing_type == WATER_WELL_THING_TYPE:
        sql = sql.options(*WATER_WELL_LOADER_OPTIONS)

    thing = session.execute(sql).scalar_one_or_none()

    if not thing:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Thing with ID {thing_id} not found.",
        )

    verify_thing_type_correspondence(thing, thing_type)
    if is_debug_timing_enabled():
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "thing lookup completed path=%s thing_id=%s thing_type=%s duration_ms=%s",
            request.url.path,
            thing_id,
            thing_type,
            duration_ms,
            extra={
                "event": "thing_lookup_completed",
                "path": request.url.path,
                "thing_id": thing_id,
                "thing_type": thing_type,
                "duration_ms": duration_ms,
            },
        )

    return thing


def add_thing(
    session: Session,
    data: BaseModel | dict,
    user: dict = None,
    request: Request | None = None,
    thing_type: str | None = None,  # to be used only for data transfers, not the API
    commit: bool = True,
) -> Thing:
    if request is not None:
        thing_type = get_thing_type_from_request(request)

    # Extract data for related tables
    # Normalize Pydantic models to dictionaries so we can safely mutate with .pop()
    if isinstance(data, BaseModel):
        data = data.model_dump()

    # ---------
    # BEGIN UNIVERSAL THING RELATED TABLES
    # ---------

    notes = data.pop("notes", None)
    alternate_ids = data.pop("alternate_ids", None)
    location_id = data.pop("location_id", None)
    first_visit_date = data.get("first_visit_date")
    if first_visit_date is None:
        effective_start = None
    elif isinstance(first_visit_date, datetime):
        # Ensure datetime is timezone-aware; default to UTC if naive
        effective_start = (
            first_visit_date
            if first_visit_date.tzinfo is not None
            else first_visit_date.replace(tzinfo=ZoneInfo("UTC"))
        )
    else:
        # Interpret date-only values as midnight UTC on that date
        dt = datetime.combine(first_visit_date, datetime.min.time())
        effective_start = dt.replace(tzinfo=ZoneInfo("UTC"))
    group_id = data.pop("group_id", None)
    monitoring_frequencies = data.pop("monitoring_frequencies", None)
    datalogger_suitability_status = data.pop("is_suitable_for_datalogger", None)
    open_status = data.pop("is_open", None)
    well_status = data.pop("well_status", None)
    monitoring_status = data.pop("monitoring_status", None)

    # ----------
    # END UNIVERSAL THING RELATED TABLES
    # ----------

    # ----------
    # BEGIN WATER WELL SPECIFIC RELATED TABLES
    # ----------

    # measuring point info
    measuring_point_height = data.pop("measuring_point_height", None)
    measuring_point_description = data.pop("measuring_point_description", None)

    # data provenance info
    well_completion_date_source = data.pop("well_completion_date_source", None)
    well_construction_method_source = data.pop("well_construction_method_source", None)
    well_depth_source = data.pop("well_depth_source", None)

    # descriptor tables
    well_purposes = data.pop("well_purposes", None)
    well_casing_materials = data.pop("well_casing_materials", None)

    # ----------
    # END WATER WELL SPECIFIC RELATED TABLES
    # ----------

    try:
        thing = Thing(**data)
        thing.thing_type = thing_type

        audit_add(user, thing)

        session.add(thing)
        session.flush()
        session.refresh(thing)

        # ----------
        # BEGIN WATER WELL SPECIFIC LOGIC
        # ----------

        if thing_type == WATER_WELL_THING_TYPE:
            # Create MeasuringPointHistory record if measuring_point_height provided
            if measuring_point_height is not None:
                measuring_point_history = MeasuringPointHistory(
                    thing_id=thing.id,
                    measuring_point_height=measuring_point_height,
                    measuring_point_description=measuring_point_description,
                    start_date=datetime.now(tz=ZoneInfo("UTC")),
                    end_date=None,
                )
                audit_add(user, measuring_point_history)
                session.add(measuring_point_history)

            if well_completion_date_source is not None:
                dp = DataProvenance(
                    target_id=thing.id,
                    target_table="thing",
                    field_name="well_completion_date",
                    origin_type=well_completion_date_source,
                )
                audit_add(user, dp)
                session.add(dp)

            if well_depth_source is not None:
                dp = DataProvenance(
                    target_id=thing.id,
                    target_table="thing",
                    field_name="well_depth",
                    origin_type=well_depth_source,
                )
                audit_add(user, dp)
                session.add(dp)

            if well_construction_method_source is not None:
                dp = DataProvenance(
                    target_id=thing.id,
                    target_table="thing",
                    field_name="well_construction_method",
                    origin_source=well_construction_method_source,
                )
                audit_add(user, dp)
                session.add(dp)

            if well_purposes:
                for purpose in well_purposes:
                    wp = WellPurpose(thing_id=thing.id, purpose=purpose)
                    audit_add(user, wp)
                    session.add(wp)

            if well_casing_materials:
                for material in well_casing_materials:
                    wcm = WellCasingMaterial(thing_id=thing.id, material=material)
                    audit_add(user, wcm)
                    session.add(wcm)

            if datalogger_suitability_status is not None:
                if datalogger_suitability_status is True:
                    status_value = "Datalogger can be installed"
                else:
                    status_value = "Datalogger cannot be installed"
                dlss = StatusHistory(
                    target_id=thing.id,
                    target_table="thing",
                    status_value=status_value,
                    status_type="Datalogger Suitability Status",
                    start_date=effective_start,
                    end_date=None,
                )
                audit_add(user, dlss)
                session.add(dlss)

            if open_status is not None:
                if open_status is True:
                    status_value = "Open"
                else:
                    status_value = "Closed"
                os_status = StatusHistory(
                    target_id=thing.id,
                    target_table="thing",
                    status_value=status_value,
                    status_type="Open Status",
                    start_date=effective_start,
                    end_date=None,
                )
                audit_add(user, os_status)
                session.add(os_status)

            if well_status is not None:
                ws_status = StatusHistory(
                    target_id=thing.id,
                    target_table="thing",
                    status_value=well_status,
                    status_type="Well Status",
                    start_date=effective_start,
                    end_date=None,
                )
                audit_add(user, ws_status)
                session.add(ws_status)

            if monitoring_status is not None:
                ms_status = StatusHistory(
                    target_id=thing.id,
                    target_table="thing",
                    status_value=monitoring_status,
                    status_type="Monitoring Status",
                    start_date=effective_start,
                    end_date=None,
                )
                audit_add(user, ms_status)
                session.add(ms_status)

        # ----------
        # END WATER WELL SPECIFIC LOGIC
        # ----------

        # ----------
        # BEGIN UNIVERSAL THING RELATED LOGIC
        # ----------

        # endpoint catches ProgrammingError if location_id or group_id do not exist
        if group_id:
            assoc = GroupThingAssociation()
            audit_add(user, assoc)
            assoc.group_id = group_id
            assoc.thing_id = thing.id
            session.add(assoc)

        if location_id is not None:
            assoc = LocationThingAssociation()
            audit_add(user, assoc)
            assoc.location_id = location_id
            assoc.thing_id = thing.id
            assoc.effective_start = effective_start
            session.add(assoc)

        if notes:
            for n in notes:
                thing_note = thing.add_note(n["content"], n["note_type"])
                session.add(thing_note)
            session.flush()
            session.refresh(thing)

        if alternate_ids:
            for aid in alternate_ids:
                id_link = ThingIdLink(
                    thing_id=thing.id,
                    relation=aid["relation"],
                    alternate_id=aid["alternate_id"],
                    alternate_organization=aid["alternate_organization"],
                )
                session.add(id_link)

        if monitoring_frequencies:
            for mf in monitoring_frequencies:
                mfh = MonitoringFrequencyHistory(
                    thing_id=thing.id,
                    monitoring_frequency=mf["monitoring_frequency"],
                    start_date=mf["start_date"],
                    end_date=mf.get("end_date", None),
                )
                session.add(mfh)

        # ----------
        # END UNIVERSAL THING RELATED LOGIC
        # ----------
        if commit:
            session.commit()
            session.refresh(thing)

            for note in thing.notes:
                session.refresh(note)
        else:
            session.flush()

    except Exception as e:
        if commit:
            session.rollback()
        raise e

    return thing


def add_well_screen(session, well_screen_data: BaseModel, user: dict = None):
    try:
        well_screen_data_dump = well_screen_data.model_dump()
        well_screen = WellScreen(**well_screen_data_dump)
        audit_add(user, well_screen)

        session.add(well_screen)
        session.flush()

        thing = session.get(Thing, well_screen_data.thing_id)
        if thing.thing_type != "water well":
            raise PydanticStyleException(
                status_code=HTTP_409_CONFLICT,
                detail=[
                    {
                        "loc": ["body", "thing_id"],
                        "type": "value_error",
                        "input": {"thing_id": thing.id},
                        "msg": f"Thing with ID {thing.id} is not a water well Thing. It is a {thing.thing_type} Thing.",
                    }
                ],
            )

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    return well_screen


def patch_thing(
    session: Session,
    request: Request,
    thing_id: int,
    payload: BaseModel,
    user: dict,
):
    thing = simple_get_by_id(session, Thing, thing_id)

    thing_type = get_thing_type_from_request(request)
    verify_thing_type_correspondence(thing, thing_type)

    thing = model_patcher(session, Thing, thing_id, payload, user)
    return thing


def modify_well_descriptor_tables(
    session: Session, thing: Thing, payload: BaseModel, user: dict
) -> None:
    """
    This function is to add and update well descriptor tables when a Thing is created
    or updated. It deletes existing descriptor table records for the Thing if they
    exist and then adds the new data.
    """
    try:
        for descriptor_table in WELL_DESCRIPTOR_MODEL_MAP.keys():
            db_table, field_name = WELL_DESCRIPTOR_MODEL_MAP[descriptor_table]
            descriptor_table_data = payload.model_dump(exclude_unset=True).pop(
                descriptor_table, None
            )
            if descriptor_table_data:
                session.query(db_table).filter(db_table.thing_id == thing.id).delete()
                for ctd in descriptor_table_data:
                    inserts = {"thing_id": thing.id, field_name: ctd}
                    record = db_table(**inserts)
                    audit_add(user, record)
                    session.add(record)
        session.commit()

        # Thing needs to be refreshed to find associated child table data
        session.refresh(thing)
    except Exception as e:
        session.rollback()
        raise e


# ============= EOF =============================================
