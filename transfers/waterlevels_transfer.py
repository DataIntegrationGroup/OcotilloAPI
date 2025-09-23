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

import pandas as pd

from db import (
    Thing,
    Sample,
    Observation,
    FieldEvent,
    FieldActivity,
    # FieldEventContactAssociation,
    Contact,
)
from transfers.util import (
    filter_to_valid_point_ids,
    logger,
    read_csv,
    convert_mt_to_utc,
    lu_to_lexicon_map,
)

# keep a dictionary of created Contacts to avoid repeated SQL queries
CREATED_CONTACTS = {}


def transfer_water_levels(session):

    wd = read_csv("WaterLevels")
    wd = filter_to_valid_point_ids(session, wd)
    gwd = wd.groupby(["PointID"])

    start_time = time.time()
    for index, group in gwd:
        logger.info(f"Processing PointID: {index[0]}")
        n = len(group)
        for i, row in enumerate(group.itertuples()):
            if i and not i % 25:
                logger.info(
                    f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
                )
                session.commit()

            if pd.isna(row.DepthToWater) or pd.isna(row.DateMeasured):
                logger.warning(f"Skipping row {row.Index} due to missing data.")
                continue

            if not pd.isna(row.TimeMeasured):
                dt_measured = f"{row.DateMeasured} {row.TimeMeasured}"
            else:
                dt_measured = f"{row.DateMeasured} 12:00:00 AM"

            dt = datetime.strptime(dt_measured, "%Y-%m-%d %I:%M:%S %p")
            dt_utc = convert_mt_to_utc(dt)

            thing = session.query(Thing).where(Thing.name == row.PointID).first()
            if thing is None:
                logger.warning(
                    f"Thing with PointID {row.PointID} not found. Skipping water level."
                )
                continue

            release_status = "public" if row.PublicRelease else "private"

            """
            Developer's notes

            Assumes for manual water levels that the date/time of the water level
            measurement is the same as the date/time of the field event.
            """

            if pd.isna(row.MeasuringAgency):
                collecting_organization = "Unknown"
            else:
                collecting_organization = row.MeasuringAgency

            # --- FieldEvent ---

            field_event = FieldEvent(
                thing=thing,
                event_date=dt_utc,
                collecting_organization=collecting_organization,
                release_status=release_status,
            )

            session.add(field_event)
            session.flush()

            # --- FieldActivity ---

            field_activity = FieldActivity(
                field_event=field_event,
                activity_type="groundwater level",
                release_status=release_status,
            )
            session.add(field_activity)
            session.flush()

            # --- Contact/FieldEventContactAssociation ---
            # AMP feedback:
            # - is Duke Engring the same as Duke University? Is it from their engineering school?
            # - speak with AMP to help identify all initials
            """
            Developer's notes

            - If MeasuredBy is NULL
              - If this is the first NULL that has been encountered, create a
                Contact with name "NM_Aquifer NULL"
              - If this is not the first NULL that has been encountered, use
                the existing Contact with name "NM_Aquifer NULL"
            - If MeasuredBy is not NULL
                - If a Contact with name MeasuredBy already exists, use it
                - If a Contact with name MeasuredBy does not exist, create it
            """
            if pd.isna(row.MeasuredBy):
                measured_by = None
            else:
                measured_by = row.MeasuredBy

            # sometimes multiple contacts need to be created, so they'll be stored in a list
            # the nth name corresponds with the nth organization
            contact_names = []
            contact_organizations = []
            roles = []
            # --- Companies/Organizations ---
            if "AGW" in measured_by:
                contact_names.append("A. G. Wassenaar, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "CDM":
                contact_names.append("CDM Smith")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "CH2MHill":
                contact_names.append("CH2M Hill")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "Chevron personnel":
                contact_names.append("Chevron")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by in [
                "City of  Santa Fe",
                "City of Santa  Fe",
                "City of Santa Fe",
                "CityofSantaFe",
            ]:
                contact_names.append(None)
                contact_organizations.append("CSF")
                roles.append("Organization")
            elif measured_by in ["DBSA", "DBStephens & Assoc"]:
                contact_names.append("Daniel B. Stephens & Associates, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif "Glorieta Geoscienc" in measured_by:
                contact_names.append("Glorieta Geoscience, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "Golder Ass. For OSE":
                contact_names.append("Golder Associates, Inc")
                contact_organizations.append("NMOSE")
                roles.append("Organization")
            elif measured_by == "Hydroscience Assoc.":
                contact_names.append("Hydroscience Associates, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif "IC Tech" in measured_by or "ICTech" in measured_by:
                contact_names.append("IC Tech, Inc")
                contact_organizations.append("NMOSE")
                roles.append("Organization")
            elif "John Shomaker" in measured_by:
                contact_names.append("John Shomaker & Associates, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "Mario Gonzales NMRWA":
                contact_names.append("Mario Gonzales")
                contact_organizations.append("NMRWA")
                roles.append("Organization")
            elif "Minton" in measured_by:
                contact_names.append("Minton Engineers")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif "MJ Darr" in measured_by:
                contact_names.append("MJDarrconsult, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "NMOSE?":
                contact_names.append(None)
                contact_organizations.append("NMOSE")
                roles.append("Organization")
            elif measured_by == "OSE":
                contact_names.append(None)
                contact_organizations.append("NMOSE")
                roles.append("Organization")
            elif measured_by == "OSE; Doug Rappuhn":
                contact_names.append("Doug Rappuhn")
                contact_organizations.append("NMOSE")
                roles.append("Organization")
            elif measured_by in ["Pump company", "PumpService"]:
                contact_names.append(None)
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "PVACD person":
                contact_names.append(None)
                contact_organizations.append("PVACD")
                roles.append("Organization")
            elif measured_by in ["Rodgers & Co", "Rodgers & Co."]:
                contact_names.append("Rodgers & Company, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by == "Sandia National labs":
                contact_names.append(None)
                contact_organizations.append("SNL")
                roles.append("Organization")
            elif measured_by in ["Santa Fe County", "SFCounty LF staff"]:
                contact_names.append(None)
                contact_organizations.append("SFC")
                roles.append("Organization")
            elif measured_by == "SFC/Frost":
                contact_names.append("Frost")
                contact_organizations.append("SFC")
                roles.append("Organization")
            elif measured_by == "Statewide Drilling":
                contact_names.append("Statewide Drilling, Inc")
                contact_organizations.append(collecting_organization)
                roles.append("Organization")
            elif measured_by in [
                "?",
                "Consultant",
                "Consulting Pro.",
                "REPORTED",
                "Unknown",
                "Unknown; reported",
                "Water operator",
                "WWTP",
                "WWTP personnel",
            ]:
                # if measured_by
                contact_names.append(None)
                contact_organizations.append(collecting_organization)
                roles.append("Unknown")
            elif measured_by in [
                "NMBGMR",
                "NMED",
                "NMOSE",
                "NPS",
                "Otero SWCD",
                "SFC",
                "Taos SWCD",
                "TWDB",
                "USFS",
                "USGS",
                "USGS WRD",
            ]:
                contact_names.append(None)
                contact_organizations.append(measured_by)
                roles.append("Organization")

            # --- People ---
            # TODO: AMP feedback to ask if the roles are correct
            elif measured_by == "Wagner":
                contact_names.append("Stacy Timmons")
                contact_organizations.append(collecting_organization)
                roles.append("Hydrogeologist")
            elif measured_by in ["Anders Lundahl", "Anders Lundalh"]:
                contact_names.append("Anders Lundahl")
                contact_organizations.append(collecting_organization)
                roles.append("Specialist")
            elif measured_by == "CE":
                contact_names.append("Cathy Eisen")
                contact_organizations.append(collecting_organization)
                roles.append("Hydrogeologist")
            """
            Developer's notes

            Use existing contact for the thing if measured by is the owner
            """
            if measured_by not in ["Owner", "Owner report", "Well owner"]:
                for i, c in enumerate(contact_names):
                    if c not in CREATED_CONTACTS.keys():
                        # create new contact if not already created
                        name = contact_names[i]
                        organization = contact_organizations[i]

                        if len(roles) > 0:
                            role = roles[i]
                        else:
                            role = "sampler"

                        contact = Contact(
                            name=name,
                            role="sampler",
                            contact_type="NM_Aquifer Import",
                            organization=organization,
                            nma_pk_waterlevels=row.GlobalID,
                        )
                        session.add(contact)
                        session.flush()  # to get the contact.id

                        CREATED_CONTACTS[c] = contact

                    """
                    Developer's notes

                    Assumes that the first listed contact is the lead and the
                    person who took the sample. The subsequent contact will be
                    participants in the field event
                    """
                    if i == 0:
                        # leader
                        # sampler
                        pass
                    else:
                        # participant
                        # not sampler
                        pass
            else:
                contact = thing.contacts[0]

            # --- Sample ---

            if not pd.isna(row.MeasurementMethod):
                sample_method = lu_to_lexicon_map[
                    f"LU_MeasurementMethod:{row.MeasurementMethod}"
                ]
            else:
                sample_method = "null placeholder"

            sample = Sample(
                field_activity=field_activity,
                # sampler_name=sampler_name,
                sample_date=dt_utc,
                sample_matrix="water",
                sample_name=str(
                    uuid.uuid4()
                ),  # TODO: should this stay as-is for water levels? since there are no lab-assigned names
                sample_method=sample_method,
                qc_type="Normal",
                depth_top=None,
                depth_bottom=None,
            )
            session.add(sample)

            # TODO: update for auto-collectors in the Sensor table, like e-probes
            #       update the deployment table here
            sensor_id = None

            if not pd.isna(row.LevelStatus):
                level_status = lu_to_lexicon_map[f"LU_LevelStatus:{row.LevelStatus}"]
            else:
                level_status = None

            observation = Observation(
                sensor_id=sensor_id,
                sample=sample,
                nma_pk_waterlevels=row.GlobalID,
                value=row.DepthToWater,
                measuring_point_height=row.MPHeight,
                observed_property="groundwater level",
                unit="ft",
                level_status=level_status,
                observation_datetime=dt_utc,
            )

            session.add(observation)
        session.commit()


# ============= EOF =============================================
