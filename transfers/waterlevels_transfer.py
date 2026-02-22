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
from sqlalchemy import insert
from sqlalchemy.exc import DatabaseError, SQLAlchemyError
from sqlalchemy.orm import Session

from db import (
    Thing,
    ThingContactAssociation,
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
    replace_nans,
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
        self._thing_id_by_pointid: dict[str, int] = {}
        self._owner_contact_id_by_pointid: dict[str, int] = {}
        self._build_caches()

    def _build_caches(self) -> None:
        with session_ctx() as session:
            self._thing_id_by_pointid = {
                name: thing_id
                for name, thing_id in session.query(Thing.name, Thing.id).all()
            }

            owner_rows = (
                session.query(Thing.name, ThingContactAssociation.contact_id)
                .join(
                    ThingContactAssociation,
                    Thing.id == ThingContactAssociation.thing_id,
                )
                .order_by(Thing.name, ThingContactAssociation.id.asc())
                .all()
            )
            owner_contact_cache: dict[str, int] = {}
            for pointid, contact_id in owner_rows:
                owner_contact_cache.setdefault(pointid, contact_id)
            self._owner_contact_id_by_pointid = owner_contact_cache

        logger.info(
            "Built WaterLevels caches: %s Things, %s owner contacts",
            len(self._thing_id_by_pointid),
            len(self._owner_contact_id_by_pointid),
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table, dtype={"MeasuredBy": str})
        input_df = replace_nans(input_df)
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
            "rows_missing_participants": 0,
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

            thing_id = self._thing_id_by_pointid.get(pointid)
            if thing_id is None:
                stats["groups_skipped_missing_thing"] += 1
                self._capture_error(pointid, "Thing not found", "PointID")
                continue

            prepared_rows: list[dict[str, Any]] = []
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

                field_event_participants = self._get_field_event_participants(
                    session, row
                )
                stats["contacts_created"] += getattr(
                    self, "_last_contacts_created_count", 0
                )
                stats["contacts_reused"] += getattr(
                    self, "_last_contacts_reused_count", 0
                )

                if not field_event_participants:
                    stats["rows_missing_participants"] += 1

                is_destroyed = (
                    glv
                    == "Well was destroyed (no subsequent water levels should be recorded)"
                )
                if is_destroyed:
                    logger.warning(
                        "Well is destroyed for %s - no field activity/sample/observation will be made",
                        self._row_context(row),
                    )
                    stats["rows_well_destroyed"] += 1

                prepared_rows.append(
                    {
                        "row": row,
                        "dt_utc": dt_utc,
                        "glv": glv,
                        "release_status": release_status,
                        "participants": field_event_participants,
                        "is_destroyed": is_destroyed,
                    }
                )
                stats["rows_created"] += 1

            if not prepared_rows:
                stats["groups_processed"] += 1
                continue

            try:
                session.flush()

                # FieldEvent batch
                field_event_rows = [
                    {
                        "thing_id": thing_id,
                        "event_date": prep["dt_utc"],
                        "release_status": prep["release_status"],
                        "notes": prep["glv"] if prep["is_destroyed"] else None,
                    }
                    for prep in prepared_rows
                ]
                field_event_ids = (
                    session.execute(
                        insert(FieldEvent).returning(FieldEvent.id),
                        field_event_rows,
                    )
                    .scalars()
                    .all()
                )
                stats["field_events_created"] += len(field_event_rows)

                # FieldEventParticipant batch + lead participant id map
                participant_rows: list[dict[str, Any]] = []
                lead_row_pos_by_prepared_idx: dict[int, int] = {}
                for prepared_idx, prep in enumerate(prepared_rows):
                    for participant_idx, participant in enumerate(prep["participants"]):
                        participant_rows.append(
                            {
                                "field_event_id": field_event_ids[prepared_idx],
                                "contact_id": participant.id,
                                "participant_role": (
                                    "Lead" if participant_idx == 0 else "Participant"
                                ),
                                "release_status": prep["release_status"],
                            }
                        )
                        if participant_idx == 0:
                            lead_row_pos_by_prepared_idx[prepared_idx] = (
                                len(participant_rows) - 1
                            )

                lead_participant_id_by_prepared_idx: dict[int, int] = {}
                if participant_rows:
                    participant_ids = (
                        session.execute(
                            insert(FieldEventParticipant).returning(
                                FieldEventParticipant.id
                            ),
                            participant_rows,
                        )
                        .scalars()
                        .all()
                    )
                    for prepared_idx, pos in lead_row_pos_by_prepared_idx.items():
                        lead_participant_id_by_prepared_idx[prepared_idx] = (
                            participant_ids[pos]
                        )

                # FieldActivity batch (non-destroyed rows)
                field_activity_rows: list[dict[str, Any]] = []
                activity_row_pos_by_prepared_idx: dict[int, int] = {}
                for prepared_idx, prep in enumerate(prepared_rows):
                    if prep["is_destroyed"]:
                        continue
                    activity_row_pos_by_prepared_idx[prepared_idx] = len(
                        field_activity_rows
                    )
                    field_activity_rows.append(
                        {
                            "field_event_id": field_event_ids[prepared_idx],
                            "activity_type": "groundwater level",
                            "release_status": prep["release_status"],
                        }
                    )

                field_activity_ids: list[int] = []
                if field_activity_rows:
                    field_activity_ids = (
                        session.execute(
                            insert(FieldActivity).returning(FieldActivity.id),
                            field_activity_rows,
                        )
                        .scalars()
                        .all()
                    )
                    stats["field_activities_created"] += len(field_activity_rows)

                # Sample batch (non-destroyed rows)
                sample_rows: list[dict[str, Any]] = []
                sample_row_pos_by_prepared_idx: dict[int, int] = {}
                for prepared_idx, prep in enumerate(prepared_rows):
                    if prep["is_destroyed"]:
                        continue
                    sample_row_pos_by_prepared_idx[prepared_idx] = len(sample_rows)
                    sample_rows.append(
                        {
                            "nma_pk_waterlevels": prep["row"].GlobalID,
                            "field_activity_id": field_activity_ids[
                                activity_row_pos_by_prepared_idx[prepared_idx]
                            ],
                            "field_event_participant_id": lead_participant_id_by_prepared_idx.get(
                                prepared_idx
                            ),
                            "sample_date": prep["dt_utc"],
                            "sample_matrix": "water",
                            "sample_name": str(uuid.uuid4()),
                            "sample_method": self._get_sample_method(prep["row"]),
                            "qc_type": "Normal",
                            "depth_top": None,
                            "depth_bottom": None,
                            "release_status": prep["release_status"],
                        }
                    )

                sample_ids: list[int] = []
                if sample_rows:
                    sample_ids = (
                        session.execute(
                            insert(Sample).returning(Sample.id),
                            sample_rows,
                        )
                        .scalars()
                        .all()
                    )
                    stats["samples_created"] += len(sample_rows)

                # Observation batch (non-destroyed rows)
                observation_rows: list[dict[str, Any]] = []
                for prepared_idx, prep in enumerate(prepared_rows):
                    if prep["is_destroyed"]:
                        continue
                    sample_id = sample_ids[sample_row_pos_by_prepared_idx[prepared_idx]]
                    observation_rows.append(
                        self._make_observation_insert_row(
                            prep["row"],
                            sample_id,
                            prep["dt_utc"],
                            prep["glv"],
                            prep["release_status"],
                        )
                    )

                if observation_rows:
                    session.execute(insert(Observation), observation_rows)
                    stats["observations_created"] += len(observation_rows)

                session.commit()
                session.expunge_all()
                stats["groups_processed"] += 1
            except DatabaseError as e:
                stats["groups_failed_commit"] += 1
                session.rollback()
                self._capture_database_error(pointid, e)
            except SQLAlchemyError as e:
                stats["groups_failed_commit"] += 1
                session.rollback()
                self._capture_error(pointid, str(e), "SQLAlchemyError")
            except Exception as e:
                stats["groups_failed_commit"] += 1
                session.rollback()
                self._capture_error(pointid, str(e), "UnknownField")

        self._log_transfer_summary(stats)

    def _make_observation(
        self, row: pd.Series, sample: Sample, dt_utc: datetime, glv: str
    ) -> Observation:
        value, measuring_point_height, data_quality = self._get_observation_parts(row)
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

    def _get_observation_parts(
        self, row: pd.Series
    ) -> tuple[float | None, float | None, str | None]:
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
                mapped_quality = lexicon_mapper.map_value(f"LU_DataQuality:{dq_code}")
                if pd.isna(mapped_quality):
                    logger.warning(
                        "%sMapped DataQuality '%s' to NaN for WaterLevels record %s; "
                        "storing NULL to satisfy FK",
                        SPACE_6,
                        dq_code,
                        row.GlobalID,
                    )
                    self._capture_error(
                        row.PointID,
                        f"Mapped DataQuality '{dq_code}' to NaN; stored NULL",
                        "DataQuality",
                    )
                    data_quality = None
                else:
                    mapped_quality_text = str(mapped_quality).strip()
                    if mapped_quality_text and mapped_quality_text.lower() != "nan":
                        data_quality = mapped_quality_text
                    else:
                        logger.warning(
                            "%sMapped DataQuality '%s' to empty value for WaterLevels "
                            "record %s; storing NULL to satisfy FK",
                            SPACE_6,
                            dq_code,
                            row.GlobalID,
                        )
                        self._capture_error(
                            row.PointID,
                            f"Mapped DataQuality '{dq_code}' to empty value; stored NULL",
                            "DataQuality",
                        )
                        data_quality = None
            except KeyError:
                logger.warning(
                    f"{SPACE_6}Unknown DataQuality code '{dq_code}' for WaterLevels record {row.GlobalID}"
                )
                self._capture_error(
                    row.PointID,
                    f"Unknown DataQuality code '{dq_code}'",
                    "DataQuality",
                )

        return value, measuring_point_height, data_quality

    def _make_observation_insert_row(
        self,
        row: pd.Series,
        sample_id: int,
        dt_utc: datetime,
        glv: str,
        release_status: str,
    ) -> dict[str, Any]:
        value, measuring_point_height, data_quality = self._get_observation_parts(row)
        return {
            "nma_pk_waterlevels": row.GlobalID,
            "sample_id": sample_id,
            "sensor_id": None,
            "analysis_method_id": None,
            "observation_datetime": dt_utc,
            "parameter_id": self.groundwater_parameter_id,
            "value": value,
            "unit": "ft",
            "measuring_point_height": measuring_point_height,
            "groundwater_level_reason": glv,
            "nma_data_quality": data_quality,
            "release_status": release_status,
        }

    def _make_sample(self, row, field_activity, dt_utc, sampler) -> Sample:
        sample_method = self._get_sample_method(row)

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

    def _get_sample_method(self, row) -> str:
        return (
            "null placeholder"
            if pd.isna(row.MeasurementMethod)
            else lexicon_mapper.map_value(
                f"LU_MeasurementMethod:{row.MeasurementMethod}", "null placeholder"
            )
        )

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

    def _get_field_event_participants(self, session, row) -> list[Contact]:
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
            owner_contact_id = self._owner_contact_id_by_pointid.get(row.PointID)
            if owner_contact_id is None:
                logger.warning(
                    "Thing for PointID=%s has no owner contact; cannot use owner fallback for %s",
                    row.PointID,
                    self._row_context(row),
                )
                self._capture_error(
                    row.PointID,
                    "Thing has no contacts for owner fallback",
                    "MeasuredBy",
                )
            else:
                contact = session.get(Contact, owner_contact_id)
                if contact is None:
                    logger.warning(
                        "Owner contact id=%s not found for PointID=%s; cannot use owner fallback for %s",
                        owner_contact_id,
                        row.PointID,
                        self._row_context(row),
                    )
                    self._capture_error(
                        row.PointID,
                        f"owner contact id {owner_contact_id} not found",
                        "MeasuredBy",
                    )
                else:
                    field_event_participants.append(contact)
                    self._last_contacts_reused_count += 1

        if len(field_event_participants) == 0:
            logger.warning(
                f"No contacts can be associated with the WaterLevels record with GlobalID {row.GlobalID}; "
                f"continuing with nullable field_event_participant_id."
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
            "rows total=%s created=%s skipped_dt=%s skipped_reason=%s missing_participants=%s well_destroyed=%s "
            "field_events=%s activities=%s samples=%s observations=%s contacts_created=%s contacts_reused=%s",
            stats["groups_total"],
            stats["groups_processed"],
            stats["groups_skipped_missing_thing"],
            stats["groups_failed_commit"],
            stats["rows_total"],
            stats["rows_created"],
            stats["rows_skipped_dt"],
            stats["rows_skipped_reason"],
            stats["rows_missing_participants"],
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
