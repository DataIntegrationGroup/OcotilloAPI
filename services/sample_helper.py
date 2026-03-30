import logging
import time

from fastapi import HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload
from starlette.status import HTTP_404_NOT_FOUND

from db import (
    Contact,
    FieldActivity,
    FieldEvent,
    FieldEventParticipant,
    GroupThingAssociation,
    LocationThingAssociation,
    Sample,
    Thing,
    ThingAquiferAssociation,
    ThingContactAssociation,
)
from services.query_helper import order_sort_filter

logger = logging.getLogger(__name__)


THING_RESPONSE_BASE = (
    joinedload(Sample.field_activity)
    .joinedload(FieldActivity.field_event)
    .joinedload(FieldEvent.thing)
)


THING_RESPONSE_LOADER_OPTIONS = (
    THING_RESPONSE_BASE.selectinload(Thing.location_associations).selectinload(
        LocationThingAssociation.location
    ),
    THING_RESPONSE_BASE.selectinload(Thing.well_purposes),
    THING_RESPONSE_BASE.selectinload(Thing.well_casing_materials),
    THING_RESPONSE_BASE.selectinload(Thing.links),
    THING_RESPONSE_BASE.selectinload(Thing.measuring_points),
    THING_RESPONSE_BASE.selectinload(Thing.monitoring_frequencies),
    THING_RESPONSE_BASE.selectinload(Thing.aquifer_associations).selectinload(
        ThingAquiferAssociation.aquifer_system
    ),
    THING_RESPONSE_BASE.selectinload(Thing.group_associations).selectinload(
        GroupThingAssociation.group
    ),
    THING_RESPONSE_BASE.selectinload(Thing.notes),
    THING_RESPONSE_BASE.selectinload(Thing.permission_history),
    THING_RESPONSE_BASE.selectinload(Thing.data_provenance),
    THING_RESPONSE_BASE.selectinload(Thing.status_history),
)


CONTACT_RESPONSE_BASE = selectinload(Sample.field_event_participant)
CONTACT_RESPONSE_PARTICIPANT = CONTACT_RESPONSE_BASE.selectinload(
    FieldEventParticipant.participant
)
CONTACT_RESPONSE_THING_ASSOCIATIONS = CONTACT_RESPONSE_PARTICIPANT.selectinload(
    Contact.thing_associations
)


CONTACT_RESPONSE_LOADER_OPTIONS = (
    CONTACT_RESPONSE_PARTICIPANT.selectinload(Contact.emails),
    CONTACT_RESPONSE_PARTICIPANT.selectinload(Contact.phones),
    CONTACT_RESPONSE_PARTICIPANT.selectinload(Contact.addresses),
    CONTACT_RESPONSE_PARTICIPANT.selectinload(Contact.incomplete_nma_phones),
    CONTACT_RESPONSE_THING_ASSOCIATIONS.selectinload(ThingContactAssociation.thing),
    CONTACT_RESPONSE_PARTICIPANT.selectinload(Contact.notes),
)


SAMPLE_ACTIVITY_LOADER = joinedload(Sample.field_activity).joinedload(
    FieldActivity.field_event
)


SAMPLE_LOADER_OPTIONS = (
    SAMPLE_ACTIVITY_LOADER,
    *THING_RESPONSE_LOADER_OPTIONS,
    *CONTACT_RESPONSE_LOADER_OPTIONS,
)


def get_db_samples(
    session: Session,
    thing_id: int | None = None,
    order: str | None = None,
    sort: str | None = None,
    filter_: str | None = None,
):
    query = session.query(Sample).options(*SAMPLE_LOADER_OPTIONS)

    if thing_id:
        query = query.join(FieldActivity)
        query = query.join(FieldEvent)
        query = query.where(FieldEvent.thing_id == thing_id)

    query = order_sort_filter(query, Sample, sort, order, filter_)

    return paginate(query)


def get_sample_by_id_with_relationships(session: Session, sample_id: int) -> Sample:
    started_at = time.perf_counter()
    sql = select(Sample).where(Sample.id == sample_id)
    sql = sql.options(*SAMPLE_LOADER_OPTIONS)
    sample = session.execute(sql).unique().scalar_one_or_none()
    if sample is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Sample with ID {sample_id} not found.",
        )

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "sample lookup completed sample_id=%s duration_ms=%s",
        sample_id,
        duration_ms,
        extra={
            "event": "sample_lookup_completed",
            "sample_id": sample_id,
            "duration_ms": duration_ms,
        },
    )
    return sample
