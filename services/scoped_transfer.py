from __future__ import annotations

import io
import json
import logging
import re
import warnings
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from functools import cached_property
from typing import Any, Callable

import pandas as pd
from pandas.errors import DtypeWarning
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from db import (
    Asset,
    AssetThingAssociation,
    Contact,
    FieldActivity,
    FieldEvent,
    FieldEventParticipant,
    Group,
    GroupThingAssociation,
    Location,
    LocationThingAssociation,
    NMA_Chemistry_SampleInfo,
    Notes,
    Observation,
    PermissionHistory,
    Sample,
    Thing,
    ThingContactAssociation,
    ThingIdLink,
)
from db.engine import session_ctx
from services.asset_helper import upload_and_associate
from services.util import (
    get_county_from_point,
    get_quad_name_from_point,
    get_state_from_point,
    retrieve_latest_polymorphic_history_table_record,
)
from transfers.asset_transfer import AssetTransferer
from transfers.associated_data import AssociatedDataTransferer
from transfers.chemistry_sampleinfo import ChemistrySampleInfoTransferer
from transfers.contact_transfer import ContactTransfer
from transfers.field_parameters_transfer import FieldParametersTransferer
from transfers.group_transfer import ProjectGroupTransferer
from transfers.hydraulicsdata import HydraulicsDataTransferer
from transfers.link_ids_transfer import (
    LinkIdsLocationDataTransferer,
    LinkIdsWellDataTransferer,
)
from transfers.logger import logger
from transfers.major_chemistry import MajorChemistryTransferer
from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer
from transfers.ngwmn_views import (
    NGWMNLithologyTransferer,
    NGWMNWaterLevelsTransferer,
    NGWMNWellConstructionTransferer,
)
from transfers.permissions_transfer import _make_permission
from transfers.radionuclides import RadionuclidesTransferer
from transfers.sensor_transfer import SensorTransferer
from transfers.soil_rock_results import SoilRockResultsTransferer
from transfers.stratigraphy_legacy import StratigraphyLegacyTransferer
from transfers.surface_water_data import SurfaceWaterDataTransferer
from transfers.surface_water_photos import SurfaceWaterPhotosTransferer
from transfers.thing_transfer import _release_status
from transfers.transferer import ChemistryTransferer, Transferer
from transfers.util import (
    filter_non_transferred_wells,
    filter_by_valid_measuring_agency,
    filter_to_valid_point_ids,
    get_transferable_wells,
    make_location,
    make_location_data_provenance,
    read_csv,
    replace_nans,
)
from transfers.waterlevels_transfer import WaterLevelTransferer, get_contacts_info
from transfers.waterlevels_transducer_transfer import (
    WaterLevelsContinuousAcousticTransferer,
    WaterLevelsContinuousPressureTransferer,
)
from transfers.waterlevelscontinuous_pressure_daily import (
    NMA_WaterLevelsContinuous_Pressure_DailyTransferer,
)
from transfers.weather_data import WeatherDataTransferer
from transfers.weather_photos import WeatherPhotosTransferer
from transfers.well_transfer import WellScreenTransferer, WellTransferer


class ScopedTransferError(RuntimeError):
    pass


@dataclass(slots=True)
class ScopedTransferOptions:
    pointids: list[str]
    only: list[str] = field(default_factory=list)
    skip: list[str] = field(default_factory=list)
    dry_run: bool = False


@dataclass(slots=True)
class ScopedFamilyResult:
    family: str
    status: str
    applicable_source_rows: int = 0
    created: int | None = None
    skipped_existing: int | None = None
    detail: str | None = None
    added_as_prerequisite: bool = False


@dataclass(slots=True)
class ScopedTransferResult:
    pointids: list[str]
    selected_families: list[str]
    added_prerequisites: list[str]
    dry_run: bool
    family_results: list[ScopedFamilyResult]
    validation_errors: list[str]
    execution_error: str | None = None
    exit_code: int = 0

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["family_results"] = [asdict(result) for result in self.family_results]
        return payload


@dataclass(frozen=True, slots=True)
class FamilySpec:
    name: str
    planner: Callable[["ScopedTransferRuntime"], ScopedFamilyResult]
    executor: Callable[["ScopedTransferRuntime"], ScopedFamilyResult]
    dependencies: tuple[str, ...] = ()


class ScopedTransferLogFilter(logging.Filter):
    """Hide legacy transfer warnings that are misleading in scoped CLI mode."""

    _suppressed_message_patterns = (
        re.compile(r"^\d+ PointIDs have duplicates; will skip\.$"),
        re.compile(r"^Duplicate PointIDs: "),
        re.compile(r"^Filtered out \d+ .+ without matching "),
        re.compile(r"^No second contact info for PointID .+, skipping\.$"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(
            pattern.match(message) for pattern in self._suppressed_message_patterns
        )


@contextmanager
def _suppress_transfer_noise():
    """Temporarily reduce reused transfer-module logging to scoped-CLI signal only."""

    root_logger = logging.getLogger()
    previous_level = root_logger.level
    previous_handler_levels = [handler.level for handler in root_logger.handlers]
    scoped_filter = ScopedTransferLogFilter()
    try:
        root_logger.setLevel(logging.WARNING)
        root_logger.addFilter(scoped_filter)
        for handler in root_logger.handlers:
            handler.setLevel(logging.WARNING)
            handler.addFilter(scoped_filter)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DtypeWarning)
            yield
    finally:
        root_logger.setLevel(previous_level)
        root_logger.removeFilter(scoped_filter)
        for handler, level in zip(root_logger.handlers, previous_handler_levels):
            handler.setLevel(level)
            handler.removeFilter(scoped_filter)


def normalize_pointids(pointids: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in pointids:
        value = (raw or "").strip().upper()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    if not normalized:
        raise ScopedTransferError("At least one --pointid value is required.")
    return normalized


def _filter_requested_pointids(
    df: pd.DataFrame | None, pointids: list[str] | None, column: str = "PointID"
) -> pd.DataFrame | None:
    if df is None or not pointids or column not in df.columns:
        return df
    normalized = df[column].astype(str).str.strip().str.upper()
    return df[normalized.isin(set(pointids))].copy()


def _matches_pointid_prefix(value: Any, pointids: list[str]) -> bool:
    if value is None or pd.isna(value):
        return False
    text = str(value).strip().upper()
    return any(text == pointid or text.startswith(f"{pointid}") for pointid in pointids)


class _PointIDFilteringMixin:
    def _get_dfs(self):
        input_df, cleaned_df = super()._get_dfs()
        cleaned_df = _filter_requested_pointids(cleaned_df, self.pointids)
        return input_df, cleaned_df


class ScopedWellScreenTransferer(_PointIDFilteringMixin, WellScreenTransferer):
    pass


class ScopedWellTransferer(WellTransferer):
    """Well transferer variant that applies PointID scoping before duplicate checks."""

    def _get_dfs(self):
        wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
        ldf = read_csv("Location")
        ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1)
        wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")
        wdf = wdf[wdf["SiteType"] == "GW"]
        wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

        input_df = wdf
        wdf = replace_nans(wdf)

        cleaned_df = get_transferable_wells(wdf)
        cleaned_df = filter_non_transferred_wells(cleaned_df)
        # In scoped mode, duplicate warnings should only consider the requested subset.
        cleaned_df = _filter_requested_pointids(cleaned_df, self.pointids)

        dupes = cleaned_df["PointID"].duplicated(keep=False)
        if dupes.any():
            dup_ids = set(cleaned_df.loc[dupes, "PointID"])
            logger.critical(f"{len(dup_ids)} PointIDs have duplicates; will skip.")
            logger.critical(f"Duplicate PointIDs: {dup_ids}")
            cleaned_df = cleaned_df[~cleaned_df["PointID"].isin(dup_ids)]

        cleaned_df = cleaned_df.sort_values(by=["PointID"])
        return input_df, cleaned_df


class ScopedSensorTransferer(_PointIDFilteringMixin, SensorTransferer):
    pass


class ScopedSurfaceWaterDataTransferer(
    _PointIDFilteringMixin, SurfaceWaterDataTransferer
):
    pass


class ScopedSurfaceWaterPhotosTransferer(
    _PointIDFilteringMixin, SurfaceWaterPhotosTransferer
):
    pass


class ScopedWeatherDataTransferer(_PointIDFilteringMixin, WeatherDataTransferer):
    pass


class ScopedWeatherPhotosTransferer(_PointIDFilteringMixin, WeatherPhotosTransferer):
    pass


class ScopedSoilRockResultsTransferer(
    _PointIDFilteringMixin, SoilRockResultsTransferer
):
    def _get_dfs(self):
        input_df = self._read_csv(self.source_table)
        cleaned_df = replace_nans(input_df)
        cleaned_df = _filter_requested_pointids(
            cleaned_df, self.pointids, column="Point_ID"
        )
        return input_df, cleaned_df


class ScopedHydraulicsDataTransferer(_PointIDFilteringMixin, HydraulicsDataTransferer):
    pass


class ScopedNGWMNWellConstructionTransferer(
    _PointIDFilteringMixin, NGWMNWellConstructionTransferer
):
    pass


class ScopedNGWMNWaterLevelsTransferer(
    _PointIDFilteringMixin, NGWMNWaterLevelsTransferer
):
    pass


class ScopedNGWMNLithologyTransferer(_PointIDFilteringMixin, NGWMNLithologyTransferer):
    pass


class ScopedPressureDailyTransferer(
    _PointIDFilteringMixin, NMA_WaterLevelsContinuous_Pressure_DailyTransferer
):
    pass


class ScopedPressureTransferer(
    _PointIDFilteringMixin, WaterLevelsContinuousPressureTransferer
):
    pass


class ScopedAcousticTransferer(
    _PointIDFilteringMixin, WaterLevelsContinuousAcousticTransferer
):
    pass


class ScopedAssociatedDataTransferer(_PointIDFilteringMixin, AssociatedDataTransferer):
    pass


class ScopedStratigraphyLegacyTransferer(StratigraphyLegacyTransferer):
    pass


class ScopedChemistrySampleInfoTransferer(ChemistrySampleInfoTransferer):
    def _build_thing_id_cache(self):
        with session_ctx() as session:
            query = (
                session.query(
                    Location.nma_pk_location, LocationThingAssociation.thing_id
                )
                .join(
                    LocationThingAssociation,
                    Location.id == LocationThingAssociation.location_id,
                )
                .join(Thing, Thing.id == LocationThingAssociation.thing_id)
                .filter(Location.nma_pk_location.isnot(None))
            )
            if self.pointids:
                query = query.filter(Thing.name.in_(self.pointids))

            results = query.all()
            location_to_thing = {}
            for nma_pk_location, thing_id in results:
                if nma_pk_location is None:
                    continue
                location_to_thing[str(nma_pk_location).lower()] = thing_id
            self._thing_id_cache = location_to_thing

        if not self._thing_id_cache:
            logger.info("No matching Thing/Location rows found for ChemistrySampleInfo")


class _ScopedChemistryMixin(ChemistryTransferer):
    def _build_sample_info_cache(self) -> None:
        with session_ctx() as session:
            query = (
                session.query(
                    NMA_Chemistry_SampleInfo.nma_sample_pt_id,
                    NMA_Chemistry_SampleInfo.id,
                )
                .join(Thing, Thing.id == NMA_Chemistry_SampleInfo.thing_id)
                .filter(NMA_Chemistry_SampleInfo.nma_sample_pt_id.isnot(None))
            )
            if self.pointids:
                query = query.filter(Thing.name.in_(self.pointids))

            sample_infos = query.all()
            self._sample_info_cache = {
                nma_sample_pt_id: csi_id for nma_sample_pt_id, csi_id in sample_infos
            }


class ScopedFieldParametersTransferer(_ScopedChemistryMixin, FieldParametersTransferer):
    pass


class ScopedMajorChemistryTransferer(_ScopedChemistryMixin, MajorChemistryTransferer):
    pass


class ScopedMinorTraceChemistryTransferer(
    _ScopedChemistryMixin, MinorTraceChemistryTransferer
):
    pass


class ScopedRadionuclidesTransferer(_ScopedChemistryMixin, RadionuclidesTransferer):
    pass


class ScopedProjectGroupTransferer(ProjectGroupTransferer):
    def _step(self, session: Session, df: pd.DataFrame, i: int, row: pd.Series):
        sql = select(Group).where(Group.name == row.Project)
        group = session.scalars(sql).one_or_none()
        if not group:
            group = Group(name=row.Project)

        for prefix in row.PointIDPrefix.split(","):
            prefix = prefix.strip()
            if not prefix:
                continue

            sql = select(Thing).where(Thing.name.like(f"{prefix}%"))
            if self.pointids:
                sql = sql.where(Thing.name.in_(self.pointids))
            records = session.scalars(sql).unique().all()
            if not records:
                continue

            existing_thing_ids = {assoc.thing_id for assoc in group.thing_associations}
            group_is_monitoring_plan = False
            for record in records:
                if not group_is_monitoring_plan and record.status_history:
                    monitoring_status = [
                        sh
                        for sh in record.status_history
                        if sh.status_type == "Monitoring Status"
                    ]
                    if monitoring_status:
                        monitoring_status = (
                            retrieve_latest_polymorphic_history_table_record(
                                record,
                                "status_history",
                                "Monitoring Status",
                            )
                        )
                        if monitoring_status.status_value == "Currently monitored":
                            group_is_monitoring_plan = True
                            group.group_type = "Monitoring Plan"

                if record.id in existing_thing_ids:
                    continue

                gta = GroupThingAssociation(group=group, thing=record)
                session.add(gta)
                group.thing_associations.append(gta)
                existing_thing_ids.add(record.id)

        session.add(group)
        session.commit()


class ScopedAssetTransferer(AssetTransferer):
    def _get_dfs(self):
        input_df = read_csv(self.source_table)
        cleaned_df = filter_to_valid_point_ids(input_df, self.pointids)
        return input_df, cleaned_df

    def _transfer_hook(self, session: Session):
        added_pointid = []
        for i, row in enumerate(self.cleaned_df.itertuples()):
            if row.PointID in added_pointid:
                continue

            added_pointid.append(row.PointID)
            well = (
                session.query(Thing)
                .filter(Thing.name == row.PointID, Thing.thing_type == "water well")
                .one_or_none()
            )
            if well is None:
                self._capture_error(row.PointID, "Thing not found", "PointID")
                continue
            self._asset_step(session, i, well)
            session.commit()

    def _asset_step(self, session, i, db_item):
        df = self.cleaned_df
        photos = df[df["PointID"] == db_item.name]
        if photos.empty:
            photos = df[df["PointID"] == db_item.name.replace("-", "")]
            if photos.empty:
                return

        existing_asset_names = {
            name
            for (name,) in session.query(Asset.name)
            .join(AssetThingAssociation, AssetThingAssociation.asset_id == Asset.id)
            .filter(AssetThingAssociation.thing_id == db_item.id)
            .all()
            if name
        }
        existing_asset_paths = {
            storage_path
            for (storage_path,) in session.query(Asset.storage_path)
            .join(AssetThingAssociation, AssetThingAssociation.asset_id == Asset.id)
            .filter(AssetThingAssociation.thing_id == db_item.id)
            .all()
            if storage_path
        }

        for row in photos.itertuples():
            photo_path = row.OLEPath
            srcblob = self._bucket.get_blob(f"nma-photos/{photo_path}")
            if not srcblob:
                self._capture_error(
                    db_item.name, f"No photo found for {photo_path}", "OLEPath"
                )
                continue

            _, filename = srcblob.name.split("/")
            if filename in existing_asset_names or any(
                storage_path.endswith(filename) for storage_path in existing_asset_paths
            ):
                continue

            payload = srcblob.download_as_bytes()
            upload = UploadFile(
                file=io.BytesIO(payload), filename=filename, size=len(payload)
            )
            uri = upload_and_associate(
                session,
                upload,
                self._bucket,
                db_item,
                filename,
                **{"label": filename, "mime_type": "image/png"},
            )
            existing_asset_names.add(filename)
            if isinstance(uri, tuple) and len(uri) > 1:
                existing_asset_paths.add(uri[1])


class ScopedLinkIdsWellDataTransferer(LinkIdsWellDataTransferer):
    def _get_dfs(self):
        input_df = read_csv(self.source_table, self.source_dtypes)
        wdf = replace_nans(input_df)
        cleaned_df = filter_to_valid_point_ids(wdf, self.pointids)
        return input_df, cleaned_df

    def _transfer_hook(self, session):
        df = self._get_df_to_iterate()
        for ci, chunk in enumerate(self._chunked_df(df)):
            thing_id_by_pointid = {
                name: thing_id
                for name, thing_id in session.query(Thing.name, Thing.id)
                .filter(Thing.name.in_(chunk.PointID.tolist()))
                .all()
            }
            logger.info(
                "Processing LinkIdsWellData chunk %s, %s rows, %s db items",
                ci,
                len(chunk),
                len(thing_id_by_pointid),
            )
            existing_link_keys = _fetch_existing_link_keys(
                session, thing_id_by_pointid.values()
            )

            rows_to_insert: list[dict[str, Any]] = []
            for row in chunk.itertuples(index=False):
                thing_id = thing_id_by_pointid.get(row.PointID)
                if thing_id is None:
                    self._missing_db_item_warning(row)
                    continue

                if pd.isna(row.OSEWellID) and pd.isna(row.OSEWelltagID):
                    continue

                for aid, relation, regex in (
                    (row.OSEWellID, "OSEPOD", self._ose_wellid_regex),
                    (row.OSEWelltagID, "OSEWellTagID", None),
                ):
                    if pd.isna(aid):
                        continue

                    aid_text = str(aid).strip()
                    if not aid_text or aid_text.casefold() in ("x", "?", "exempt"):
                        continue

                    if regex and not regex.match(aid_text):
                        continue

                    link_row = {
                        "thing_id": thing_id,
                        "relation": relation,
                        "alternate_id": aid_text,
                        "alternate_organization": "NMOSE",
                    }
                    link_key = _link_row_key(link_row)
                    if link_key in existing_link_keys:
                        continue

                    rows_to_insert.append(link_row)
                    existing_link_keys.add(link_key)

            if rows_to_insert:
                session.execute(insert(ThingIdLink), rows_to_insert)
            session.commit()
            session.expunge_all()

    def _chunked_df(self, df: pd.DataFrame):
        chunk_size = getattr(self, "chunk_size", 1000)
        for start in range(0, len(df), chunk_size):
            yield df.iloc[start : start + chunk_size]


class ScopedLinkIdsLocationTransferer(LinkIdsLocationDataTransferer):
    def _get_dfs(self):
        input_df = read_csv(
            self.source_table,
            {
                "SiteID": str,
                "Township": str,
                "TownshipDirection": str,
                "Range": str,
                "RangeDirection": str,
                "SectionQuarters": str,
            },
        )
        ldf = input_df[input_df["SiteType"] == self.site_type]
        ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
        ldf = replace_nans(ldf)
        cleaned_df = filter_to_valid_point_ids(ldf, self.pointids)
        return input_df, cleaned_df

    def _transfer_hook(self, session):
        df = self._get_df_to_iterate()
        for ci, chunk in enumerate(self._chunked_df(df)):
            thing_id_by_pointid = {
                name: thing_id
                for name, thing_id in session.query(Thing.name, Thing.id)
                .filter(Thing.name.in_(chunk.PointID.tolist()))
                .all()
            }
            logger.info(
                "Processing LinkIdsLocationData chunk %s, %s rows, %s db items",
                ci,
                len(chunk),
                len(thing_id_by_pointid),
            )
            existing_link_keys = _fetch_existing_link_keys(
                session, thing_id_by_pointid.values()
            )

            rows_to_insert: list[dict[str, Any]] = []
            for row in chunk.itertuples(index=False):
                thing_id = thing_id_by_pointid.get(row.PointID)
                if thing_id is None:
                    self._missing_db_item_warning(row)
                    continue

                for func in (
                    self._add_link_alternate_site_id,
                    self._add_link_site_id,
                    self._add_link_plss,
                ):
                    link_row = func(row, thing_id)
                    if not link_row:
                        continue
                    link_key = _link_row_key(link_row)
                    if link_key in existing_link_keys:
                        continue
                    rows_to_insert.append(link_row)
                    existing_link_keys.add(link_key)

            if rows_to_insert:
                session.execute(insert(ThingIdLink), rows_to_insert)
            session.commit()
            session.expunge_all()

    def _chunked_df(self, df: pd.DataFrame):
        chunk_size = getattr(self, "chunk_size", 1000)
        for start in range(0, len(df), chunk_size):
            yield df.iloc[start : start + chunk_size]


class ScopedWaterLevelTransferer(WaterLevelTransferer):
    """Scoped water-level transferer with rerun-safe contact and row handling."""

    def _build_caches(self) -> None:
        with session_ctx() as session:
            thing_query = session.query(Thing.name, Thing.id)
            if self.pointids:
                thing_query = thing_query.filter(Thing.name.in_(self.pointids))
            self._thing_id_by_pointid = {
                name: thing_id for name, thing_id in thing_query.all()
            }
            self._created_contact_id_by_key = {
                (name, organization): contact_id
                for name, organization, contact_id in session.query(
                    Contact.name, Contact.organization, Contact.id
                ).all()
            }
            owner_query = (
                session.query(Thing.name, ThingContactAssociation.contact_id)
                .join(
                    ThingContactAssociation,
                    Thing.id == ThingContactAssociation.thing_id,
                )
                .order_by(Thing.name, ThingContactAssociation.id.asc())
            )
            if self.pointids:
                owner_query = owner_query.filter(Thing.name.in_(self.pointids))
            owner_rows = owner_query.all()
            owner_contact_cache: dict[str, int] = {}
            for pointid, contact_id in owner_rows:
                owner_contact_cache.setdefault(pointid, contact_id)
            self._owner_contact_id_by_pointid = owner_contact_cache

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table, dtype={"MeasuredBy": str})
        input_df = replace_nans(input_df)
        cleaned_df = filter_to_valid_point_ids(input_df, self.pointids)
        cleaned_df = filter_by_valid_measuring_agency(cleaned_df)
        return input_df, cleaned_df

    def _lookup_existing_contact_ids(
        self, session: Session, keys: list[tuple[str, str]]
    ) -> dict[tuple[str, str], int]:
        existing_contact_ids: dict[tuple[str, str], int] = {}
        for name, organization in keys:
            contact_id = (
                session.query(Contact.id)
                .filter(
                    Contact.name == name,
                    Contact.organization == organization,
                )
                .scalar()
            )
            if contact_id is not None:
                existing_contact_ids[(name, organization)] = contact_id
        return existing_contact_ids

    def _get_field_event_participant_ids(self, session, row) -> list[int]:
        self._last_contacts_created_count = 0
        self._last_contacts_reused_count = 0
        field_event_participant_ids: list[int] = []
        measured_by = None if pd.isna(row.MeasuredBy) else row.MeasuredBy

        if measured_by not in ["Owner", "Owner report", "Well owner"]:
            if measured_by:
                contact_info = get_contacts_info(
                    row, measured_by, self._measured_by_mapper
                )
                contacts_to_create: list[dict[str, Any]] = []
                missing_keys: list[tuple[str, str]] = []
                for name, organization, role in contact_info:
                    key = (name, organization)
                    contact_id = self._created_contact_id_by_key.get(key)
                    if contact_id is not None:
                        field_event_participant_ids.append(contact_id)
                        self._last_contacts_reused_count += 1
                    else:
                        contacts_to_create.append(
                            {
                                "name": name,
                                "role": role,
                                "contact_type": "Field Event Participant",
                                "organization": organization,
                                "nma_pk_waterlevels": row.GlobalID,
                            }
                        )
                        missing_keys.append(key)

                if contacts_to_create:
                    try:
                        with session.begin_nested():
                            created_contact_ids = (
                                session.execute(
                                    insert(Contact).returning(Contact.id),
                                    contacts_to_create,
                                )
                                .scalars()
                                .all()
                            )
                    except Exception as e:
                        # Match the scoped reference branch behavior: if insert loses a race
                        # against an existing contact, reuse that contact instead of failing
                        # the whole water-level group.
                        logger.critical(
                            "Contact insert failed for PointID=%s, GlobalID=%s: %s",
                            row.PointID,
                            row.GlobalID,
                            str(e),
                        )
                        existing_contact_ids = self._lookup_existing_contact_ids(
                            session, missing_keys
                        )
                        unresolved_keys: list[tuple[str, str]] = []
                        for key in missing_keys:
                            existing_contact_id = existing_contact_ids.get(key)
                            if existing_contact_id is None:
                                unresolved_keys.append(key)
                                continue
                            self._created_contact_id_by_key[key] = existing_contact_id
                            field_event_participant_ids.append(existing_contact_id)
                            self._last_contacts_reused_count += 1

                        if unresolved_keys:
                            logger.critical(
                                "Unable to resolve existing contact ids for PointID=%s, GlobalID=%s, keys=%s",
                                row.PointID,
                                row.GlobalID,
                                unresolved_keys,
                            )
                    else:
                        for key, created_contact_id, payload in zip(
                            missing_keys, created_contact_ids, contacts_to_create
                        ):
                            self._created_contact_id_by_key[key] = created_contact_id
                            field_event_participant_ids.append(created_contact_id)
                            self._last_contacts_created_count += 1
        else:
            owner_contact_id = self._owner_contact_id_by_pointid.get(row.PointID)
            if owner_contact_id is None:
                self._capture_error(
                    row.PointID,
                    "Thing has no contacts for owner fallback",
                    "MeasuredBy",
                )
            else:
                field_event_participant_ids.append(owner_contact_id)
                self._last_contacts_reused_count += 1

        return field_event_participant_ids

    def _transfer_hook(self, session: Session) -> None:
        stats: dict[str, int] = {
            "rows_skipped_existing": 0,
            "field_events_created": 0,
            "field_activities_created": 0,
            "samples_created": 0,
            "observations_created": 0,
        }

        gwd = self.cleaned_df.groupby(["PointID"])
        for index, group in gwd:
            pointid = index[0]
            thing_id = self._thing_id_by_pointid.get(pointid)
            if thing_id is None:
                self._capture_error(pointid, "Thing not found", "PointID")
                continue

            group_globalids = [
                str(global_id)
                for global_id in group["GlobalID"].tolist()
                if pd.notna(global_id)
            ]
            existing_globalids: set[str] = set()
            if group_globalids:
                existing_globalids.update(
                    global_id
                    for (global_id,) in session.query(Sample.nma_pk_waterlevels)
                    .filter(Sample.nma_pk_waterlevels.in_(group_globalids))
                    .all()
                    if global_id
                )
                existing_globalids.update(
                    global_id
                    for (global_id,) in session.query(Observation.nma_pk_waterlevels)
                    .filter(Observation.nma_pk_waterlevels.in_(group_globalids))
                    .all()
                    if global_id
                )

            prepared_rows: list[dict[str, Any]] = []
            for row in group.itertuples():
                row_globalid = str(row.GlobalID) if pd.notna(row.GlobalID) else None
                if row_globalid and row_globalid in existing_globalids:
                    # Scoped reruns should skip already-imported legacy water-level rows.
                    stats["rows_skipped_existing"] += 1
                    continue

                dt_utc = self._get_dt_utc(row)
                if dt_utc is None:
                    continue
                try:
                    glv = self._get_groundwater_level_reason(row)
                except (KeyError, ValueError) as exc:
                    self._capture_error(
                        row.PointID,
                        f"invalid groundwater level reason: {exc}",
                        "LevelStatus",
                    )
                    continue

                release_status = "public" if row.PublicRelease else "private"
                participant_ids = self._get_field_event_participant_ids(session, row)
                is_destroyed = (
                    glv
                    == "Well was destroyed (no subsequent water levels should be recorded)"
                )
                prepared_rows.append(
                    {
                        "row": row,
                        "dt_utc": dt_utc,
                        "glv": glv,
                        "release_status": release_status,
                        "participant_ids": participant_ids,
                        "is_destroyed": is_destroyed,
                    }
                )

            for prep in prepared_rows:
                field_event = FieldEvent(
                    thing_id=thing_id,
                    event_date=prep["dt_utc"],
                    release_status=prep["release_status"],
                    notes=prep["glv"] if prep["is_destroyed"] else None,
                )
                session.add(field_event)
                session.flush()
                stats["field_events_created"] += 1

                lead_participant = None
                participants: list[FieldEventParticipant] = []
                for participant_idx, participant_id in enumerate(
                    prep["participant_ids"]
                ):
                    participant = FieldEventParticipant(
                        field_event_id=field_event.id,
                        contact_id=participant_id,
                        participant_role=(
                            "Lead" if participant_idx == 0 else "Participant"
                        ),
                        release_status=prep["release_status"],
                    )
                    session.add(participant)
                    participants.append(participant)
                if participants:
                    session.flush()
                    lead_participant = participants[0]

                if prep["is_destroyed"]:
                    continue

                field_activity = FieldActivity(
                    field_event_id=field_event.id,
                    activity_type="groundwater level",
                    release_status=prep["release_status"],
                )
                session.add(field_activity)
                session.flush()
                stats["field_activities_created"] += 1

                sample = self._make_sample(
                    prep["row"],
                    field_activity,
                    prep["dt_utc"],
                    lead_participant,
                )
                sample.release_status = prep["release_status"]
                session.add(sample)
                session.flush()
                stats["samples_created"] += 1

                observation = self._make_observation(
                    prep["row"],
                    sample,
                    prep["dt_utc"],
                    prep["glv"],
                )
                observation.release_status = prep["release_status"]
                session.add(observation)
                stats["observations_created"] += 1

            unique_notes: dict[tuple[str, Any], Any] = {}
            for prep in prepared_rows:
                site_notes = getattr(prep["row"], "SiteNotes", None)
                if site_notes:
                    content = str(site_notes).strip()
                    if content:
                        dt = prep["dt_utc"]
                        key = (content, dt.date())
                        if key not in unique_notes:
                            unique_notes[key] = dt

            for (content, _), dt in unique_notes.items():
                date_prefix = dt.strftime("%Y-%m-%d")
                session.add(
                    Notes(
                        target_table="thing",
                        target_id=thing_id,
                        note_type="Site Notes (legacy)",
                        content=f"{date_prefix}: {content}",
                        release_status="public",
                    )
                )

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise


def _fetch_existing_link_keys(
    session: Session, thing_ids: list[int] | Any
) -> set[tuple[int, str, str, str]]:
    thing_ids = list(thing_ids)
    if not thing_ids:
        return set()
    return {
        (
            thing_id,
            relation,
            alternate_id,
            alternate_organization,
        )
        for thing_id, relation, alternate_id, alternate_organization in session.query(
            ThingIdLink.thing_id,
            ThingIdLink.relation,
            ThingIdLink.alternate_id,
            ThingIdLink.alternate_organization,
        )
        .filter(ThingIdLink.thing_id.in_(thing_ids))
        .all()
    }


def _link_row_key(row: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        int(row["thing_id"]),
        str(row["relation"]),
        str(row["alternate_id"]),
        str(row["alternate_organization"]),
    )


class ScopedTransferRuntime:
    def __init__(self, options: ScopedTransferOptions):
        self.options = ScopedTransferOptions(
            pointids=normalize_pointids(options.pointids),
            only=list(options.only or []),
            skip=list(options.skip or []),
            dry_run=bool(options.dry_run),
        )
        self._registry = build_family_registry()

    @cached_property
    def selected_family_names(self) -> list[str]:
        only = [name.strip() for name in self.options.only if name and name.strip()]
        skip = [name.strip() for name in self.options.skip if name and name.strip()]
        overlap = set(only) & set(skip)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ScopedTransferError(
                f"Cannot use the same family in both --only and --skip: {names}"
            )

        if only:
            selected = list(dict.fromkeys(only))
        else:
            selected = list(DEFAULT_FAMILY_ORDER)
            if skip:
                selected = [name for name in selected if name not in set(skip)]

        unknown = [name for name in selected if name not in self._registry]
        if unknown:
            raise ScopedTransferError(
                f"Unknown scoped-transfer family: {', '.join(sorted(unknown))}"
            )

        resolved: list[str] = []
        added: set[str] = set()

        def add_family(name: str):
            if name in resolved:
                return
            for dep in self._registry[name].dependencies:
                add_family(dep)
                added.add(dep)
            if name not in resolved:
                resolved.append(name)

        for family in selected:
            add_family(family)
        self._added_prerequisites = sorted(
            dep for dep in added if dep not in set(only or selected)
        )
        return resolved

    @property
    def added_prerequisites(self) -> list[str]:
        _ = self.selected_family_names
        return getattr(self, "_added_prerequisites", [])

    @property
    def registry(self) -> dict[str, FamilySpec]:
        return self._registry


DEFAULT_FAMILY_ORDER = [
    "wells",
    "springs",
    "perennial-streams",
    "ephemeral-streams",
    "met-stations",
    "rock-sample-locations",
    "diversion-of-surface-water",
    "lake-pond-reservoir",
    "soil-gas-sample-locations",
    "other-site-types",
    "outfall-wastewater-return-flow",
    "screens",
    "contacts",
    "permissions",
    "waterlevels",
    "link-ids",
    "groups",
    "assets",
    "associated-data",
    "hydraulics-data",
    "chemistry-sampleinfo",
    "field-parameters",
    "major-chemistry",
    "radionuclides",
    "minor-trace-chemistry",
    "sensors",
    "pressure",
    "acoustic",
    "pressure-daily",
    "ngwmn-views",
    "nma-stratigraphy",
    "surface-water-data",
    "surface-water-photos",
    "weather-data",
    "weather-photos",
    "soil-rock-results",
    "cleanup-locations",
]


def _run_transferer_class(
    klass: type[Transferer], pointids: list[str]
) -> ScopedFamilyResult:
    transferer = klass(pointids=pointids)
    transferer.transfer()
    applicable_rows = (
        len(transferer.cleaned_df) if transferer.cleaned_df is not None else 0
    )
    status = "completed" if applicable_rows else "no-op"
    return ScopedFamilyResult(
        family="",
        status=status,
        applicable_source_rows=applicable_rows,
    )


def _execute_wells(pointids: list[str]) -> ScopedFamilyResult:
    transferer = ScopedWellTransferer(pointids=pointids)
    # WellTransferer only supports the parallel entrypoint; run it with a
    # single worker so the CLI stays effectively serial.
    transferer.transfer_parallel(num_workers=1)
    applicable_rows = (
        len(transferer.cleaned_df) if transferer.cleaned_df is not None else 0
    )
    status = "completed" if applicable_rows else "no-op"
    return ScopedFamilyResult(
        family="",
        status=status,
        applicable_source_rows=applicable_rows,
    )


def _plan_transferer_class(
    klass: type[Transferer], pointids: list[str]
) -> ScopedFamilyResult:
    transferer = klass(pointids=pointids)
    _input_df, cleaned_df = transferer._get_dfs()
    applicable_rows = len(cleaned_df) if cleaned_df is not None else 0
    status = "planned" if applicable_rows else "no-op"
    return ScopedFamilyResult(
        family="",
        status=status,
        applicable_source_rows=applicable_rows,
    )


def _plan_direct_pointid_table(
    source_table: str,
    pointids: list[str],
    *,
    site_type: str | None = None,
    pointid_column: str = "PointID",
) -> ScopedFamilyResult:
    df = read_csv(source_table)
    if site_type and "SiteType" in df.columns:
        df = df[df["SiteType"] == site_type]
    filtered = _filter_requested_pointids(df, pointids, pointid_column)
    count = len(filtered) if filtered is not None else 0
    return ScopedFamilyResult(
        family="",
        status="planned" if count else "no-op",
        applicable_source_rows=count,
    )


def _plan_waterlevels(pointids: list[str]) -> ScopedFamilyResult:
    df = read_csv("WaterLevels", dtype={"MeasuredBy": str})
    df = replace_nans(df)
    df = _filter_requested_pointids(df, pointids)
    df = filter_by_valid_measuring_agency(df)
    count = len(df) if df is not None else 0
    return ScopedFamilyResult(
        family="waterlevels",
        status="planned" if count else "no-op",
        applicable_source_rows=count,
    )


def _plan_sensors(pointids: list[str]) -> ScopedFamilyResult:
    df = read_csv("Equipment")
    if " " in "".join(df.columns.tolist()):
        df.columns = df.columns.str.replace(" ", "_")
    df = df[df["SerialNo"].notna()]
    df = _filter_requested_pointids(df, pointids)
    count = len(df) if df is not None else 0
    return ScopedFamilyResult(
        family="sensors",
        status="planned" if count else "no-op",
        applicable_source_rows=count,
    )


def _plan_contacts(pointids: list[str]) -> ScopedFamilyResult:
    owners_df = read_csv("OwnersData")
    owner_link_df = read_csv("OwnerLink")
    location_df = read_csv("Location")
    owner_link_df = owner_link_df.join(
        location_df.set_index("LocationId"), on="LocationId"
    )
    owner_link_df = _filter_requested_pointids(owner_link_df, pointids)
    if owner_link_df is None or owner_link_df.empty:
        return ScopedFamilyResult(
            family="contacts",
            status="no-op",
            applicable_source_rows=0,
        )

    owner_keys = (
        owner_link_df["OwnerKey"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.casefold()
        .unique()
    )
    owners_df = owners_df.copy()
    owner_key_column = next(
        (column for column in owners_df.columns if column.lower() == "ownerkey"),
        None,
    )
    if owner_key_column is None:
        return ScopedFamilyResult(
            family="contacts",
            status="no-op",
            applicable_source_rows=0,
        )
    normalized_owner_keys = (
        owners_df[owner_key_column].fillna("").astype(str).str.strip().str.casefold()
    )
    owners_df = owners_df[normalized_owner_keys.isin(set(owner_keys))]
    return ScopedFamilyResult(
        family="contacts",
        status="planned" if not owners_df.empty else "no-op",
        applicable_source_rows=len(owners_df),
    )


def _plan_groups(pointids: list[str]) -> ScopedFamilyResult:
    df = read_csv("Projects", {"Project": str, "PointIDPrefix": str})
    if df is None or df.empty:
        return ScopedFamilyResult(
            family="groups",
            status="no-op",
            applicable_source_rows=0,
        )

    matched = 0
    for row in df.itertuples(index=False):
        prefixes = [
            prefix.strip().upper() for prefix in str(row.PointIDPrefix).split(",")
        ]
        if any(
            any(pointid.startswith(prefix) for prefix in prefixes if prefix)
            for pointid in pointids
        ):
            matched += 1

    return ScopedFamilyResult(
        family="groups",
        status="planned" if matched else "no-op",
        applicable_source_rows=matched,
    )


def _get_sample_point_ids_for_pointids(pointids: list[str]) -> set[str]:
    df = read_csv("Chemistry_SampleInfo")
    if df is None or df.empty:
        return set()
    sample_info_df = df[
        df["SamplePointID"].map(lambda value: _matches_pointid_prefix(value, pointids))
    ]
    return {
        str(value).strip().upper()
        for value in sample_info_df["SamplePtID"].tolist()
        if value is not None and pd.notna(value)
    }


def _plan_chemistry_sampleinfo(pointids: list[str]) -> ScopedFamilyResult:
    df = read_csv("Chemistry_SampleInfo")
    if df is None or df.empty:
        return ScopedFamilyResult(
            family="chemistry-sampleinfo",
            status="no-op",
            applicable_source_rows=0,
        )
    filtered = df[
        df["SamplePointID"].map(lambda value: _matches_pointid_prefix(value, pointids))
    ]
    return ScopedFamilyResult(
        family="chemistry-sampleinfo",
        status="planned" if not filtered.empty else "no-op",
        applicable_source_rows=len(filtered),
    )


def _plan_chemistry_child_table(
    source_table: str, pointids: list[str]
) -> ScopedFamilyResult:
    sample_pt_ids = _get_sample_point_ids_for_pointids(pointids)
    if not sample_pt_ids:
        return ScopedFamilyResult(family="", status="no-op", applicable_source_rows=0)

    df = read_csv(source_table)
    if df is None or df.empty:
        return ScopedFamilyResult(family="", status="no-op", applicable_source_rows=0)

    sample_ids = df["SamplePtID"].fillna("").astype(str).str.strip().str.upper()
    filtered = df[sample_ids.isin(sample_pt_ids)]
    return ScopedFamilyResult(
        family="",
        status="planned" if not filtered.empty else "no-op",
        applicable_source_rows=len(filtered),
    )


def _plan_ngwmn_views(pointids: list[str]) -> ScopedFamilyResult:
    total = 0
    for table_name in (
        "view_NGWMN_WaterLevels",
        "view_NGWMN_WellConstruction",
        "view_NGWMN_Lithology",
    ):
        df = read_csv(table_name)
        filtered = _filter_requested_pointids(df, pointids)
        total += len(filtered) if filtered is not None else 0
    return ScopedFamilyResult(
        family="ngwmn-views",
        status="planned" if total else "no-op",
        applicable_source_rows=total,
    )


def _execute_permissions(pointids: list[str]) -> ScopedFamilyResult:
    with session_ctx() as session:
        wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
        wdf = replace_nans(wdf)
        wdf = _filter_requested_pointids(wdf, pointids)

        transferred_wells = (
            session.query(Thing, Contact)
            .select_from(Thing)
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .filter(Thing.thing_type == "water well")
            .filter(Thing.name.in_(pointids))
            .order_by(Thing.name)
            .all()
        )

        existing_permissions = {
            (target_id, contact_id, permission_type)
            for target_id, contact_id, permission_type in session.query(
                PermissionHistory.target_id,
                PermissionHistory.contact_id,
                PermissionHistory.permission_type,
            )
            .filter(PermissionHistory.target_table == "thing")
            .all()
        }

        created_count = 0
        skipped_existing = 0
        for thing, contact in transferred_wells:
            for field_name, permission_type in (
                ("SampleOK", "Water Chemistry Sample"),
                ("MonitorOK", "Water Level Sample"),
            ):
                permission = _make_permission(
                    wdf, thing, contact.id, field_name, permission_type
                )
                if permission is None:
                    continue
                key = (thing.id, contact.id, permission.permission_type)
                if key in existing_permissions:
                    skipped_existing += 1
                    continue
                session.add(permission)
                existing_permissions.add(key)
                created_count += 1

        session.commit()
        return ScopedFamilyResult(
            family="permissions",
            status="completed" if transferred_wells else "no-op",
            applicable_source_rows=len(transferred_wells),
            created=created_count,
            skipped_existing=skipped_existing,
        )


_THING_SITE_TYPE_SPECS: dict[str, tuple[str, str]] = {
    "springs": ("SP", "spring"),
    "perennial-streams": ("PS", "perennial stream"),
    "ephemeral-streams": ("ES", "ephemeral stream"),
    "met-stations": ("MS", "met station"),
    "rock-sample-locations": ("R", "rock sample location"),
    "diversion-of-surface-water": ("D", "diversion of surface water"),
    "lake-pond-reservoir": ("L", "lake, pond, reservoir"),
    "soil-gas-sample-locations": ("SG", "soil gas sample location"),
    "other-site-types": ("O", "other site type"),
    "outfall-wastewater-return-flow": ("OW", "outfall wastewater return flow"),
}


def _make_thing_payload_factory(thing_type: str):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": thing_type,
            "release_status": _release_status(row),
        }

    return make_payload


def _plan_non_well_family(pointids: list[str], site_type: str) -> ScopedFamilyResult:
    df = read_csv("Location")
    df = replace_nans(df)
    df = df[df["SiteType"] == site_type]
    df = df[df["Easting"].notna() & df["Northing"].notna()]
    df = _filter_requested_pointids(df, pointids)
    count = len(df)
    return ScopedFamilyResult(
        family="",
        status="planned" if count else "no-op",
        applicable_source_rows=count,
    )


def _execute_non_well_family(
    family: str, pointids: list[str], site_type: str, thing_type: str
) -> ScopedFamilyResult:
    df = read_csv("Location")
    df = replace_nans(df)
    df = df[df["SiteType"] == site_type]
    df = df[df["Easting"].notna() & df["Northing"].notna()]
    df = _filter_requested_pointids(df, pointids)

    if df is None or df.empty:
        return ScopedFamilyResult(
            family=family,
            status="no-op",
            applicable_source_rows=0,
        )

    duplicate_mask = df["PointID"].duplicated(keep=False)
    duplicate_pointids = set(df.loc[duplicate_mask, "PointID"])
    cached_elevations: dict[str, Any] = {}
    payload_factory = _make_thing_payload_factory(thing_type)
    created = 0
    skipped_existing = 0

    with session_ctx() as session:
        existing_names = {
            name
            for (name,) in session.query(Thing.name)
            .filter(Thing.name.in_(df["PointID"].tolist()))
            .all()
        }

        for row in df.itertuples(index=False):
            if row.PointID in duplicate_pointids:
                continue
            if row.PointID in existing_names:
                skipped_existing += 1
                continue

            location, elevation_method, location_notes = make_location(
                row, cached_elevations
            )
            session.add(location)
            session.flush()
            payload = payload_factory(row)
            thing = Thing(
                name=payload["name"],
                thing_type=payload["thing_type"],
                release_status=payload["release_status"],
                nma_pk_location=row.LocationId,
            )
            session.add(thing)
            session.flush()
            session.add(
                LocationThingAssociation(location_id=location.id, thing_id=thing.id)
            )
            for note_type, note_content in location_notes.items():
                if pd.notna(note_content):
                    session.add(
                        Notes(
                            target_id=location.id,
                            target_table="location",
                            note_type=note_type,
                            content=note_content,
                            release_status="draft",
                        )
                    )
            location_stub = type("LocationStub", (), {"id": location.id})()
            for provenance in make_location_data_provenance(
                row, location_stub, elevation_method
            ):
                session.add(provenance)
            created += 1
            existing_names.add(row.PointID)

        session.commit()

    return ScopedFamilyResult(
        family=family,
        status="completed" if created or skipped_existing else "no-op",
        applicable_source_rows=len(df),
        created=created,
        skipped_existing=skipped_existing,
    )


def _execute_cleanup_locations(pointids: list[str]) -> ScopedFamilyResult:
    with session_ctx() as session:
        locations = (
            session.query(Location)
            .join(
                LocationThingAssociation,
                LocationThingAssociation.location_id == Location.id,
            )
            .join(Thing, Thing.id == LocationThingAssociation.thing_id)
            .filter(Thing.name.in_(pointids))
            .all()
        )

        updates = []
        for location in locations:
            y, x = location.latlon
            updates.append(
                {
                    "id": location.id,
                    "state": location.state or get_state_from_point(x, y),
                    "county": location.county or get_county_from_point(x, y),
                    "quad_name": location.quad_name or get_quad_name_from_point(x, y),
                }
            )
        if updates:
            session.bulk_update_mappings(Location, updates)
            session.commit()

        return ScopedFamilyResult(
            family="cleanup-locations",
            status="completed" if updates else "no-op",
            applicable_source_rows=len(locations),
            created=len(updates),
        )


def build_family_registry() -> dict[str, FamilySpec]:
    registry: dict[str, FamilySpec] = {
        "wells": FamilySpec(
            "wells",
            planner=lambda rt: _plan_transferer_class(
                ScopedWellTransferer, rt.options.pointids
            ),
            executor=lambda rt: _execute_wells(rt.options.pointids),
        ),
        "screens": FamilySpec(
            "screens",
            planner=lambda rt: _plan_transferer_class(
                ScopedWellScreenTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedWellScreenTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "contacts": FamilySpec(
            "contacts",
            planner=lambda rt: _plan_contacts(rt.options.pointids),
            executor=lambda rt: _run_transferer_class(
                ContactTransfer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "permissions": FamilySpec(
            "permissions",
            planner=lambda rt: _plan_direct_pointid_table(
                "WellData", rt.options.pointids
            ),
            executor=lambda rt: _execute_permissions(rt.options.pointids),
            dependencies=("wells", "contacts"),
        ),
        "waterlevels": FamilySpec(
            "waterlevels",
            planner=lambda rt: _plan_waterlevels(rt.options.pointids),
            executor=lambda rt: _run_transferer_class(
                ScopedWaterLevelTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "pressure": FamilySpec(
            "pressure",
            planner=lambda rt: _plan_transferer_class(
                ScopedPressureTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedPressureTransferer, rt.options.pointids
            ),
            dependencies=("wells", "sensors"),
        ),
        "acoustic": FamilySpec(
            "acoustic",
            planner=lambda rt: _plan_transferer_class(
                ScopedAcousticTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedAcousticTransferer, rt.options.pointids
            ),
            dependencies=("wells", "sensors"),
        ),
        "pressure-daily": FamilySpec(
            "pressure-daily",
            planner=lambda rt: _plan_transferer_class(
                ScopedPressureDailyTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedPressureDailyTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "sensors": FamilySpec(
            "sensors",
            planner=lambda rt: _plan_sensors(rt.options.pointids),
            executor=lambda rt: _run_transferer_class(
                ScopedSensorTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "groups": FamilySpec(
            "groups",
            planner=lambda rt: _plan_groups(rt.options.pointids),
            executor=lambda rt: _run_transferer_class(
                ScopedProjectGroupTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "assets": FamilySpec(
            "assets",
            planner=lambda rt: _plan_direct_pointid_table(
                "WellPhotos", rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedAssetTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "associated-data": FamilySpec(
            "associated-data",
            planner=lambda rt: _plan_transferer_class(
                ScopedAssociatedDataTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedAssociatedDataTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "hydraulics-data": FamilySpec(
            "hydraulics-data",
            planner=lambda rt: _plan_transferer_class(
                ScopedHydraulicsDataTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedHydraulicsDataTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "chemistry-sampleinfo": FamilySpec(
            "chemistry-sampleinfo",
            planner=lambda rt: _plan_chemistry_sampleinfo(rt.options.pointids),
            executor=lambda rt: _run_transferer_class(
                ScopedChemistrySampleInfoTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "field-parameters": FamilySpec(
            "field-parameters",
            planner=lambda rt: _plan_chemistry_child_table(
                "FieldParameters", rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedFieldParametersTransferer, rt.options.pointids
            ),
            dependencies=("chemistry-sampleinfo",),
        ),
        "major-chemistry": FamilySpec(
            "major-chemistry",
            planner=lambda rt: _plan_chemistry_child_table(
                "MajorChemistry", rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedMajorChemistryTransferer, rt.options.pointids
            ),
            dependencies=("chemistry-sampleinfo",),
        ),
        "minor-trace-chemistry": FamilySpec(
            "minor-trace-chemistry",
            planner=lambda rt: _plan_chemistry_child_table(
                "MinorandTraceChemistry", rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedMinorTraceChemistryTransferer, rt.options.pointids
            ),
            dependencies=("chemistry-sampleinfo",),
        ),
        "radionuclides": FamilySpec(
            "radionuclides",
            planner=lambda rt: _plan_chemistry_child_table(
                "Radionuclides", rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedRadionuclidesTransferer, rt.options.pointids
            ),
            dependencies=("chemistry-sampleinfo",),
        ),
        "ngwmn-views": FamilySpec(
            "ngwmn-views",
            planner=lambda rt: _plan_ngwmn_views(rt.options.pointids),
            executor=lambda rt: _execute_ngwmn_views(rt.options.pointids),
            dependencies=("wells",),
        ),
        "nma-stratigraphy": FamilySpec(
            "nma-stratigraphy",
            planner=lambda rt: _plan_transferer_class(
                ScopedStratigraphyLegacyTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedStratigraphyLegacyTransferer, rt.options.pointids
            ),
            dependencies=("wells",),
        ),
        "surface-water-data": FamilySpec(
            "surface-water-data",
            planner=lambda rt: _plan_transferer_class(
                ScopedSurfaceWaterDataTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedSurfaceWaterDataTransferer, rt.options.pointids
            ),
        ),
        "surface-water-photos": FamilySpec(
            "surface-water-photos",
            planner=lambda rt: _plan_transferer_class(
                ScopedSurfaceWaterPhotosTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedSurfaceWaterPhotosTransferer, rt.options.pointids
            ),
        ),
        "weather-data": FamilySpec(
            "weather-data",
            planner=lambda rt: _plan_transferer_class(
                ScopedWeatherDataTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedWeatherDataTransferer, rt.options.pointids
            ),
        ),
        "weather-photos": FamilySpec(
            "weather-photos",
            planner=lambda rt: _plan_transferer_class(
                ScopedWeatherPhotosTransferer, rt.options.pointids
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedWeatherPhotosTransferer, rt.options.pointids
            ),
        ),
        "soil-rock-results": FamilySpec(
            "soil-rock-results",
            planner=lambda rt: _plan_direct_pointid_table(
                "Soil_Rock_Results",
                rt.options.pointids,
                pointid_column="Point_ID",
            ),
            executor=lambda rt: _run_transferer_class(
                ScopedSoilRockResultsTransferer, rt.options.pointids
            ),
        ),
        "cleanup-locations": FamilySpec(
            "cleanup-locations",
            planner=lambda rt: ScopedFamilyResult(
                family="cleanup-locations",
                status="planned",
                applicable_source_rows=len(rt.options.pointids),
            ),
            executor=lambda rt: _execute_cleanup_locations(rt.options.pointids),
        ),
        "link-ids": FamilySpec(
            "link-ids",
            planner=lambda rt: _plan_direct_pointid_table(
                "WellData", rt.options.pointids
            ),
            executor=lambda rt: _execute_link_ids(rt.options.pointids),
            dependencies=("wells",),
        ),
    }

    for family_name, (site_type, thing_type) in _THING_SITE_TYPE_SPECS.items():
        registry[family_name] = FamilySpec(
            family_name,
            planner=lambda rt, st=site_type: _plan_non_well_family(
                rt.options.pointids, st
            ),
            executor=lambda rt, fn=family_name, st=site_type, tt=thing_type: _execute_non_well_family(
                fn, rt.options.pointids, st, tt
            ),
        )

    return registry


def _execute_link_ids(pointids: list[str]) -> ScopedFamilyResult:
    _run_transferer_class(ScopedLinkIdsWellDataTransferer, pointids)
    _run_transferer_class(ScopedLinkIdsLocationTransferer, pointids)
    well_df = _filter_requested_pointids(
        replace_nans(read_csv("WellData", {"OSEWellID": str, "OSEWelltagID": str})),
        pointids,
    )
    location_df = _filter_requested_pointids(
        replace_nans(
            read_csv(
                "Location",
                {
                    "SiteID": str,
                    "Township": str,
                    "TownshipDirection": str,
                    "Range": str,
                    "RangeDirection": str,
                    "SectionQuarters": str,
                },
            )
        ),
        pointids,
    )
    count = len(well_df) + len(location_df)
    return ScopedFamilyResult(
        family="link-ids",
        status="completed" if count else "no-op",
        applicable_source_rows=count,
    )


def _execute_ngwmn_views(pointids: list[str]) -> ScopedFamilyResult:
    results = [
        _run_transferer_class(ScopedNGWMNWellConstructionTransferer, pointids),
        _run_transferer_class(ScopedNGWMNWaterLevelsTransferer, pointids),
        _run_transferer_class(ScopedNGWMNLithologyTransferer, pointids),
    ]
    count = sum(result.applicable_source_rows for result in results)
    return ScopedFamilyResult(
        family="ngwmn-views",
        status="completed" if count else "no-op",
        applicable_source_rows=count,
    )


def run_scoped_transfer(options: ScopedTransferOptions) -> ScopedTransferResult:
    runtime = ScopedTransferRuntime(options)

    with _suppress_transfer_noise():
        plan_results: list[ScopedFamilyResult] = []
        matched_pointids: set[str] = set()
        for family_name in runtime.selected_family_names:
            spec = runtime.registry[family_name]
            result = spec.planner(runtime)
            result.family = family_name
            result.added_as_prerequisite = family_name in runtime.added_prerequisites
            plan_results.append(result)

            if result.applicable_source_rows:
                if family_name in _THING_SITE_TYPE_SPECS:
                    site_type, _thing_type = _THING_SITE_TYPE_SPECS[family_name]
                    location_df = read_csv("Location")
                    location_df = replace_nans(location_df)
                    location_df = location_df[location_df["SiteType"] == site_type]
                    location_df = _filter_requested_pointids(
                        location_df, runtime.options.pointids
                    )
                    matched_pointids.update(
                        location_df["PointID"]
                        .astype(str)
                        .str.strip()
                        .str.upper()
                        .tolist()
                    )
                elif family_name == "wells":
                    well_df = read_csv("WellData", dtype={"OSEWelltagID": str})
                    well_df = replace_nans(well_df)
                    well_df = _filter_requested_pointids(
                        well_df, runtime.options.pointids
                    )
                    matched_pointids.update(
                        well_df["PointID"].astype(str).str.strip().str.upper().tolist()
                    )
                else:
                    matched_pointids.update(runtime.options.pointids)

        missing = sorted(set(runtime.options.pointids) - matched_pointids)
        if missing:
            return ScopedTransferResult(
                pointids=runtime.options.pointids,
                selected_families=runtime.selected_family_names,
                added_prerequisites=runtime.added_prerequisites,
                dry_run=runtime.options.dry_run,
                family_results=plan_results,
                validation_errors=[
                    "Requested PointIDs not found in applicable source data: "
                    + ", ".join(missing)
                ],
                exit_code=1,
            )

        if runtime.options.dry_run:
            return ScopedTransferResult(
                pointids=runtime.options.pointids,
                selected_families=runtime.selected_family_names,
                added_prerequisites=runtime.added_prerequisites,
                dry_run=True,
                family_results=plan_results,
                validation_errors=[],
                exit_code=0,
            )

        executed_results: list[ScopedFamilyResult] = []
        try:
            for family_name in runtime.selected_family_names:
                spec = runtime.registry[family_name]
                result = spec.executor(runtime)
                result.family = family_name
                result.added_as_prerequisite = (
                    family_name in runtime.added_prerequisites
                )
                executed_results.append(result)
        except Exception as exc:
            return ScopedTransferResult(
                pointids=runtime.options.pointids,
                selected_families=runtime.selected_family_names,
                added_prerequisites=runtime.added_prerequisites,
                dry_run=False,
                family_results=executed_results,
                validation_errors=[],
                execution_error=str(exc),
                exit_code=1,
            )

        return ScopedTransferResult(
            pointids=runtime.options.pointids,
            selected_families=runtime.selected_family_names,
            added_prerequisites=runtime.added_prerequisites,
            dry_run=False,
            family_results=executed_results,
            validation_errors=[],
            exit_code=0,
        )


def format_scoped_transfer_json(result: ScopedTransferResult) -> str:
    return json.dumps(result.to_payload(), indent=2, default=str)
