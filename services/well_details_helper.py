import logging
import time
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db import (
    Contact,
    Deployment,
    FieldActivity,
    FieldEvent,
    FieldEventParticipant,
    Observation,
    Sample,
    Sensor,
    ThingContactAssociation,
    WellScreen,
)
from services.env import get_bool_env
from services.thing_helper import get_thing_of_a_thing_type_by_id

logger = logging.getLogger(__name__)


def is_debug_timing_enabled() -> bool:
    return bool(get_bool_env("API_DEBUG_TIMING", False))


def _log_payload_stage(payload_name: str, stage: str, thing_id: int, started_at: float):
    if not is_debug_timing_enabled():
        return
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "%s stage=%s thing_id=%s duration_ms=%s",
        payload_name,
        stage,
        thing_id,
        duration_ms,
        extra={
            "event": "well_payload_stage_timing",
            "payload_name": payload_name,
            "stage": stage,
            "thing_id": thing_id,
            "duration_ms": duration_ms,
        },
    )


@contextmanager
def _payload_stage_timer(payload_name: str, stage: str, thing_id: int):
    started_at = time.perf_counter()
    try:
        yield
    finally:
        _log_payload_stage(payload_name, stage, thing_id, started_at)


def get_well_details_payload(
    session: Session,
    request,
    thing_id: int,
    field_event_limit: int = 25,
):
    with _payload_stage_timer("well_details", "payload_total", thing_id):
        with _payload_stage_timer("well_details", "load_well", thing_id):
            well = get_thing_of_a_thing_type_by_id(session, request, thing_id)

        with _payload_stage_timer("well_details", "load_contacts", thing_id):
            contacts = session.scalars(
                select(Contact)
                .join(ThingContactAssociation)
                .where(ThingContactAssociation.thing_id == well.id)
                .options(
                    selectinload(Contact.emails),
                    selectinload(Contact.phones),
                    selectinload(Contact.addresses),
                    selectinload(Contact.incomplete_nma_phones),
                    selectinload(Contact.thing_associations).selectinload(
                        ThingContactAssociation.thing
                    ),
                )
                .order_by(Contact.id)
            ).all()

        with _payload_stage_timer("well_details", "load_sensors", thing_id):
            sensors = session.scalars(
                select(Sensor)
                .join(Deployment)
                .where(Deployment.thing_id == well.id)
                .distinct()
                .order_by(Sensor.id)
            ).all()

        with _payload_stage_timer("well_details", "load_deployments", thing_id):
            deployments = session.scalars(
                select(Deployment)
                .where(Deployment.thing_id == well.id)
                .options(selectinload(Deployment.sensor))
                .order_by(Deployment.installation_date.desc(), Deployment.id.desc())
            ).all()

        with _payload_stage_timer("well_details", "load_well_screens", thing_id):
            well_screens = session.scalars(
                select(WellScreen)
                .where(WellScreen.thing_id == well.id)
                .options(
                    selectinload(WellScreen.aquifer_system),
                    selectinload(WellScreen.geologic_formation),
                )
                .order_by(WellScreen.screen_depth_top.asc(), WellScreen.id.asc())
            ).all()

        with _payload_stage_timer("well_details", "load_field_events", thing_id):
            field_events = session.scalars(
                select(FieldEvent)
                .where(FieldEvent.thing_id == well.id)
                .options(
                    selectinload(FieldEvent.field_event_participants).selectinload(
                        FieldEventParticipant.participant
                    ),
                    selectinload(FieldEvent.field_activities)
                    .selectinload(FieldActivity.samples)
                    .selectinload(Sample.field_event_participant)
                    .selectinload(FieldEventParticipant.participant),
                    selectinload(FieldEvent.field_activities)
                    .selectinload(FieldActivity.samples)
                    .selectinload(Sample.observations)
                    .selectinload(Observation.parameter),
                )
                .order_by(FieldEvent.event_date.desc(), FieldEvent.id.desc())
                .limit(field_event_limit)
            ).all()

        return {
            "well": well,
            "contacts": contacts,
            "sensors": sensors,
            "deployments": deployments,
            "well_screens": well_screens,
            "field_events": field_events,
        }


def get_well_export_payload(
    session: Session,
    request,
    thing_id: int,
):
    payload_started_at = time.perf_counter()
    stage_started_at = time.perf_counter()
    well = get_thing_of_a_thing_type_by_id(session, request, thing_id)
    _log_payload_stage("well_export", "load_well", thing_id, stage_started_at)

    stage_started_at = time.perf_counter()
    contacts = session.scalars(
        select(Contact)
        .join(ThingContactAssociation)
        .where(ThingContactAssociation.thing_id == well.id)
        .options(
            selectinload(Contact.emails),
            selectinload(Contact.phones),
            selectinload(Contact.addresses),
            selectinload(Contact.incomplete_nma_phones),
            selectinload(Contact.thing_associations).selectinload(
                ThingContactAssociation.thing
            ),
        )
        .order_by(Contact.id)
    ).all()
    _log_payload_stage("well_export", "load_contacts", thing_id, stage_started_at)

    stage_started_at = time.perf_counter()
    sensors = session.scalars(
        select(Sensor)
        .join(Deployment)
        .where(Deployment.thing_id == well.id)
        .distinct()
        .order_by(Sensor.id)
    ).all()
    _log_payload_stage("well_export", "load_sensors", thing_id, stage_started_at)

    stage_started_at = time.perf_counter()
    deployments = session.scalars(
        select(Deployment)
        .where(Deployment.thing_id == well.id)
        .options(selectinload(Deployment.sensor))
        .order_by(Deployment.installation_date.desc(), Deployment.id.desc())
    ).all()
    _log_payload_stage(
        "well_export",
        "load_deployments",
        thing_id,
        stage_started_at,
    )
    _log_payload_stage("well_export", "payload_total", thing_id, payload_started_at)

    return {
        "well": well,
        "contacts": contacts,
        "sensors": sensors,
        "deployments": deployments,
    }
