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

from core.initializers import erase_and_rebuild_db
from db import (
    Location,
    Thing,
    LocationThingAssociation,
    Group,
    GroupThingAssociation,
    Sensor,
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
def add_location(context, session):
    loc = Location(
        # name="first location",
        # notes="these are some test notes",
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
    n = loc.add_note("Test location", "Other")
    session.add(n)
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
        # notes="These are some test well notes",
        # measuring_notes="These are some measuring notes",
        # water_notes="This are some water notes",
    )

    session.add(well)
    session.commit()

    assoc = LocationThingAssociation(location=location, thing=well)
    assoc.effective_start = "2025-02-01T00:00:00Z"
    session.add(assoc)
    session.commit()
    session.refresh(well)

    for nt, c in (
        ("Other", "well notes"),
        ("Water", "water notes"),
        ("Measuring", "measuring notes"),
    ):
        n = well.add_note(c, nt)
        session.add(n)

    session.commit()
    session.refresh(well)

    context.objects["wells"].append(well)
    return well


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
def add_sensor(context, session, sid):
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
def add_group(context, session, wells):
    group = Group(name="Collabnet")
    for w in wells:
        assoc = GroupThingAssociation(group=group, thing=w)
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


@add_context_object_container("transducer_observations")
def add_transducer_observation(context, session, block, deployment_id, value):
    obs = TransducerObservation(
        parameter_id=block.parameter_id,
        deployment_id=deployment_id,
        observation_datetime=datetime.now(),
        value=value,
    )
    session.add(obs)
    context.objects["transducer_observations"].append(obs)
    return obs


def before_all(context):
    context.objects = {}
    rebuild = False
    # rebuild = True
    if rebuild:
        erase_and_rebuild_db()

    with session_ctx() as session:

        loc_1 = add_location(context, session)
        loc_2 = add_location(context, session)
        loc_3 = add_location(context, session)
        loc_4 = add_location(context, session)

        well_1 = add_well(context, session, loc_1, name_num=1)
        well_2 = add_well(context, session, loc_2, name_num=2)
        well_3 = add_well(context, session, loc_3, name_num=3)
        spring_4 = add_spring(context, session, loc_4, name_num=4)
        sensor_1 = add_sensor(context, session, well_1.id)
        deployment = add_deployment(context, session, well_1.id, sensor_1.id)
        add_group(context, session, [well_1, well_2])

        # parameter ID can be hardcoded because init_parameter always creates the same one
        parameter = session.get(Parameter, 1)
        block = add_block(context, session, parameter)
        for i in range(1, 10):
            add_transducer_observation(
                context, session, block, deployment.id, random.random()
            )

        session.commit()


def after_all(context):
    with session_ctx() as session:
        for table in context.objects.values():
            for obj in table:
                session.delete(obj)
        session.commit()


# ============= EOF =============================================
