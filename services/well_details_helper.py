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
from services.thing_helper import get_thing_of_a_thing_type_by_id


def get_well_details_payload(
    session: Session,
    request,
    thing_id: int,
    recent_observation_limit: int = 100,
):
    well = get_thing_of_a_thing_type_by_id(session, request, thing_id)

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

    sensors = session.scalars(
        select(Sensor)
        .join(Deployment)
        .where(Deployment.thing_id == well.id)
        .distinct()
        .order_by(Sensor.id)
    ).all()

    deployments = session.scalars(
        select(Deployment)
        .where(Deployment.thing_id == well.id)
        .options(selectinload(Deployment.sensor))
        .order_by(Deployment.installation_date.desc(), Deployment.id.desc())
    ).all()

    well_screens = session.scalars(
        select(WellScreen)
        .where(WellScreen.thing_id == well.id)
        .order_by(WellScreen.screen_depth_top.asc(), WellScreen.id.asc())
    ).all()

    groundwater_parameter_id = (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )

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

    latest_field_event_sample = None
    if recent_groundwater_level_observations:
        latest_sample_id = recent_groundwater_level_observations[0].sample_id
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

    return {
        "well": well,
        "contacts": contacts,
        "sensors": sensors,
        "deployments": deployments,
        "well_screens": well_screens,
        "recent_groundwater_level_observations": recent_groundwater_level_observations,
        "latest_field_event_sample": latest_field_event_sample,
    }
