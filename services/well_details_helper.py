import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from db import (
    Contact,
    Deployment,
    FieldActivity,
    FieldEvent,
    FieldEventParticipant,
    Observation,
    Parameter,
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


def get_well_details_payload(
    session: Session,
    request,
    thing_id: int,
    recent_observation_limit: int = 100,
):
    payload_started_at = time.perf_counter()
    stage_started_at = time.perf_counter()
    well = get_thing_of_a_thing_type_by_id(session, request, thing_id)
    _log_payload_stage("well_details", "load_well", thing_id, stage_started_at)

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
    _log_payload_stage("well_details", "load_contacts", thing_id, stage_started_at)

    stage_started_at = time.perf_counter()
    sensors = session.scalars(
        select(Sensor)
        .join(Deployment)
        .where(Deployment.thing_id == well.id)
        .distinct()
        .order_by(Sensor.id)
    ).all()
    _log_payload_stage("well_details", "load_sensors", thing_id, stage_started_at)

    stage_started_at = time.perf_counter()
    deployments = session.scalars(
        select(Deployment)
        .where(Deployment.thing_id == well.id)
        .options(selectinload(Deployment.sensor))
        .order_by(Deployment.installation_date.desc(), Deployment.id.desc())
    ).all()
    _log_payload_stage(
        "well_details",
        "load_deployments",
        thing_id,
        stage_started_at,
    )

    stage_started_at = time.perf_counter()
    well_screens = session.scalars(
        select(WellScreen)
        .where(WellScreen.thing_id == well.id)
        .order_by(WellScreen.screen_depth_top.asc(), WellScreen.id.asc())
    ).all()
    _log_payload_stage(
        "well_details",
        "load_well_screens",
        thing_id,
        stage_started_at,
    )

    stage_started_at = time.perf_counter()
    groundwater_parameter_id = (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )
    _log_payload_stage(
        "well_details",
        "resolve_groundwater_parameter",
        thing_id,
        stage_started_at,
    )

    stage_started_at = time.perf_counter()
    recent_groundwater_level_observations = session.scalars(
        select(Observation)
        .join(Sample)
        .join(FieldActivity)
        .join(FieldEvent)
        .where(
            FieldEvent.thing_id == well.id,
            Observation.parameter_id == groundwater_parameter_id,
        )
        .options(selectinload(Observation.parameter))
        .order_by(Observation.observation_datetime.desc(), Observation.id.desc())
        .limit(recent_observation_limit)
    ).all()
    _log_payload_stage(
        "well_details",
        "load_recent_groundwater_level_observations",
        thing_id,
        stage_started_at,
    )

    latest_field_event_sample = None
    if recent_groundwater_level_observations:
        latest_sample_id = recent_groundwater_level_observations[0].sample_id
        stage_started_at = time.perf_counter()
        latest_field_event_sample = session.scalar(
            select(Sample)
            .where(Sample.id == latest_sample_id)
            .options(
                joinedload(Sample.field_activity)
                .joinedload(FieldActivity.field_event)
                .joinedload(FieldEvent.thing),
                joinedload(Sample.field_event_participant).joinedload(
                    FieldEventParticipant.participant
                ),
            )
        )
        _log_payload_stage(
            "well_details",
            "load_latest_field_event_sample",
            thing_id,
            stage_started_at,
        )

    _log_payload_stage(
        "well_details",
        "payload_total",
        thing_id,
        payload_started_at,
    )

    return {
        "well": well,
        "contacts": contacts,
        "sensors": sensors,
        "deployments": deployments,
        "well_screens": well_screens,
        "recent_groundwater_level_observations": recent_groundwater_level_observations,
        "latest_field_event_sample": latest_field_event_sample,
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
