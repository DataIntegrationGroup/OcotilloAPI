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
    StatusHistory,
    ThingIdLink,
    WellPurpose,
    MeasuringPointHistory,
    MonitoringFrequencyHistory,
    DataProvenance,
    Contact,
)
from db.engine import session_ctx
from services.util import get_bool_env


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
        # elevation_accuracy=100,
        # elevation_method="Survey-grade GPS",
        # coordinate_accuracy=50,
        # coordinate_method="GPS, uncorrected",
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


@add_context_object_container("monitoring_frequency_histories")
def add_monitoring_frequency_history(
    context, session, well, monitoring_frequency, start_date, end_date
):
    mfh = MonitoringFrequencyHistory(
        thing=well,
        monitoring_frequency=monitoring_frequency,
        start_date=start_date,
        end_date=end_date,
    )
    session.add(mfh)
    session.commit()
    session.refresh(mfh)

    context.objects["monitoring_frequency_histories"].append(mfh)
    return mfh


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


@add_context_object_container("data_provenance")
def add_data_provenance(
    context,
    session,
    target_id,
    target_table,
    field_name,
    origin_source,
    collection_method=None,
    accuracy_value=None,
    accuracy_unit=None,
):
    data_provenance = DataProvenance(
        field_name=field_name,
        collection_method=collection_method,
        target_id=target_id,
        target_table=target_table,
        origin_source=origin_source,
        accuracy_value=accuracy_value,
        accuracy_unit=accuracy_unit,
    )

    session.add(data_provenance)
    session.commit()
    session.refresh(data_provenance)

    context.objects["data_provenance"].append(data_provenance)
    return data_provenance


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

    if get_bool_env("REBUILD_DB", False):
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
        sensor_1 = add_sensor(context, session)
        deployment = add_deployment(context, session, well_1.id, sensor_1.id)

        for well in [well_1, well_2, well_3]:
            add_measuring_point_history(context, session, well=well)

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

        monitoring_frequency_histories = [
            (well_1, "Monthly", "2020-01-01", "2021-01-01"),
            (well_1, "Annual", "2020-01-01", None),
        ]
        for (
            well,
            monitoring_frequency,
            start_date,
            end_date,
        ) in monitoring_frequency_histories:
            add_monitoring_frequency_history(
                context, session, well, monitoring_frequency, start_date, end_date
            )

        id_links = [
            ("same_as", "12345678", "USGS"),
            ("same_as", "OSE-0001", "NMOSE"),
            ("same_as", "Roving Bovine Ranch Well #1", "NMBGMR"),
        ]
        for relation, alternate_id, alternate_organization in id_links:
            add_id_link(
                context,
                session,
                thing=well_1,
                relation=relation,
                alternate_id=alternate_id,
                alternate_organization=alternate_organization,
            )

        group = add_group(context, session, [well_1, well_2])

        data_provenance_entries = [
            (
                loc_1.id,
                "location",
                "elevation",
                "Private geologist, consultant or univ associate",
                "LiDAR DEM",
                None,
                None,
            ),
            (well_1.id, "thing", "well_depth", "Other", None, None, None),
        ]
        for (
            target_id,
            target_table,
            field_name,
            origin_source,
            collection_method,
            accuracy_value,
            accuracy_unit,
        ) in data_provenance_entries:
            add_data_provenance(
                context,
                session,
                target_id,
                target_table,
                field_name,
                origin_source,
                collection_method,
                accuracy_value,
                accuracy_unit,
            )

        # parameter ID can be hardcoded because init_parameter always creates the same one
        parameter = session.get(Parameter, 1)
        block = add_block(context, session, parameter)
        for i in range(1, 10):
            add_transducer_observation(
                context, session, block, deployment.id, random.random()
            )

        session.commit()

        # the following needs to be refreshed to get all the new relationships
        session.refresh(well_1)
        session.refresh(loc_1)


def after_all(context):
    with session_ctx() as session:
        for table in context.objects.values():
            for obj in table:
                obj = session.get(type(obj), obj.id)
                if obj:
                    session.delete(obj)

        # session.query(TransducerObservationBlock).delete()
        # session.query(TransducerObservation).delete()
        # session.query(StatusHistory).delete()
        # session.query(DataProvenance).delete()
        # session.query(ThingIdLink).delete()
        # session.query(Parameter).delete()
        # session.query(Deployment).delete()
        # session.query(GroupThingAssociation).delete()
        # session.query(Group).delete()
        # session.query(Sensor).delete()
        session.query(Contact).delete()
        session.commit()


# ============= EOF =============================================
