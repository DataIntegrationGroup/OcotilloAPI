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
def add_location(context, session, lid):
    loc = session.get(Location, lid)

    if not loc:
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
def add_well(context, session, location, thing_id):
    well = session.get(Thing, thing_id)
    if well is None:
        well = Thing(
            name=f"WL-{thing_id:04d}",
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


@add_context_object_container("springs")
def add_spring(context, session, location, thing_id):
    spring = session.get(Thing, thing_id)
    if spring is None:
        spring = Thing(
            name=f"SP-{thing_id:04d}",
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


@add_context_object_container("sensors")
def add_sensor(context, session, sid):
    sensor = session.get(Sensor, sid)
    if sensor is None:
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
def add_group(context, session, wells, gid):
    group = session.get(Group, gid)
    if not group:
        group = Group(name="Collabnet")
        for w in wells:
            assoc = GroupThingAssociation(group=group, thing=w)
            session.add(assoc)

        session.add(group)
        session.commit()
        session.refresh(group)

    context.objects["groups"].append(group)


@add_context_object_container("deployments")
def add_deployment(context, session, sid):
    deployment = session.get(Deployment, sid)
    if deployment is None:
        deployment = Deployment(
            thing_id=1,
            sensor_id=1,
            installation_date=datetime.now(),
        )
        session.add(deployment)
        session.commit()
        session.refresh(deployment)

    context.objects["deployments"].append(deployment)
    return deployment


@add_context_object_container("blocks")
def add_block(context, session, parameter):
    block = (
        session.query(TransducerObservationBlock)
        .filter(TransducerObservationBlock.parameter_id == parameter.id)
        .one_or_none()
    )
    add_obs = False
    if block is None:
        block = TransducerObservationBlock(
            parameter_id=parameter.id,
            start_datetime=datetime.now() - timedelta(hours=1),
            end_datetime=datetime.now() + timedelta(hours=1),
            review_status="not reviewed",
        )

        session.add(block)
        session.commit()
        session.refresh(block)
        add_obs = True

    context.objects["blocks"].append(block)
    return add_obs


def before_all(context):
    context.objects = {}

    force = True
    with session_ctx() as session:
        if force or session.query(LexiconTerm).count() == 0:
            erase_and_rebuild_db(session)
            init_lexicon()
            init_parameter()

        loc = add_location(context, session, 1)
        loc2 = add_location(context, session, 2)
        loc3 = add_location(context, session, 3)
        loc4 = add_location(context, session, 4)

        add_well(context, session, loc, 1)
        add_well(context, session, loc2, 2)
        add_well(context, session, loc3, 3)
        add_spring(context, session, loc4, 4)
        add_sensor(context, session, 1)
        deployment = add_deployment(context, session, 1)

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


def after_all(context):
    pass


# ============= EOF =============================================
