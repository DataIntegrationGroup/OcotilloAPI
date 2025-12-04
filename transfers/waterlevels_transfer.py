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
import json
from typing import Optional
import uuid
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from db import (
    Thing,
    Sample,
    Observation,
    FieldEvent,
    FieldActivity,
    Contact,
    FieldEventParticipant,
    Parameter,
)
from db.engine import session_ctx
from transfers.transferer import Transferer
from transfers.util import (
    filter_to_valid_point_ids,
    logger,
    read_csv,
    convert_mt_to_utc,
    filter_by_valid_measuring_agency,
    lexicon_mapper,
    get_transfers_data_path,
)

# constants
SPACE_2 = " " * 2
SPACE_4 = " " * 4
SPACE_6 = " " * 6


def get_contacts_info(
    row, measured_by, measured_by_mapper
) -> list[tuple[str, str, str]]:
    # TODO: get help figuring out (AMP)
    if measured_by in measured_by_mapper:
        args = measured_by_mapper[measured_by]
        if isinstance(args[0], list):
            names, orgs, roles = zip(*args)
        else:
            names, orgs, roles = [args[0]], [args[1]], [args[2]]

    else:
        names = [measured_by]
        orgs = ["Unknown"]
        roles = ["Unknown"]
        logger.warning(
            f"{SPACE_6}The following record has not been mapped to a Contact: MeasuredBy {row.MeasuredBy} | MeasuringAgency {row.MeasuringAgency} for WaterLevels record with GLobalID {row.GlobalID}"
        )

    return zip(names, orgs, roles)


class WaterLevelTransferer(Transferer):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.source_table = "WaterLevels"
        with session_ctx() as session:
            groundwater_parameter_id = (
                session.query(Parameter)
                .filter(Parameter.parameter_name == "groundwater level")
                .one()
                .id
            )
            self.groundwater_parameter_id = groundwater_parameter_id

        path = get_transfers_data_path("measured_by_mapper.json")
        with open(path, "r") as f:
            self._measured_by_mapper = json.load(f)

        self._created_contacts = {}

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table)
        cleaned_df = filter_to_valid_point_ids(input_df)
        cleaned_df = filter_by_valid_measuring_agency(cleaned_df)
        return input_df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        gwd = self.cleaned_df.groupby(["PointID"])
        for index, group in gwd:
            pointid = index[0]
            thing = session.query(Thing).where(Thing.name == pointid).first()

            for i, row in enumerate(group.itertuples()):
                dt_utc = self._get_dt_utc(row)
                if dt_utc is None:
                    continue

                release_status = "public" if row.PublicRelease else "private"

                # field event
                field_event = FieldEvent(
                    thing=thing,
                    event_date=dt_utc,
                    release_status=release_status,
                )
                session.add(field_event)
                field_event_participants = self._get_field_event_participants(
                    session, row, thing
                )
                sampler = None
                for i, participant in enumerate(field_event_participants):
                    field_event_participant = FieldEventParticipant(
                        field_event=field_event, participant=participant
                    )
                    if i == 0:
                        field_event_participant.participant_role = "Lead"
                        sampler = field_event_participant
                    else:
                        field_event_participant.participant_role = "Participant"

                    session.add(field_event_participant)

                # reasons
                glv = self._get_groundwater_level_reason(row)
                if (
                    glv
                    == "Well was destroyed (no subsequent water levels should be recorded)"
                ):
                    logger.warning(
                        "Well is destroyed - no field activity/sample/observation will be made"
                    )
                    field_event.notes = glv
                    continue

                # Field Activity
                # TODO: use create schema to validate data
                field_activity = FieldActivity(
                    field_event=field_event,
                    activity_type="groundwater level",
                    release_status=release_status,
                )
                session.add(field_activity)

                # Sample
                sample = self._make_sample(row, field_activity, dt_utc, sampler)
                session.add(sample)

                # Observation
                observation = self._make_observation(row, sample, dt_utc, glv)
                session.add(observation)

            session.commit()

    def _make_observation(
        self, row: pd.Series, sample: Sample, dt_utc: datetime, glv: str
    ) -> Observation:
        if pd.isna(row.MPHeight):
            if pd.notna(row.DepthToWater) and pd.notna(row.DepthToWaterBGS):
                logger.warning(
                    f"{SPACE_6}Calculating measuring_point_height as DepthToWater - DepthToWaterBGS because MPHeight is NULL"
                )
                measuring_point_height = row.DepthToWater - row.DepthToWaterBGS
            else:
                logger.warning(
                    f"{SPACE_6}Setting measuring_point_height to None because MPHeight is NULL and DepthToWater or DepthToWaterBGS is NULL"
                )
                measuring_point_height = None
        else:
            # some mp heights are recorded as negative numbers, but they should be positive
            measuring_point_height = abs(row.MPHeight)

        if pd.isna(row.DepthToWater):
            if pd.notna(row.DepthToWaterBGS):
                logger.warning(
                    f"{SPACE_6}Calculating observation value as DepthToWaterBGS + MPHeight (0 if MPHeight is NULL) because DepthToWater is NULL"
                )
                value = row.DepthToWaterBGS + measuring_point_height
            else:
                # use None not NaN
                value = None
        else:
            value = row.DepthToWater

            # TODO: after sensors have been added to the database update sensor_id (or sensor) for waterlevels that come from db sensors (like e probes?)
        observation = Observation(
            nma_pk_waterlevels=row.GlobalID,
            sample=sample,
            sensor_id=None,
            analysis_method_id=None,
            observation_datetime=dt_utc,
            parameter_id=self.groundwater_parameter_id,
            value=value,
            unit="ft",
            measuring_point_height=measuring_point_height,
            groundwater_level_reason=glv,
        )
        return observation

    def _make_sample(self, row, field_activity, dt_utc, sampler) -> Sample:
        sample_method = (
            "null placeholder"
            if pd.isna(row.MeasurementMethod)
            else lexicon_mapper.map_value(
                f"LU_MeasurementMethod:{row.MeasurementMethod}"
            )
        )
        sample = Sample(
            nma_pk_waterlevels=row.GlobalID,
            field_activity=field_activity,
            field_event_participant=sampler,
            sample_date=dt_utc,
            sample_matrix="water",
            sample_name=str(uuid.uuid4()),
            sample_method=sample_method,
            qc_type="Normal",
            depth_top=None,
            depth_bottom=None,
        )
        return sample

    def _get_groundwater_level_reason(self, row) -> Optional[str]:
        glv = row.LevelStatus
        if pd.isna(glv):
            return None

        lookup_key = f"LU_LevelStatus:{glv}"
        mapped = lexicon_mapper.map_value(lookup_key)

        # If the mapper returns the raw key, it means "not mapped"
        if mapped == lookup_key:
            logger.warning(f"Unknown LevelStatus '{glv}', mapping to None")
            return None

        if mapped == "Water level not affected by status":
            mapped = "Water level not affected"

        return mapped

    def _get_field_event_participants(self, session, row, thing) -> list[Contact]:
        field_event_participants = []
        measured_by = None if pd.isna(row.MeasuredBy) else row.MeasuredBy

        if measured_by not in ["Owner", "Owner report", "Well owner"]:
            # --- Contact/FieldEventParticipant ---
            contact_info = get_contacts_info(row, measured_by, self._measured_by_mapper)

            for name, organization, role in contact_info:
                if (name, organization) in self._created_contacts:
                    contact = self._created_contacts[(name, organization)]
                else:
                    try:
                        # create new contact if not already created
                        contact = Contact(
                            name=name,
                            role=role,
                            contact_type="Field Event Participant",
                            organization=organization,
                            nma_pk_waterlevels=row.GlobalID,
                        )
                        session.add(contact)

                        logger.info(
                            f"{SPACE_2}Created contact: | Name {contact.name} | Role {contact.role} | Organization {contact.organization} | nma_pk_waterlevels {contact.nma_pk_waterlevels}"
                        )

                        self._created_contacts[(name, organization)] = contact
                    except Exception as e:
                        logger.critical(
                            f"Contact cannot be created: Name {name} | Role {role} | Organization {organization} because of the following: {str(e)}"
                        )
                        continue

                field_event_participants.append(contact)
        else:
            contact = thing.contacts[0]
            field_event_participants.append(contact)

        if len(field_event_participants) == 0:
            logger.critical(
                f"No contacts can be associated with the WaterLevels record with GlobalID {row.GlobalID}, therefore no field event, field activity, sample, and observation can be made. Skipping."
            )

        return field_event_participants

    def _get_dt_utc(self, row) -> datetime | None:
        if pd.isna(row.DateMeasured):
            logger.critical(
                f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} because there is no DateMeasured"
            )
            self._capture_error(row.PointID, "no DateMeasured", "DateMeasured")
            return None

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
            self._capture_error(row.PointID, str(e), "DateMeasured")
            logger.critical(
                f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to "
                f"invalid date/time: {e}"
            )
            return None


# ============= EOF =============================================
