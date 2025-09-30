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

# keep a dictionary of created Contacts to avoid repeated SQL queries
CREATED_CONTACTS = {}
SPACE_2 = " " * 2
SPACE_4 = " " * 4


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

            if pd.isna(row.DateMeasured):
                logger.critical(
                    f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} because there is no DateMeasured"
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

            logger.info(
                f"{SPACE_2}Created field event: ID {field_event.id} | Date {field_event.event_date} | Thing ID {field_event.thing.id} | Thing Name {field_event.thing.name}"
            )

            # --- FieldActivity ---

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
            if measured_by is None:
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

            # --- Companies/Organizations/Misc ---
            elif measured_by == "A&T Pump & Well Serv":
                ns = [None]
                os = ["A&T Pump & Well Service, LLC"]
                rs = ["Organization"]
            elif "AGW" in measured_by:
                os = ["A. G. Wassenaar, Inc"]
                if "Turner" in measured_by:
                    ns = ["Turner"]
                    rs = ["Unknown"]
                else:
                    ns = [None]
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
            elif measured_by == "Cook":
                ns = ["Cook"]
                os = ["Balleau Groundwater, Inc"]
                rs = ["Unknown"]
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
            elif measured_by == "Jerome Salazar":
                ns = ["Jerome Salazar"]
                os = ["Chevron"]
                rs = ["Unknown"]
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
            elif measured_by in ["Tribble, Cruz", "Tribble/Cruz"]:
                ns = ["Tribble", "Cruz"]
                os = [
                    "Daniel B. Stephens & Associates, Inc",
                    "Daniel B. Stephens & Associates, Inc",
                ]
                rs = ["Unknown", "Unknown"]
            elif measured_by == "Driller":
                ns = [None]
                os = [measuring_agency]
                rs = ["Driller"]
            elif measured_by == "EnecoTech":
                # TODO: verify organization name with AMP
                ns = [None]
                os = ["EnecoTech"]
                rs = ["Organization"]
            elif measured_by == "Faith Engineering":
                ns = [None]
                os = ["Faith Engineering, Inc"]
                rs = ["Organization"]
            elif measured_by in [
                "GGI",
                "GGI for OSE",
                "GGI-OSE",
                "Glorieta Geoscienc" "Glorieta Geoscience",
            ]:
                ns = [None]
                os = ["Glorieta Geoscience, Inc"]
                rs = ["Organization"]
            elif measured_by == "Hodgins, GCI":
                ns = ["Meghan Hodgins"]
                os = ["Glorieta Geoscience, Inc"]
                rs = ["Geologist"]
            elif measured_by == "Kreamer, GGI":
                ns = ["Kreamer"]
                os = ["Glorieta Geoscience, Inc"]
                rs = ["Unknown"]
            elif measured_by == "Olson, GGI":
                ns = ["Olson"]
                os = ["Glorieta Geoscience, Inc"]
                rs = ["Unknown"]
            elif measured_by == "Golder Ass. For OSE":
                ns = [None]
                os = ["Golder Associates, Inc"]
                rs = ["Organization"]
            elif measured_by == "Hathorn Well Service":
                ns = [None]
                os = ["Hathorn's Well Service"]
                rs = ["Organization"]
            elif measured_by == "Hydroscience Assoc.":
                ns = [None]
                os = ["Hydroscience Associates, Inc"]
                rs = ["Organization"]
            elif "IC Tech" in measured_by or "ICTech" in measured_by:
                ns = [None]
                os = ["IC Tech, Inc"]
                rs = ["Organization"]
            elif measured_by in [
                "John Shomaker",
                "John Shomaker & Asso",
                "John Shomaker Assoc.",
                "JS&A",
                "JSA",
                "JSAI",
                "Shomaker",
            ]:
                ns = [None]
                os = ["John Shomaker & Associates, Inc"]
                rs = ["Organization"]
            elif measured_by in [
                "Fleming",
                "Fleming - Shomaker",
                "Fleming/Shomaker",
                "Shomaker - Fleming",
                "Shomaker - Fleming",
                "Shomaker/Fleming",
            ]:
                ns = ["Fleming"]
                os = ["John Shomaker & Associates, Inc"]
                rs = ["Unknown"]
            elif measured_by in ["Kuck", "Kuckleman"]:
                ns = [None]
                os = ["Kuckleman Pump Service"]
                rs = ["Organization"]
            elif measured_by == "Lee Foster":
                ns = [None]
                os = ["Foster Well Service, Inc"]
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
            elif measured_by == "NESWCD":
                ns = [None]
                os = ["Northeastern SWCD"]
                rs = ["Organization"]
            elif measured_by in ["NMOSE?", "OSE"]:
                ns = [None]
                os = ["NMOSE"]
                rs = ["Organization"]
            elif measured_by in ["OSE; Doug Rappuhn", "D.Rappuhn OSE"]:
                # TODO: verify role with AMP
                ns = ["Doug Rappuhn"]
                os = ["NMOSE"]
                rs = ["Hydrologist"]
            elif measured_by == "OSE, ST":
                ns = [None, "Stacy Timmons"]
                os = ["NMOSE", "NMBGMR"]
                rs = ["Organization", "Hydrogeologist"]
            elif measured_by == "PVACD person":
                ns = [None]
                os = ["PVACD"]
                rs = ["Organization"]
            elif measured_by in ["Rodgers & Co", "Rodgers & Co."]:
                ns = [None]
                os = ["Rodgers & Company, Inc"]
                rs = ["Organization"]
            elif measured_by in ["Sandia National labs", "SNL"]:
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
            elif measured_by == "SPCE HOA":
                ns = [None]
                os = ["San Pedro Creek Estates HOA"]
                rs = ["Organization"]
            elif measured_by == "Statewide Drilling":
                ns = [None]
                os = ["Statewide Drilling, Inc"]
                rs = ["Organization"]
            elif measured_by == "Tec Drilling":
                ns = [None]
                os = ["Tec Drilling Limited"]
                rs = ["Organization"]
            elif measured_by == "TetraTech":
                ns = [None]
                os = ["Tetra Tech, Inc"]
                rs = ["Organization"]
            elif measured_by == "Thompson Drilling":
                ns = [None]
                os = ["Thompson Drilling, Inc"]
                rs = ["Organization"]
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
            elif measured_by == "USGA":
                ns = [None]
                os = ["USGS"]
                rs = ["Organization"]
            elif measured_by == "USGS/NESWCD":
                ns = [None, None]
                os = ["USGS", "Northeastern SWCD"]
                rs = ["Organization", "Organization"]
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
            elif measured_by in ["CE", "ce"]:
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
            elif measured_by == "EM":
                ns = ["Ethan Mamer"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "EM, AL":
                ns = ["Ethan Mamer", "Angela Lucero"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrologist"]
            elif measured_by in ["EM, CM", "EM,CM"]:
                ns = ["Ethan Mamer", "Cris Morton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "EM, JB":
                ns = ["Ethan Mamer", "Joseph Beman"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Technician"]
            elif measured_by == "EM, KP":
                # TODO: verify Kitty's role with AMP
                ns = ["Ethan Mamer", "Kitty Pokorny"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "EM, LS":
                ns = ["Ethan Mamer", "Laila Sturgis"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "EM, MF":
                ns = ["Ethan Mamer", "Marissa Fichera"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "EM, SMC":
                ns = ["Ethan Mamer", "Sara Chudnoff"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "EM, TK":
                ns = ["Ethan Mamer", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "EM, TN":
                ns = ["Ethan Mamer", "Talon Newton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "Gary Goss":
                ns = [measured_by]
                os = [measuring_agency]
                rs = ["Operator"]
            elif measured_by == "GCR":
                ns = ["Geoff Rawling"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by in ["GCR/ST", "GCRST", "GR/ST", "Rawling/Wagner"]:
                ns = ["Geoff Rawling", "Stacy Timmons"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "GCR/ST/JM":
                # TODO: verify Joe's role with AMP
                ns = ["Geoff Rawling", "Stacy Timmons", "Joe Marcoline"]
                os = ["NMBGMR", "NMBGMR", "NMED"]
                rs = ["Hydrogeologist", "Hydrogeologist", "Unknown"]
            elif measured_by == "GR":
                ns = ["Geoff Rawling"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "GR, AL":
                ns = ["Geoff Rawling", "Angela Lucero"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrologist"]
            elif measured_by == "GR, CE":
                ns = ["Geoff Rawling", "Cathy Eisen"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "GR, SC":
                ns = ["Geoff Rawling", "Scott Christenson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Technician"]
            elif measured_by in ["GR, TK", "GR/TK"]:
                ns = ["Geoff Rawling", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "GR/LL":
                ns = ["Geoff Rawling", "Lewis Land"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["JB", "JEB"]:
                ns = ["Joseph Beman"]
                os = ["NMBGMR"]
                rs = ["Technician"]
            elif measured_by == "Jim Corbin":
                ns = ["Jim Corbin"]
                os = ["Corbin Consulting, Inc"]
                rs = ["Unknown"]
            elif measured_by in ["JM", "Joe Marcoline"]:
                ns = ["Joe Marcoline"]
                os = ["NMED"]
                rs = ["Unknown"]
            elif measured_by == "Johnson":
                ns = ["Peggy Johnson"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by in ["Johnson - Kuck", "Johnson-Kuck", "Johnson/Kuck"]:
                # TODO: get Kuckleman's first name, role, organization from AMP
                ns = ["Peggy Johnson", "Kuckleman"]
                os = ["NMBGMR", "Unknown"]
                rs = ["Hydrogeologist", "Unknown"]
            elif measured_by in ["Johnson-Lyman", "Johnson/Lyman", "PJ/Lyman"]:
                ns = ["Peggy Johnson", "John Lyman"]
                os = ["NMBGMR", "Unknown"]
                rs = ["Hydrogeologist", "Unknown"]
            elif measured_by == "Jose Varela Lopez":
                ns = ["Jose Varela Lopez"]
                os = ["Puerta del Canon Ranch"]
                rs = ["Operator"]
            elif measured_by == "K. McLain":
                ns = ["Katie McLain"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "K. McLain, M. Hein":
                ns = ["Katie McLain", "Marina Hein"]
                os = ["NMBGMR", "NMT"]
                rs = ["Hydrogeologist", "Biologist"]
            elif measured_by in ["K.Summers", "WK Summers"]:
                ns = ["Kelly Summers"]
                os = ["NMBGMR"]
                rs = ["Hydrologist"]
            elif measured_by == "Kelsey McNamara":
                ns = [measured_by]
                os = ["NMBGMR"]
                rs = ["Geologist"]
            elif measured_by in ["Kitty", "Kitty Pokorny", "KP"]:
                ns = ["Kitty Pokorny"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == ["KP, MF"]:
                ns = ["Kitty Pokorny", "Marissa Fichera"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "KP, ST":
                ns = ["Kitty Pokorny", "Stacy Timmons"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "KP, TK":
                ns = ["Kitty Pokorny", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["KR", "Kylian Robinson"]:
                ns = ["Kylian Robinson"]
                os = ["NMED"]
                rs = ["Hydrogeologist"]
            elif measured_by == "Leroy Romero":
                ns = ["Leroy Romero"]
                os = ["Los Golondrinas"]
                rs = ["Unknown"]
            elif measured_by == "LL, TN":
                ns = ["Lewis Land", "Talon Newton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "LS":
                ns = ["Laila Sturgis"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "LS, TK":
                ns = ["Laila Sturgis", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "Lyman":
                ns = ["John Lyman"]
                os = ["Unknown"]
                rs = ["Unknown"]
            elif measured_by == "M. Hein":
                ns = ["Marina Hein"]
                os = ["NMT"]
                rs = ["Biologist"]
            elif measured_by == "MH, KM":
                ns = ["Marina Hein", "Katie McLain"]
                os = ["NMT", "NMBGMR"]
                rs = ["Biologist", "Hydrogeologist"]
            elif measured_by == "Patricia Rosacker":
                ns = ["Patricia Rosacker"]
                os = ["CSF"]
                rs = ["Lab Manager"]
            elif measured_by == "PB, PJ":
                ns = ["Paul Bauer", "Peggy Johnson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Geologist", "Hydrogeologist"]
            elif measured_by == "PB, PJ, TK":
                ns = ["Paul Bauer", "Peggy Johnson", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Geologist", "Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "Pepin":
                ns = ["Jeff Pepin"]
                os = ["USGS"]
                rs = ["Hydrologist"]
            elif measured_by == "Pepin/Kelley":
                ns = ["Jeff Pepin", "Shari Kelley"]
                os = ["USGS", "NMBGMR"]
                rs = ["Hydrologist", "Geologist"]
            elif measured_by == "Mark Person":
                ns = [measured_by]
                os = ["NMT"]
                rs = ["Geologist"]
            elif measured_by == "PJ":
                ns = ["Peggy Johnson"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by in ["PJ PB", "PJ, PB"]:
                ns = ["Peggy Johnson", "Paul Bauer"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Geologist"]
            elif measured_by in ["PJ TK PB", "PJ, TK, PB"]:
                ns = ["Peggy Johnson", "Trevor Kludt", "Paul Bauer"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist", "Geologist"]
            elif measured_by == "RL Borton":
                ns = ["R. L. Borton"]
                os = ["NMOSE"]
                rs = ["Unknown"]
            elif measured_by == "RP":
                ns = ["RP"]
                os = ["NMOSE"]
                rs = ["Unknown"]
            elif measured_by in ["Sara Chudnoff", "SMC"]:
                ns = ["Sara Chudnoff"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "SMC, EM":
                ns = ["Sara Chudnoff", "Ethan Mamer"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "SMC, SC":
                ns = ["Sara Chudnoff", "Scott Christenson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Technician"]
            elif measured_by == "SMC, TK":
                ns = ["Sara Chudnoff", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["SC", "SCC", "SD"]:
                ns = ["Scott Christenson"]
                os = ["NMBGMR"]
                rs = ["Technician"]
            elif measured_by == "SC, AL":
                ns = ["Scott Christenson", "Angela Lucero"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrologist"]
            elif measured_by == "SC, CM":
                ns = ["Scott Christenson", "Cris Morton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, DL":
                ns = ["Scott Christenson", "Dan Lavery"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, EM":
                ns = ["Scott Christenson", "Ethan Mamer"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, GR":
                ns = ["Scott Christenson", "Geoff Rawling"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, KP":
                ns = ["Scott Christenson", "Kitty Pokorny"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, SMC":
                ns = ["Scott Christenson", "Sara Chudnoff"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, ST":
                ns = ["Scott Christenson", "Stacy Timmons"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, TK":
                ns = ["Scott Christenson", "Trevor Kludt"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SC, TN":
                ns = ["Scott Christenson", "Talon Newton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Technician", "Hydrogeologist"]
            elif measured_by == "SK":
                ns = ["Shari Kelley"]
                os = ["NMBGMR"]
                rs = ["Geologist"]
            elif measured_by == "SK, SC, GR":
                ns = ["Shari Kelley", "Scott Christenson", "Geoff Rawling"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Geologist", "Technician", "Geologist"]
            elif measured_by == "SR":
                ns = ["Stephanie Roussel"]
                os = ["USGS"]
                rs = ["Hydrologist"]
            elif measured_by == "SR, EM":
                ns = ["Stephanie Roussel", "Ethan Mamer"]
                os = ["USGS", "NMBGMR"]
                rs = ["Hydrologist", "Hydrogeologist"]
            elif measured_by in [" Wagner", "ST", "Stacy Timmons", "Timmons", "Wagner"]:
                ns = ["Stacy Timmons"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "ST, CE":
                ns = ["Stacy Timmons", "Cathy Eisen"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["ST, Joe Marcoline", "ST/JM"]:
                ns = ["Stacy Timmons", "Joe Marcoline"]
                os = ["NMBGMR", "NMED"]
                rs = ["Hydrogeologist", "Unknown"]
            elif measured_by == "ST, KP":
                ns = ["Stacy Timmons", "Kitty Pokorny"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "ST, SK":
                ns = ["Stacy Timmons", "Shari Kelley"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Geologist"]
            elif measured_by == "ST, SK, Person":
                ns = ["Stacy Timmons", "Shari Kelley", "Mark Person"]
                os = ["NMBGMR", "NMBGMR", "NMT"]
                rs = ["Hydrogeologist", "Geologist", "Geologist"]
            elif measured_by == "ST, SMC":
                ns = ["Stacy Timmons", "Sara Chudnoff"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["ST/BF", "ST/BFK"]:
                ns = ["Stacy Timmons", "Brigitte Felix"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Publications Manager"]
            elif measured_by == "ST/BTN":
                ns = ["Stacy Timmons", "Talon Newton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["ST/GCR", "ST/GR", "Wagner/Rawling"]:
                ns = ["Stacy Timmons", "Geoff Rawling"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "ST/JW":
                ns = ["Stacy Timmons", "Jim Witcher"]
                os = ["NMBGMR", "Witcher & Associates"]
                rs = ["Hydrogeologist", "Geologist"]
            elif measured_by == "ST/LL":
                ns = ["Stacy Timmons", "Lewis Land"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["TK", "Trevor Kludt"]:
                ns = ["Trevor Kludt"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by in ["TK BF", "TK, BF", "TK/BF"]:
                ns = ["Trevor Kludt", "Brigitte Felix"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Publications Manager"]
            elif measured_by in ["tk cm", "TK, CM"]:
                ns = ["Trevor Kludt", "Cris Morton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["TK KR", "TK, KR"]:
                ns = ["Trevor Kludt", "Kylian Robinson"]
                os = ["NMBGMR", "NMED"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "TK, AL":
                ns = ["Trevor Kludt", "Angela Lucero"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrologist"]
            elif measured_by in ["TK, CE", "TK,CE"]:
                ns = ["Trevor Kludt", "Cathy Eisen"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "TK, EM":
                ns = ["Trevor Kludt", "Ethan Mamer"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["TK, GR", "TK, GCR", "TK/GR", "TK/RG"]:
                ns = ["Trevor Kludt", "Geoff Rawling"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "TK, KrPe":
                ns = ["Trevor Kludt", "Kirsten Pearthree"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Research Scientist"]
            elif measured_by == "TK, PB, PJ":
                ns = ["Trevor Kludt", "Paul Bauer", "Peggy Johnson"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Geologist", "Hydrogeologist"]
            elif measured_by == "TK, SC":
                ns = ["Trevor Kludt", "Scott Christenson"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Technician"]
            elif measured_by in ["TK, ST, CE", "TK, ST; CE"]:
                ns = ["Trevor Kludt", "Stacy Timmons", "Cathy Eisen"]
                os = ["NMBGMR", "NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "TK, TN":
                ns = ["Trevor Kludt", "Talon Newton"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by == "TN":
                ns = ["Talon Newton"]
                os = ["NMBGMR"]
                rs = ["Hydrogeologist"]
            elif measured_by == "TN, LL":
                ns = ["Talon Newton", "Lewis Land"]
                os = ["NMBGMR", "NMBGMR"]
                rs = ["Hydrogeologist", "Hydrogeologist"]
            elif measured_by in ["Wasiolek", "Wasiolek rpt 1983"]:
                ns = ["Maryann Wasiolek"]
                os = ["Hydroscience Associates, Inc"]
                rs = ["Hydrogeologist"]

            else:
                logger.critical(
                    f"Skipping the following record because it has no mappings: {row.MeasuredBy} // {row.MeasuringAgency} for PointID {row.PointID}"
                )
                continue
            """
            Developer's notes

            Use existing contact for the thing if measured by is the owner
            """
            field_event_contacts = []
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

                        CREATED_CONTACTS[c] = contact
                    else:
                        contact = CREATED_CONTACTS[c]
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
                if i == 0:
                    field_event_contact = FieldEventContactAssociation(
                        field_event=field_event,
                        contact=fec,
                        field_contact_role="Lead",
                    )
                    sampler = field_event_contact
                else:
                    field_event_contact = FieldEventContactAssociation(
                        field_event=field_event,
                        contact=fec,
                        field_contact_role="Participant",
                    )
                session.add(field_event_contact)
                session.flush()
                logger.info(
                    f"{SPACE_4}Created field event contact: ID {field_event_contact.id} | Contact Name {field_event_contact.contact.name} | Field Contact Role {field_event_contact.field_contact_role}"
                )

            if pd.isna(row.DepthToWater):
                logger.warning(
                    f"{SPACE_4}No sample and observation have been made for WaterLevels record with GlobalID {row.GlobalID} because DepthToWater is NULL"
                )
                continue
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
                sample_name=str(
                    uuid.uuid4()
                ),  # TODO: should this stay as-is for water levels? since there are no lab-assigned names
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
