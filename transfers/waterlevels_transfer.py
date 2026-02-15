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
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import pandas as pd
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
from sqlalchemy.exc import DatabaseError, SQLAlchemyError
from sqlalchemy.orm import Session
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
    source_table = "WaterLevels"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
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
        input_df = read_csv(self.source_table, dtype={"MeasuredBy": str})
        cleaned_df = filter_to_valid_point_ids(input_df)
        cleaned_df = filter_by_valid_measuring_agency(cleaned_df)
        logger.info(
            "Prepared %s rows for %s after filtering (%s -> %s)",
            len(cleaned_df),
            self.source_table,
            len(input_df),
            len(cleaned_df),
        )
        return input_df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        stats: dict[str, int] = {
            "groups_total": 0,
            "groups_processed": 0,
            "groups_skipped_missing_thing": 0,
            "groups_failed_commit": 0,
            "rows_total": 0,
            "rows_created": 0,
            "rows_skipped_dt": 0,
            "rows_skipped_reason": 0,
            "rows_skipped_contacts": 0,
            "rows_well_destroyed": 0,
            "field_events_created": 0,
            "field_activities_created": 0,
            "samples_created": 0,
            "observations_created": 0,
            "contacts_created": 0,
            "contacts_reused": 0,
        }

        gwd = self.cleaned_df.groupby(["PointID"])
        total_groups = len(gwd)
        for gi, (index, group) in enumerate(gwd, start=1):
            stats["groups_total"] += 1
            pointid = index[0]
            logger.info(
                "Processing WaterLevels group %s/%s for PointID=%s (%s rows)",
                gi,
                total_groups,
                pointid,
                len(group),
            )

            thing = session.query(Thing).where(Thing.name == pointid).one_or_none()
            if thing is None:
                stats["groups_skipped_missing_thing"] += 1
                logger.warning(
                    "Skipping PointID=%s because Thing was not found", pointid
                )
                self._capture_error(pointid, "Thing not found", "PointID")
                continue

            for i, row in enumerate(group.itertuples()):
                stats["rows_total"] += 1
                dt_utc = self._get_dt_utc(row)
                if dt_utc is None:
                    stats["rows_skipped_dt"] += 1
                    continue

                # reasons
                try:
                    glv = self._get_groundwater_level_reason(row)
                except (KeyError, ValueError) as e:
                    stats["rows_skipped_reason"] += 1
                    logger.warning(
                        "Skipping %s due to invalid groundwater level reason: %s",
                        self._row_context(row),
                        e,
                    )
                    self._capture_error(
                        row.PointID,
                        f"invalid groundwater level reason: {e}",
                        "LevelStatus",
                    )
                    continue

                release_status = "public" if row.PublicRelease else "private"

                # field event
                field_event = FieldEvent(
                    thing=thing,
                    event_date=dt_utc,
                    release_status=release_status,
                )
                session.add(field_event)
                stats["field_events_created"] += 1
                field_event_participants = self._get_field_event_participants(
                    session, row, thing
                )
                stats["contacts_created"] += getattr(
                    self, "_last_contacts_created_count", 0
                )
                stats["contacts_reused"] += getattr(
                    self, "_last_contacts_reused_count", 0
                )

                if not field_event_participants:
                    stats["rows_skipped_contacts"] += 1
                    logger.warning(
                        "Skipping %s because no field event participants were found",
                        self._row_context(row),
                    )
                    continue

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

                if (
                    glv
                    == "Well was destroyed (no subsequent water levels should be recorded)"
                ):
                    logger.warning(
                        "Well is destroyed for %s - no field activity/sample/observation will be made",
                        self._row_context(row),
                    )
                    stats["rows_well_destroyed"] += 1
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
                stats["field_activities_created"] += 1

                # Sample
                sample = self._make_sample(row, field_activity, dt_utc, sampler)
                session.add(sample)
                stats["samples_created"] += 1

                # Observation
                observation = self._make_observation(row, sample, dt_utc, glv)
                session.add(observation)
                stats["observations_created"] += 1
                stats["rows_created"] += 1

            try:
                session.commit()
                session.expunge_all()
                stats["groups_processed"] += 1
            except DatabaseError as e:
                stats["groups_failed_commit"] += 1
                logger.exception(
                    "Failed committing WaterLevels group for PointID=%s: %s",
                    pointid,
                    e,
                )
                session.rollback()
                self._capture_database_error(pointid, e)
            except SQLAlchemyError as e:
                stats["groups_failed_commit"] += 1
                logger.exception(
                    "SQLAlchemy failure committing WaterLevels group for PointID=%s: %s",
                    pointid,
                    e,
                )
                session.rollback()
                self._capture_error(pointid, str(e), "UnknownField")
            except Exception as e:
                stats["groups_failed_commit"] += 1
                logger.exception(
                    "Unexpected failure committing WaterLevels group for PointID=%s: %s",
                    pointid,
                    e,
                )
                session.rollback()
                self._capture_error(pointid, str(e), "UnknownField")

        self._log_transfer_summary(stats)

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

        data_quality = None
        dq_raw = getattr(row, "DataQuality", None)
        if dq_raw and pd.notna(dq_raw):
            dq_code = str(dq_raw).strip()
            try:
                data_quality = lexicon_mapper.map_value(f"LU_DataQuality:{dq_code}")
            except KeyError:
                logger.warning(
                    f"{SPACE_6}Unknown DataQuality code '{dq_code}' for WaterLevels record {row.GlobalID}"
                )

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
            nma_data_quality=data_quality,
        )
        return observation

    def _make_sample(self, row, field_activity, dt_utc, sampler) -> Sample:
        sample_method = (
            "null placeholder"
            if pd.isna(row.MeasurementMethod)
            else lexicon_mapper.map_value(
                f"LU_MeasurementMethod:{row.MeasurementMethod}", "null placeholder"
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

    def _get_groundwater_level_reason(self, row) -> str:
        glv = row.LevelStatus
        if pd.isna(glv):
            return None

        if glv == "X?":
            glv = "X"
        glv = lexicon_mapper.map_value(f"LU_LevelStatus:{glv}")
        if glv == "Water level not affected by status":
            glv = "Water level not affected"
        elif glv is None:
            self._capture_error(
                row.PointID, f"Unknown groundwater level reason: {glv}", "LevelStatus"
            )
            raise ValueError(f"Unknown groundwater level reason: {glv}")
        return glv

    def _get_field_event_participants(self, session, row, thing) -> list[Contact]:
        self._last_contacts_created_count = 0
        self._last_contacts_reused_count = 0
        field_event_participants = []
        measured_by = None if pd.isna(row.MeasuredBy) else row.MeasuredBy

        if measured_by not in ["Owner", "Owner report", "Well owner"]:
            # --- Contact/FieldEventParticipant ---
            if measured_by:
                contact_info = get_contacts_info(
                    row, measured_by, self._measured_by_mapper
                )
                for name, organization, role in contact_info:
                    if (name, organization) in self._created_contacts:
                        contact = self._created_contacts[(name, organization)]
                        self._last_contacts_reused_count += 1
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
                            self._last_contacts_created_count += 1
                        except Exception as e:
                            logger.critical(
                                f"Contact cannot be created: Name {name} | Role {role} | Organization {organization} because of the following: {str(e)}"
                            )
                            continue

                    field_event_participants.append(contact)
        else:
            if thing.contacts:
                contact = thing.contacts[0]
                field_event_participants.append(contact)
                self._last_contacts_reused_count += 1
            else:
                logger.warning(
                    "Thing for PointID=%s has no contacts; cannot use owner fallback for %s",
                    row.PointID,
                    self._row_context(row),
                )
                self._capture_error(
                    row.PointID,
                    "Thing has no contacts for owner fallback",
                    "MeasuredBy",
                )

        if len(field_event_participants) == 0:
            logger.critical(
                f"No contacts can be associated with the WaterLevels record with GlobalID {row.GlobalID}, "
                f"therefore no field event, field activity, sample, and observation can be made. Skipping."
            )

        return field_event_participants

    def _row_context(self, row: Any) -> str:
        return (
            f"PointID={getattr(row, 'PointID', None)}, "
            f"OBJECTID={getattr(row, 'OBJECTID', None)}, "
            f"GlobalID={getattr(row, 'GlobalID', None)}"
        )

    def _log_transfer_summary(self, stats: dict[str, int]) -> None:
        logger.info(
            "WaterLevels summary: groups total=%s processed=%s skipped_missing_thing=%s failed_commit=%s "
            "rows total=%s created=%s skipped_dt=%s skipped_reason=%s skipped_contacts=%s well_destroyed=%s "
            "field_events=%s activities=%s samples=%s observations=%s contacts_created=%s contacts_reused=%s",
            stats["groups_total"],
            stats["groups_processed"],
            stats["groups_skipped_missing_thing"],
            stats["groups_failed_commit"],
            stats["rows_total"],
            stats["rows_created"],
            stats["rows_skipped_dt"],
            stats["rows_skipped_reason"],
            stats["rows_skipped_contacts"],
            stats["rows_well_destroyed"],
            stats["field_events_created"],
            stats["field_activities_created"],
            stats["samples_created"],
            stats["observations_created"],
            stats["contacts_created"],
            stats["contacts_reused"],
        )

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
                dot_index = t.find(".")
                t = t[: dot_index + 7]

            dt_measured = f"{row.DateMeasured} {t}"

        try:
            dt = datetime.strptime(dt_measured, fmt)
        except ValueError as e:
            self._capture_error(row.PointID, str(e), "DateMeasured")
            logger.critical(
                f"transfer_water_levels. Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to "
                f"invalid date/time: {e}"
            )
            return None

        time_datum = getattr(row, "TimeDatum", None)
        if time_datum and pd.notna(time_datum):
            datum = str(time_datum).strip().upper()
            if datum in {"MST", "MDT"}:
                offset_hours = -7 if datum == "MST" else -6
                tz = timezone(timedelta(hours=offset_hours))
                return dt.replace(tzinfo=tz).astimezone(timezone.utc)

        return convert_mt_to_utc(dt)


# ============= EOF =============================================
