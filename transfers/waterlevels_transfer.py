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
    filter_by_valid_measuring_agency,
    lu_to_lexicon_map,
)

# keep a dictionary of created Contacts to avoid repeated SQL queries
CREATED_CONTACTS = {}


def transfer_water_levels(session):

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

            if pd.isna(row.DepthToWater) or pd.isna(row.DateMeasured):
                logger.critical(
                    f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to "
                    f"missing "
                    f"data."
                )
                continue

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
                dt_utc = convert_mt_to_utc(dt)
            except ValueError as e:
                logger.warning(
                    f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to "
                    f"invalid date/time: {e}"
                )
                continue

            release_status = "public" if row.PublicRelease else "private"

            """
            Developer's notes

            Assumes for manual water levels that the date/time of the water level
            measurement is the same as the date/time of the field event.
            """

            # --- FieldEvent ---

            field_event = FieldEvent(
                thing=thing,
                event_date=dt_utc,
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

            if pd.isna(row.MeasuringAgency):
                measuring_agency = "Unknown"
            else:
                measuring_agency = row.MeasuringAgency

            # sometimes multiple contacts need to be created, so they'll be stored in a list
            # the nth name corresponds with the nth organization
            contact_names = []
            contact_organizations = []
            roles = []

            # ns --> names
            # os --> organizations
            # rs --> roles

            # TODO: get help figuring out (AMP)
            if measured_by in [
                "Anthony Chavez",
                "BEI",
                "BF/RG",
                "Borchert",
                "Borton & Cooper",
                "CDWR",
                "Chaves/Cruz",
                "Chavez/Cruz",
                "CM, AK" "Cook",
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
            ]:
                logger.critical(
                    f"Skipping water level for PointID {row.PointID} because contact could not be determined for {measured_by}"
                )
                # TODO: if any of these people are not knowable after AMP review put them into db
                #   as Unknown/Unknown. These can be audited in the future with nma_pk_waterlevels
                continue

            # --- Companies/Organizations/Misc ---
            if measured_by == "A&T Pump & Well Serv":
                ns = [None]
                os = ["A&T Pump & Well Service, LLC"]
                rs = ["Organization"]
            elif "AGW" in measured_by:
                if "Turner" in measured_by:
                    ns = ["Turner"]
                else:
                    ns = [None]
                os = ["A. G. Wassenaar, Inc"]
                rs = ["Organization"]
            elif measured_by == "AMEC":
                ns = [None]
                os = ["AMEC Earth & Environmental"]
                rs = ["Organization"]
            elif measured_by == "ARCADIS":
                ns = [None]
                os = ["Arcadis"]
                rs = ["Organization"]
            elif "Balleau" in measured_by:
                ns = [None]
                os = ["Balleau Groundwater, Inc"]
                rs = ["Organization"]
            elif measured_by == "Bureau":
                ns = [None]
                os = ["NMBGMR"]
                rs = ["Organization"]
            elif measured_by == "CDM":
                ns = [None]
                os = ["CDM Smith"]
                rs = ["Organization"]
            elif measured_by == "CH2MHill":
                ns = [None]
                os = ["CH2M Hill"]
                rs = ["Organization"]
            elif measured_by == "Chevron personnel":
                ns = [None]
                os = ["Chevron"]
                rs = ["Organization"]
            elif measured_by in [
                "City of  Santa Fe",
                "City of Santa  Fe",
                "City of Santa Fe",
                "CityofSantaFe",
            ]:
                ns = [None]
                os = ["CSF"]
                rs = ["Organization"]
            elif measured_by in ["DBSA", "DBStephens & Assoc"]:
                ns = [None]
                os = ["Daniel B. Stephens & Associates, Inc"]
                rs = ["Organization"]
            elif measured_by == "Calvert":
                ns = ["Calvert"]
                os = ["Daniel B. Stephens & Associates, Inc"]
                # TODO: see if AMP knows this person's name and role
                rs = ["Unknown"]
            elif measured_by == "Driller":
                ns = [None]
                os = [measuring_agency]
                rs = ["Driller"]
            elif "Glorieta Geoscienc" in measured_by:
                ns = [None]
                os = ["Glorieta Geoscience, Inc"]
                rs = ["Organization"]
            elif measured_by == "Golder Ass. For OSE":
                ns = [None]
                os = ["Golder Associates, Inc"]
                rs = ["Organization"]
            elif measured_by == "Hydroscience Assoc.":
                ns = [None]
                os = ["Hydroscience Associates, Inc"]
                rs = ["Organization"]
            elif "IC Tech" in measured_by or "ICTech" in measured_by:
                ns = [None]
                os = ["IC Tech, Inc"]
                rs = ["Organization"]
            elif "John Shomaker" in measured_by:
                ns = [None]
                os = ["John Shomaker & Associates, Inc"]
                rs = ["Organization"]
            elif measured_by == "Mario Gonzales NMRWA":
                # TODO: does AMP know this person's role at NMRWA?
                ns = ["Mario Gonzalez"]
                os = ["NMRWA"]
                rs = ["Unknown"]
            elif "Minton" in measured_by:
                ns = [None]
                os = ["Minton Engineers"]
                rs = ["Organization"]
            elif "MJ Darr" in measured_by:
                ns = [None]
                rs = ["MJDarrconsult, Inc"]
                os = [measuring_agency]
            elif measured_by in ["NMOSE?", "OSE"]:
                ns = [None]
                os = ["NMOSE"]
                rs = ["Organization"]
            elif measured_by in ["OSE; Doug Rappuhn", "D.Rappuhn OSE"]:
                # TODO: verify role with AMP
                ns = ["Doug Rappuhn"]
                os = ["NMOSE"]
                rs = ["Hydrologist"]
            elif measured_by == "PVACD person":
                ns = [None]
                os = ["PVACD"]
                rs = ["Organization"]
            elif measured_by in ["Rodgers & Co", "Rodgers & Co."]:
                ns = [None]
                os = ["Rodgers & Company, Inc"]
                rs = ["Organization"]
            elif measured_by == "Sandia National labs":
                ns = [None]
                os = ["SNL"]
                rs = ["Organization"]
            elif measured_by in ["Santa Fe County", "SFCounty LF staff"]:
                ns = [None]
                os = ["SFC"]
                rs = ["Organization"]
            elif measured_by == "SFC/Frost":
                ns = ["Frost"]
                os = ["SFC"]
                rs = ["Unknown"]
            elif measured_by == "Statewide Drilling":
                ns = [None]
                os = ["Statewide Drilling, Inc"]
                rs = ["Organization"]
            elif measured_by in [
                "?",
                "Consultant",
                "Consulting Pro.",
                "Pump company",
                "PumpService",
                "REPORTED",
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
            elif measured_by in [
                "Arcadis",
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
                # organizations whose names do not need to be changed
                ns = [None]
                os = [measured_by]
                rs = ["Organization"]

            # --- People ---
            elif measured_by == " Wagner":
                ns = ["Stacy Timmons"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "AL":
                ns = ["Angela Lucero"]
                os = ["NMBGMR"]
                rs = ["Hydrologist"]
            elif measured_by == "AL, GR":
                ns = ["Angela Lucero", "Geoff Rawling"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrologist", "Hydrogeologist"]
            elif measured_by == "AL, SC":
                ns = ["Angela Lucero", "Scott Christenson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrologist", "Technician"]
            elif measured_by == "Amy Kronson":
                ns = ["Amy Kronson"]
                os = ["NMBGMR"]
                rs = ["Technician"]
            elif measured_by in ["Anders Lundahl", "Anders Lundalh"]:
                ns = ["Anders Lundahl"]
                os = [measuring_agency]
                rs = ["Specialist"]
            elif measured_by == "Andrew Matejunas":
                ns = [measured_by]
                os = ["NMBGMR"]
                rs = ["Research Assistant"]
            elif measured_by == "Andy Manning":
                ns = [measured_by]
                os = ["USGS"]
                rs = ["Hydrogeologist"]
            elif measured_by in ["Bob Borton", "Borton"]:
                ns = ["Bob Borton"]
                os = ["NMBGMR"]
                rs = ["Geologist"]
            elif measured_by == "CE":
                ns = ["Cathy Eisen"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "CE PJ":
                ns = ["Cathy Eisen", "Peggy Johnson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["CE TK", "CE, TK"]:
                ns = ["Cathy Eisen", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "CE, GR":
                ns = ["Cathy Eisen", "Geoff Rawling"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "CM":
                ns = ["Cris Morton"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "CM, EM":
                ns = ["Cris Morton", "Ethan Mamer"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "CM, LS, KP":
                # TODO: verify Kitty's role with AMP
                ns = ["Cris Morton", "Laila Sturgis", "Kitty Pokorny"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "CM, LS, KrPe":
                ns = ["Cris Morton", "Laila Sturgis", "Kirsten Pearthree"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist", "Research Scientist"]
            elif measured_by == "CM, SC":
                ns = ["Cris Morton", "Scott Christenson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Technician"]
            elif measured_by == "CM, TK":
                ns = ["Cris Morton", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "Dan McGregor":
                ns = [measured_by]
                os = ["Bernalillo County"]
                rs = ["Hydrogeologist"]
            elif measured_by in ["Dennis Cooper", "Dennis R. Cooper"]:
                ns = ["Dennis Cooper"]
                os = ["NMOSE"]
                rs = ["Engineer"]

            else:
                logger.warning(
                    f"The following record has not been mapped to a Contact: {row.MeasuredBy} // {row.MeasuringAgency} for PointID {row.PointID}"
                )
            """
            Developer's notes

            Use existing contact for the thing if measured by is the owner
            """
            if measured_by not in ["Owner", "Owner report", "Well owner"]:
                contact_names.extend(ns)
                contact_organizations.extend(os)
                roles.extend(rs)
                for i, c in enumerate(contact_names):
                    if c not in CREATED_CONTACTS.keys():
                        # create new contact if not already created
                        name = contact_names[i]
                        organization = contact_organizations[i]
                        role = roles[i]

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

            # todo: use create schema to validate data
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

            # TODO: use create schema to validate data
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
