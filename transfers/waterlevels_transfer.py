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
import time
import uuid
from datetime import datetime
import json

import pandas as pd

from db import (
    Thing,
    Sample,
    Observation,
    FieldEvent,
    FieldActivity,
    FieldEventContactAssociation,
    Contact,
)
from transfers.util import (
    filter_to_valid_point_ids,
    logger,
    read_csv,
    convert_mt_to_utc,
    filter_by_valid_measuring_agency,
    lexicon_mapper,
)

# constants
SPACE_2 = " " * 2
SPACE_4 = " " * 4


def get_dt_utc(row):
    if pd.isna(row.DateMeasured):
        logger.critical(
            f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} because there is no DateMeasured"
        )
        return

    if pd.isna(row.TimeMeasured):
        fmt = "%Y-%m-%d"
        dt_measured = row.DateMeasured
    else:
        fmt = "%Y-%m-%d %H:%M:%S.%f"
        t = row.TimeMeasured
        # Truncate microseconds to 6 digits if present
        if "." in t:
            t = t[:-6]

        dt_measured = f"{row.DateMeasured} {t}"

    try:
        dt = datetime.strptime(dt_measured, fmt)
        return convert_mt_to_utc(dt)
    except ValueError as e:
        logger.critical(
            f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to "
            f"invalid date/time: {e}"
        )


def get_contacts_info(row, measured_by, measured_by_mapper):

    measuring_agency = (
        "Unknown" if pd.isna(row.MeasuringAgency) else row.MeasuringAgency
    )

    # ns --> names
    # os --> organizations
    # rs --> roles

    # TODO: get help figuring out (AMP)
    if measured_by in measured_by_mapper:
        args = measured_by_mapper[measured_by]
        if isinstance(args[0], list):
            ns, os, rs = zip(*args)
        else:
            ns = [args[0]]
            os = [args[1]]
            rs = [args[2]]
    elif measured_by is None:
        ns = [None]
        os = ["Unknown"]
        rs = ["Unknown"]
    elif measured_by in [
        "Anthony Chavez",
        "BEI",
        "BF/RG",
        "Borchert",
        "Borton & Cooper",
        "CDWR",
        "Chaves/Cruz",
        "Chavez/Cruz",
        "CM, AK",
        "Coons",
        "Cooper",
        "Corbin",
        "Crocker",
        "Cruz",
        "Cruz-Tribble",
        "Cruz/Frost",
        "D.Bird",
        "D.D.",
        "D.Duncan",
        "Dames & Moore",
        "Dames/Moore",
        "Dave Snider",
        "David N Jenkins",
        "David N. Jenkins",
        "DC",
        "Decker",
        "DL, TK",
        "DR",
        "DR, ST",
        "Duke Engring",
        "Duncan",
        "EA",
        "EA/HB",
        "Frost",
        "G.Boylan",
        "GLR, SC",
        "GLR, SK, SC",
        "GR, MM",
        "GR/PW",
        "GR/RG",
        "HB",
        "Heaton",
        "Horner-Crocker",
        "HR",
        "Hydrogeologic Serv",
        "J.Evans",
        "J.Frost",
        "Jenkins",
        "Johnson/Cruz",
        "Johnson/Robbins",
        "Kilmer/Jenkins",
        "KP, MR",
        "KP, MT",
        "Lazarus",
        "Mike Rodgers",
        "Mourant",
        "MWB Consultant",
        "Myers report",
        "Rankin",
        "Sandia Drillers",
        "SC, MR",
        "SdC",
        "SM&Assoc",
        "SMA",
        "Spiegel",
        "Spiegel & Baldwin",
        "SPRI",
        "Steve",
        "T.Decker",
        "Topol",
        "URS",
        "UTM",
        "VeneKlasen",
        "Vista del Oro",
    ]:
        # set name to measured_by so that water level is logged to that
        # person even if they are not known. this allows future updates
        ns = [measured_by]
        os = ["Unknown"]
        rs = ["Unknown"]
        logger.warning(
            f"{SPACE_4}The following record has not been mapped to a Contact: {row.MeasuredBy} // {row.MeasuringAgency} for PointID {row.PointID} (which comes from the WaterLevels table)"
        )

    elif measured_by in [
        "?",
        "Consultant",
        "Consulting Pro.",
        "Gamma log unit",
        "Pump company",
        "PumpService",
        "REPORTED",
        "Theis report",
        "Unknown",
        "Unknown; reported",
        "Water operator",
        "WWTP",
        "WWTP personnel",
    ]:
        # Unknowns
        ns = [None]
        os = [measuring_agency]
        rs = ["Unknown"]

    else:
        logger.critical(
            f"Skipping the following record because it has no mappings: {row.MeasuredBy} // {row.MeasuringAgency} for PointID {row.PointID}"
        )
        return

    return ns, os, rs


def transfer_water_levels(session):
    # keep a dictionary of created Contacts to avoid repeated SQL queries
    created_contacts = {}
    with open("transfers/data/measured_by_mapper.json", "r") as f:
        measured_by_mapper = json.load(f)

    wd = read_csv("WaterLevels")
    wd = filter_to_valid_point_ids(session, wd)
    wd = filter_by_valid_measuring_agency(wd)
    gwd = wd.groupby(["PointID"])

    start_time = time.time()
    for index, group in gwd:
        pointid = index[0]
        logger.info(f"Processing PointID: {pointid}")
        thing = session.query(Thing).where(Thing.name == pointid).first()
        if thing is None:
            logger.critical(
                f"Thing with PointID={pointid} not found. Skipping water levels"
            )
            continue

        n = len(group)
        for i, row in enumerate(group.itertuples()):
            if i and not i % 25:
                logger.info(
                    f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
                )
                session.commit()

            dt_utc = get_dt_utc(row)
            if dt_utc is None:
                continue

            if pd.isna(row.DepthToWater):
                logger.warning(
                    f"{SPACE_4}No sample and observation have been made for WaterLevels record with GlobalID {row.GlobalID} because DepthToWater is NULL"
                )
                continue

            release_status = "public" if row.PublicRelease else "private"

            """
            Developer's notes

            Assumes for manual water levels that the date/time of the water level
            measurement is the same as the date/time of the field event.
            """

            # --- FieldEvent ---
            # TODO: use create schema to validate data
            field_event = FieldEvent(
                thing=thing,
                event_date=dt_utc,
                release_status=release_status,
            )

            session.add(field_event)
            session.flush()

            logger.info(
                f"{SPACE_2}Created field event: ID {field_event.id} | Date {field_event.event_date} | Thing ID {field_event.thing.id} | Thing Name {field_event.thing.name}"
            )

            # --- FieldActivity ---
            # TODO: use create schema to validate data
            field_activity = FieldActivity(
                field_event=field_event,
                activity_type="groundwater level",
                release_status=release_status,
            )
            session.add(field_activity)
            session.flush()

            logger.info(
                f"{SPACE_4}Created field activity: ID {field_activity.id} | Type {field_activity.activity_type}"
            )

            measured_by = None if pd.isna(row.MeasuredBy) else row.MeasuredBy

            """
            Developer's notes

            Use existing contact for the thing if measured by is the owner
            """
            field_event_contacts = []
            if measured_by not in ["Owner", "Owner report", "Well owner"]:
                # --- Contact/FieldEventContactAssociation ---
                contact_names, contact_organizations, roles = get_contacts_info(
                    row, measured_by, measured_by_mapper
                )

                for i, c in enumerate(contact_names):
                    if c in created_contacts:
                        contact = created_contacts[c]
                    else:
                        # create new contact if not already created
                        name = contact_names[i]
                        organization = contact_organizations[i]
                        role = roles[i]

                        contact = Contact(
                            name=name,
                            role=role,
                            contact_type="Field Event Participant",
                            organization=organization,
                            nma_pk_waterlevels=row.GlobalID,
                        )
                        session.add(contact)
                        session.flush()  # to get the contact.id

                        logger.info(
                            f"{SPACE_4}Created contact: ID {contact.id} | Name {contact.name} | Role {contact.role} | Organization {contact.organization} | nma_pk_waterlevels {contact.nma_pk_waterlevels}"
                        )

                        created_contacts[c] = contact

                    field_event_contacts.append(contact)
            else:
                contact = thing.contacts[0]
                field_event_contacts.append(contact)

            """
            Developer's notes

            Assumes that the first listed contact is the lead and the
            person who took the sample. The subsequent contact will be
            participants in the field event
            """
            for i, fec in enumerate(field_event_contacts):
                field_event_contact = FieldEventContactAssociation(
                    field_event=field_event, contact=fec
                )
                if i == 0:
                    field_event_contact.field_contact_role = "Lead"
                    sampler = field_event_contact
                else:
                    field_event_contact.field_contact_role = "Participant"

                session.add(field_event_contact)
                session.flush()
                logger.info(
                    f"{SPACE_4}Created field event contact: ID {field_event_contact.id} | Contact Name {field_event_contact.contact.name} | Field Contact Role {field_event_contact.field_contact_role}"
                )

            # --- Sample ---
            if not pd.isna(row.MeasurementMethod):
                sample_method = lexicon_mapper.map_value(
                    f"LU_MeasurementMethod:{row.MeasurementMethod}"
                )
            else:
                sample_method = "null placeholder"

            # todo: use create schema to validate data
            sample = Sample(
                nma_pk_waterlevels=row.GlobalID,
                field_activity=field_activity,
                field_event_contact=sampler,
                sample_date=dt_utc,
                sample_matrix="water",
                sample_name=str(uuid.uuid4()),
                sample_method=sample_method,
                qc_type="Normal",
                depth_top=None,
                depth_bottom=None,
            )
            session.add(sample)
            session.flush()
            logger.info(
                f"{SPACE_4}Created sample: ID {sample.id} | Date {sample.sample_date} | Matrix {sample.sample_matrix} | Method {sample.sample_method}"
            )

            if not pd.isna(row.LevelStatus):
                level_status = lexicon_mapper.map_value(
                    f"LU_LevelStatus:{row.LevelStatus}"
                )
            else:
                level_status = None

            # TODO: use create schema to validate data

            # TODO: after sensors have been added to the database update sensor_id (or sensor) for waterlevels that come from db sensors (like e probes?)
            observation = Observation(
                nma_pk_waterlevels=row.GlobalID,
                sample=sample,
                sensor_id=None,
                analysis_method_id=None,
                observation_datetime=dt_utc,
                observed_property="groundwater level",
                value=row.DepthToWater,
                unit="ft",
                measuring_point_height=row.MPHeight,
                level_status=level_status,
            )
            session.add(observation)
            session.flush()
            logger.info(
                f"{SPACE_4}Created observation: ID {observation.id} | DT {observation.observation_datetime} | Value {observation.value} | MPHeight {observation.measuring_point_height} | nma_pk_waterlevels {observation.nma_pk_waterlevels}"
            )
        session.commit()


# ============= EOF =============================================
