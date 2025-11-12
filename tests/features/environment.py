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
# =============== ================================================================
import random
from datetime import datetime, timedelta

from core.initializers import erase_and_rebuild_db, init_lexicon, init_parameter
from db import (
    Location,
    Thing,
    LocationThingAssociation,
    Group,
    GroupThingAssociation,
    Sensor,
    LexiconTerm,
    TransducerObservation,
    Parameter,
    Deployment,
    TransducerObservationBlock,
    StatusHistory,
    ThingIdLink,
    WellPurpose,
    MeasuringPointHistory,
)
from db.engine import session_ctx


def add_context_object_container(name):
    def wrapper(func):
        def closure(context, *args, **kwargs):
            if name not in context.objects:
                context.objects[name] = []
            return func(context, *args, **kwargs)

        return closure

    return wrapper


@add_context_object_container("locations")
def add_location(context, session):
    loc = Location(
        # name="first location",
        notes="these are some test notes",
        point="POINT(-107.949533 33.809665)",
        elevation=2464.9,
        release_status="draft",
        elevation_accuracy=100,
        elevation_method="Survey-grade GPS",
        coordinate_accuracy=50,
        coordinate_method="GPS, uncorrected",
    )
    session.add(loc)
    session.commit()
    session.refresh(loc)

    context.objects["locations"].append(loc)
    return loc


@add_context_object_container("wells")
def add_well(context, session, location, name_num):
    well = Thing(
        name=f"WL-{name_num:04d}",
        first_visit_date="2023-03-03",
        thing_type="water well",
        release_status="draft",
        well_depth=10,
        hole_depth=10,
        well_construction_notes="Test well construction notes",
        well_casing_diameter=5.0,
        well_casing_depth=10.0,
    )
    session.add(well)
    session.commit()

    assoc = LocationThingAssociation(location=location, thing=well)
    assoc.effective_start = "2025-02-01T00:00:00Z"
    session.add(assoc)
    session.commit()

    session.refresh(well)

    context.objects["wells"].append(well)
    return well


@add_context_object_container("well_purposes")
def add_well_purpose(context, session, well, purpose_term):
    purpose = WellPurpose(thing=well, purpose=purpose_term)
    session.add(purpose)
    session.commit()
    session.refresh(purpose)

    context.objects["well_purposes"].append(purpose)
    return purpose


@add_context_object_container("measuring_point_histories")
def add_measuring_point_history(context, session, well):
    mph = MeasuringPointHistory(
        thing=well,
        measuring_point_height=2,
        measuring_point_description="test description",
        start_date="2024-01-01",
        end_date=None,
        reason="Initial measuring point record",
    )
    session.add(mph)
    session.commit()
    session.refresh(mph)

    context.objects["measuring_point_histories"].append(mph)
    return mph


@add_context_object_container("springs")
def add_spring(context, session, location, name_num):
    spring = Thing(
        name=f"SP-{name_num:04d}",
        first_visit_date="2023-03-03",
        thing_type="spring",
        release_status="draft",
        # well_depth=10,
        # hole_depth=10,
        # well_construction_notes="Test well construction notes",
        # well_casing_diameter=5.0,
        # well_casing_depth=10.0,
    )
    session.add(spring)
    session.commit()

    assoc = LocationThingAssociation(location=location, thing=spring)
    assoc.effective_start = "2025-02-01T00:00:00Z"
    session.add(assoc)
    session.commit()

    session.refresh(spring)
    context.objects["springs"].append(spring)
    return spring


@add_context_object_container("sensors")
def add_sensor(context, session):
    sensor = Sensor(
        name="Test Sensor",
        sensor_type="Pressure Transducer",
        model="Model X",
        serial_no="123456",
        pcn_number="PCN123456",
        owner_agency="NMBGMR",
        sensor_status="In Service",
        notes="Test equipment",
        release_status="draft",
    )
    session.add(sensor)
    session.commit()
    session.refresh(sensor)

    context.objects["sensors"].append(sensor)
    return sensor


@add_context_object_container("groups")
def add_group(context, session, things):
    group = Group(
        name="Collabnet",
        description="Healy Collaborative Network",
        project_area=None,
        group_type="Monitoring Plan",
        monitoring_frequency="Quarterly",
    )
    for thing in things:
        assoc = GroupThingAssociation(group=group, thing=thing)
        session.add(assoc)

    session.add(group)
    session.commit()
    session.refresh(group)

    context.objects["groups"].append(group)
    return group


@add_context_object_container("deployments")
def add_deployment(context, session, tid, sid):
    deployment = Deployment(
        thing_id=tid,
        sensor_id=sid,
        installation_date=datetime.now(),
    )
    session.add(deployment)
    session.commit()
    session.refresh(deployment)

    context.objects["deployments"].append(deployment)
    return deployment


@add_context_object_container("blocks")
def add_block(context, session, parameter):
    block = TransducerObservationBlock(
        parameter_id=parameter.id,
        start_datetime=datetime.now() - timedelta(hours=1),
        end_datetime=datetime.now() + timedelta(hours=1),
        review_status="not reviewed",
    )

    session.add(block)
    session.commit()
    session.refresh(block)

    context.objects["blocks"].append(block)
    return block


@add_context_object_container("status_history")
def add_status_history(
    context,
    session,
    status_type,
    status_value,
    start_date,
    end_date,
    reason,
    target_id,
    target_table,
):
    status_history = StatusHistory(
        status_type=status_type,
        status_value=status_value,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        target_id=target_id,
        target_table=target_table,
    )

    session.add(status_history)
    session.commit()
    session.refresh(status_history)

    context.objects["status_history"].append(status_history)
    return status_history


@add_context_object_container("id_links")
def add_id_link(
    context, session, thing, relation, alternate_id, alternate_organization
):
    id_link = ThingIdLink(
        thing_id=thing.id,
        relation=relation,
        alternate_id=alternate_id,
        alternate_organization=alternate_organization,
    )
    session.add(id_link)
    session.commit()
    session.refresh(id_link)

    context.objects["id_links"].append(id_link)
    return id_link


def before_all(context):
    context.objects = {}

    force = False
    with session_ctx() as session:
        if session.query(LexiconTerm).count() == 0 or force:
            erase_and_rebuild_db(session)
            init_lexicon()
            init_parameter()

        loc_1 = add_location(context, session)
        loc_2 = add_location(context, session)
        loc_3 = add_location(context, session)
        loc_4 = add_location(context, session)

        well_1 = add_well(context, session, loc_1, name_num=1)
        well_2 = add_well(context, session, loc_2, name_num=2)
        well_3 = add_well(context, session, loc_3, name_num=3)
        spring_4 = add_spring(context, session, loc_4, name_num=4)
        sensor_1 = add_sensor(context, session)
        deployment = add_deployment(context, session, well_1.id, sensor_1.id)

        well_status_1 = add_status_history(
            context,
            session,
            status_type="Well Status",
            status_value="Active, pumping well",
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2021, 1, 1),
            reason="Initial status",
            target_id=context.objects["wells"][0].id,
            target_table="thing",
        )

        well_status_2 = add_status_history(
            context,
            session,
            status_type="Well Status",
            status_value="Destroyed, exists but not usable",
            start_date=datetime(2021, 1, 1),
            end_date=None,
            reason="Roving bovine",
            target_id=context.objects["wells"][0].id,
            target_table="thing",
        )

        monitoring_status_1 = add_status_history(
            context,
            session,
            status_type="Monitoring Status",
            status_value="Currently monitored",
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2021, 1, 1),
            reason="Initial monitoring status",
            target_id=context.objects["wells"][0].id,
            target_table="thing",
        )

        monitoring_status_2 = add_status_history(
            context,
            session,
            status_type="Monitoring Status",
            status_value="Not currently monitored",
            start_date=datetime(2021, 1, 1),
            end_date=None,
            reason="Roving bovine destroyed well",
            target_id=context.objects["wells"][0].id,
            target_table="thing",
        )

        measuring_point_history_1 = add_measuring_point_history(
            context, session, well=well_1
        )

        id_link_1 = add_id_link(
            context,
            session,
            thing=well_1,
            relation="same_as",
            alternate_id="12345678",
            alternate_organization="USGS",
        )

        id_link_2 = add_id_link(
            context,
            session,
            thing=well_1,
            relation="same_as",
            alternate_id="OSE-0001",
            alternate_organization="NMOSE",
        )

        id_link_3 = add_id_link(
            context,
            session,
            thing=well_1,
            relation="same_as",
            alternate_id="Roving Bovine Ranch Well #1",
            alternate_organization="NMBGMR",
        )

        group = add_group(context, session, [well_1, well_2])

        for purpose in ["Domestic", "Irrigation"]:
            add_well_purpose(context, session, well_1, purpose)

        # parameter ID can be hardcoded because init_parameter always creates the same one
        parameter = session.get(Parameter, 1)
        add_obs = add_block(context, session, parameter)
        if add_obs:
            for i in range(1, 10):
                obs = TransducerObservation(
                    parameter_id=parameter.id,
                    deployment_id=deployment.id,
                    observation_datetime=datetime.now(),
                    value=random.random(),
                )
                session.add(obs)
        session.commit()

        # the well needs to be refreshed to get all the new relationships
        session.refresh(well_1)


def after_all(context):
    with session_ctx() as session:
        for table in context.objects.values():
            for obj in table:
                session.delete(obj)
        session.commit()


# ============= EOF =============================================
