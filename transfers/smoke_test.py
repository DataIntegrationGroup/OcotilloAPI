from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, select

from core.enums import Organization
from db import (
    Address,
    Contact,
    Deployment,
    Email,
    IncompleteNMAPhone,
    Observation,
    Phone,
    Sensor,
    Thing,
    ThingContactAssociation,
    WellScreen,
)
from db.engine import session_ctx
from db.field import FieldActivity, FieldEvent
from db.sample import Sample
from transfers.contact_transfer import _select_ownerkey_col
from transfers.sensor_transfer import EQUIPMENT_TO_SENSOR_TYPE_MAP
from transfers.util import (
    SensorParameterEstimator,
    filter_by_valid_measuring_agency,
    get_transfers_data_path,
    get_transferable_wells,
    read_csv,
    replace_nans,
)


class SmokePopulation(str, Enum):
    all = "all"
    agreed = "agreed"


class EntityStatus(str, Enum):
    present_in_both = "PRESENT_IN_BOTH"
    absent_in_both = "ABSENT_IN_BOTH"
    missing_in_destination = "MISSING_IN_DESTINATION"
    extra_in_destination = "EXTRA_IN_DESTINATION"


class ValueStatus(str, Enum):
    match = "MATCH"
    missing_in_destination = "MISSING_IN_DESTINATION"
    extra_in_destination = "EXTRA_IN_DESTINATION"
    both_missing_and_extra = "BOTH_MISSING_AND_EXTRA"
    not_applicable = "NOT_APPLICABLE"


@dataclass
class SmokeResult:
    pointid: str
    entity: str
    source_count: int
    destination_count: int
    status: EntityStatus
    value_status: ValueStatus
    missing_value_sample: list[str]
    extra_value_sample: list[str]

    @property
    def passed(self) -> bool:
        return self.status in {
            EntityStatus.present_in_both,
            EntityStatus.absent_in_both,
        }


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def _has_text(value: Any) -> bool:
    return bool(_normalize_text(value))


def _looks_like_phone(value: Any) -> bool:
    text = _normalize_text(value)
    if not text or "@" in text:
        return False
    if not re.fullmatch(r"[\d\s().+\-]+", text):
        return False
    digits = re.sub(r"\D", "", text)
    return len(digits) >= 7


def _normalize_email(raw: Any) -> str:
    text = _normalize_text(raw)
    if not text:
        return ""
    text = re.sub(r"^\s*email\s*:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[.,;:]+$", "", text)
    return text.strip()


def _normalize_number(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    try:
        return f"{float(text):.6f}"
    except ValueError:
        return text.lower()


def _normalize_contact_name(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    # Transfer may preserve errant multiple spaces from source; compare normalized.
    return re.sub(r"\s+", " ", text).strip().lower()


def _normalize_phone(raw: Any) -> str:
    text = _normalize_text(raw)
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    # Treat US country-code-prefixed values as equivalent (1XXXXXXXXXX == XXXXXXXXXX).
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def _parse_legacy_datetime_date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value).strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text, format="%Y-%m-%d %H:%M:%S.%f").date().isoformat()
    except (TypeError, ValueError):
        return None


def _normalize_date_like(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.date().isoformat()


def _load_owner_org_mapper() -> dict[str, str]:
    try:
        mapper_path = get_transfers_data_path("owners_organization_mapper.json")
        with open(mapper_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_ownerkey_mapper() -> dict[str, str]:
    try:
        mapper_path = get_transfers_data_path("owners_ownerkey_mapper.json")
        with open(mapper_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_source_organization(raw_company: Any, mapper: dict[str, str]) -> str:
    company = _normalize_text(raw_company)
    if not company:
        return ""
    organization = mapper.get(company, company)
    try:
        Organization(organization)
    except ValueError:
        return ""
    return _normalize_text(organization)


def _load_well_population(population: SmokePopulation) -> pd.DataFrame:
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    ldf = read_csv("Location")
    ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1, errors="ignore")
    df = wdf.join(ldf.set_index("LocationId"), on="LocationId")
    df = df[df["SiteType"] == "GW"]
    df = df[df["Easting"].notna() & df["Northing"].notna()]
    df = replace_nans(df)

    if population == SmokePopulation.agreed:
        df = get_transferable_wells(df)

        # Match current WellTransferer duplicate handling (skip every duplicate PointID).
        dupes = df["PointID"].duplicated(keep=False)
        if dupes.any():
            dup_ids = set(df.loc[dupes, "PointID"])
            df = df[~df["PointID"].isin(dup_ids)]

    return df


def _sample_pointids(
    df: pd.DataFrame, sample_size: int, seed: int, all_wells: bool = False
) -> list[str]:
    pointids = sorted(
        {_normalize_text(v) for v in df["PointID"].tolist() if _has_text(v)}
    )
    if not pointids:
        return []
    if all_wells:
        return pointids

    n = min(sample_size, len(pointids))
    rng = random.Random(seed)
    return sorted(rng.sample(pointids, n))


def _count_by_pointid(
    df: pd.DataFrame, pointid_col: str, pointids: list[str]
) -> dict[str, int]:
    if df.empty or pointid_col not in df.columns:
        return {pid: 0 for pid in pointids}
    sub = df[df[pointid_col].isin(pointids)]
    if sub.empty:
        return {pid: 0 for pid in pointids}

    counts = sub.groupby(pointid_col).size().to_dict()
    return {pid: int(counts.get(pid, 0)) for pid in pointids}


def _source_entity_counts(
    pointids: list[str], well_df: pd.DataFrame
) -> dict[str, dict[str, int]]:
    counts = {
        "thing": _count_by_pointid(well_df, "PointID", pointids),
    }

    ws = replace_nans(read_csv("WellScreens"))
    counts["wellscreens"] = _count_by_pointid(ws, "PointID", pointids)

    wl = replace_nans(read_csv("WaterLevels"))
    wl = filter_by_valid_measuring_agency(wl)
    counts["waterlevel_observations"] = _count_by_pointid(wl, "PointID", pointids)

    eq = read_csv("Equipment")
    eq.columns = eq.columns.str.replace(" ", "_")
    if "SerialNo" in eq.columns:
        eq = eq[eq["SerialNo"].notna()]
    else:
        eq = eq.iloc[0:0]
    eq = replace_nans(eq)
    counts["deployments"] = _count_by_pointid(eq, "PointID", pointids)

    # Owners/contact graph counts.
    odf = read_csv("OwnersData")
    odf = odf.drop(["OBJECTID", "GlobalID"], axis=1, errors="ignore")

    ldf = read_csv("OwnerLink")
    ldf = ldf.drop(["OBJECTID", "GlobalID"], axis=1, errors="ignore")
    locdf = read_csv("Location")
    ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

    owner_key_col = _select_ownerkey_col(odf, "OwnersData")
    link_owner_key_col = _select_ownerkey_col(ldf, "OwnerLink")

    odf["ownerkey_norm"] = (
        odf[owner_key_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .replace({"": pd.NA})
    )
    ldf["ownerkey_norm"] = (
        ldf[link_owner_key_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .replace({"": pd.NA})
    )

    ldf_join = ldf.set_index("ownerkey_norm")[["PointID"]]
    owners = odf.join(ldf_join, on="ownerkey_norm")
    owners = replace_nans(owners)
    owners = owners[owners["PointID"].isin(pointids)]

    contact_counts = defaultdict(int)
    phone_counts = defaultdict(int)
    email_counts = defaultdict(int)
    address_counts = defaultdict(int)

    for row in owners.itertuples(index=False):
        pid = _normalize_text(getattr(row, "PointID", None))
        if not pid:
            continue

        contact_counts[pid] += 1

        primary_phone = getattr(row, "Phone", None)
        cell_phone = getattr(row, "CellPhone", None)
        secondary_phone = getattr(row, "SecondCtctPhone", None)
        for phone_value in (primary_phone, cell_phone, secondary_phone):
            if _has_text(phone_value):
                phone_counts[pid] += 1

        for email_value in (
            getattr(row, "Email", None),
            getattr(row, "SecondCtctEmail", None),
        ):
            normalized = _normalize_email(email_value)
            if not normalized:
                continue
            if _looks_like_phone(normalized):
                phone_counts[pid] += 1
            else:
                email_counts[pid] += 1

        if _has_text(getattr(row, "MailingAddress", None)):
            address_counts[pid] += 1
        if _has_text(getattr(row, "PhysicalAddress", None)):
            address_counts[pid] += 1

    counts["contacts"] = {pid: int(contact_counts.get(pid, 0)) for pid in pointids}
    counts["contact_phones"] = {pid: int(phone_counts.get(pid, 0)) for pid in pointids}
    counts["contact_emails"] = {pid: int(email_counts.get(pid, 0)) for pid in pointids}
    counts["contact_addresses"] = {
        pid: int(address_counts.get(pid, 0)) for pid in pointids
    }

    return counts


def _blank_signature_map(pointids: list[str]) -> dict[str, set[str]]:
    return {pid: set() for pid in pointids}


def _source_entity_signatures(
    pointids: list[str], well_df: pd.DataFrame
) -> dict[str, dict[str, set[str]]]:
    owner_org_mapper = _load_owner_org_mapper()
    ownerkey_mapper = _load_ownerkey_mapper()
    signatures = {
        "thing": _blank_signature_map(pointids),
        "wellscreens": _blank_signature_map(pointids),
        "contacts": _blank_signature_map(pointids),
        "contact_phones": _blank_signature_map(pointids),
        "contact_emails": _blank_signature_map(pointids),
        "contact_addresses": _blank_signature_map(pointids),
        "waterlevel_observations": _blank_signature_map(pointids),
        "deployments": _blank_signature_map(pointids),
    }

    # Well core fields from WellData.
    for row in well_df[well_df["PointID"].isin(pointids)].itertuples(index=False):
        pid = _normalize_text(getattr(row, "PointID", None))
        if not pid:
            continue
        sig = "|".join(
            [
                _normalize_number(getattr(row, "WellDepth", None)),
                _normalize_number(getattr(row, "HoleDepth", None)),
                _normalize_text(getattr(row, "FormationZone", None)).upper(),
            ]
        )
        signatures["thing"][pid].add(sig)

    # Well screens.
    ws = replace_nans(read_csv("WellScreens"))
    ws = ws[ws["PointID"].isin(pointids)]
    for row in ws.itertuples(index=False):
        pid = _normalize_text(getattr(row, "PointID", None))
        if not pid:
            continue
        top = getattr(row, "ScreenTop", None)
        bottom = getattr(row, "ScreenBottom", None)
        stype = getattr(row, "ScreenType", None)
        sig = "|".join(
            [
                _normalize_number(top),
                _normalize_number(bottom),
                _normalize_text(stype).lower(),
            ]
        )
        signatures["wellscreens"][pid].add(sig)

    # Deployments from Equipment.
    eq = read_csv("Equipment")
    eq.columns = eq.columns.str.replace(" ", "_")
    if "SerialNo" in eq.columns:
        eq = eq[eq["SerialNo"].notna()]
    else:
        eq = eq.iloc[0:0]
    eq = replace_nans(eq)
    eq = eq[eq["PointID"].isin(pointids)]
    estimators: dict[str, SensorParameterEstimator] = {}
    for row in eq.itertuples(index=False):
        pid = _normalize_text(getattr(row, "PointID", None))
        if not pid:
            continue
        installed = _parse_legacy_datetime_date(getattr(row, "DateInstalled", None))
        if installed is None:
            equipment_type = getattr(row, "EquipmentType", None)
            sensor_type = EQUIPMENT_TO_SENSOR_TYPE_MAP.get(equipment_type)
            if sensor_type:
                estimator = estimators.get(sensor_type)
                if estimator is None:
                    estimator = SensorParameterEstimator(sensor_type)
                    estimators[sensor_type] = estimator
                installed = _normalize_date_like(
                    estimator.estimate_installation_date(row)
                )
            else:
                installed = ""
        removed = _parse_legacy_datetime_date(getattr(row, "DateRemoved", None)) or ""
        sig = "|".join(
            [
                _normalize_text(getattr(row, "SerialNo", None)).lower(),
                installed,
                removed,
            ]
        )
        signatures["deployments"][pid].add(sig)

    # Owners/contact graph signatures.
    odf = read_csv("OwnersData")
    odf = odf.drop(["OBJECTID", "GlobalID"], axis=1, errors="ignore")
    ldf = read_csv("OwnerLink")
    ldf = ldf.drop(["OBJECTID", "GlobalID"], axis=1, errors="ignore")
    locdf = read_csv("Location")
    ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

    owner_key_col = _select_ownerkey_col(odf, "OwnersData")
    link_owner_key_col = _select_ownerkey_col(ldf, "OwnerLink")
    odf["ownerkey_canonical"] = odf[owner_key_col].replace(ownerkey_mapper)
    ldf["ownerkey_canonical"] = ldf[link_owner_key_col].replace(ownerkey_mapper)
    odf["ownerkey_norm"] = (
        odf["ownerkey_canonical"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .replace({"": pd.NA})
    )
    ldf["ownerkey_norm"] = (
        ldf["ownerkey_canonical"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .replace({"": pd.NA})
    )
    owners = replace_nans(
        odf.join(ldf.set_index("ownerkey_norm")[["PointID"]], on="ownerkey_norm")
    )
    owners = owners[owners["PointID"].notna()]
    owners = owners.sort_values(by=["PointID"])

    ContactIdentity = tuple[str | None, str | None, str]
    contact_by_owner_type: dict[tuple[str, str], int] = {}
    contact_by_name_org: dict[tuple[str | None, str | None], int] = {}
    contact_store: dict[int, dict[str, Any]] = {}
    pid_to_contact_ids: dict[str, set[int]] = defaultdict(set)
    next_contact_id = 1

    def _make_name(first: Any, last: Any) -> str | None:
        f = _normalize_text(first)
        l = _normalize_text(last)
        if not f and not l:
            return None
        if f and not l:
            return f
        if not f and l:
            return l
        return f"{f} {l}"

    def _safe_make_name(
        first: Any,
        last: Any,
        owner_key: str | None,
        organization: str | None,
        fallback_suffix: str | None,
    ) -> str | None:
        name = _make_name(first, last)
        if name is None and not organization:
            fallback = _normalize_text(owner_key) or None
            if fallback and fallback_suffix:
                fallback = f"{fallback}-{fallback_suffix}"
            return fallback
        return name

    def _resolve_contact(
        owner_key: str | None,
        contact_type: str,
        name: str | None,
        organization: str | None,
    ) -> tuple[int | None, bool]:
        nonlocal next_contact_id
        key_owner = (
            (_normalize_text(owner_key), contact_type)
            if _normalize_text(owner_key)
            else None
        )
        key_name_org = (name, organization)
        allow_name_org_fallback = (not _normalize_text(owner_key)) or bool(organization)

        if key_owner and key_owner in contact_by_owner_type:
            return contact_by_owner_type[key_owner], False

        if allow_name_org_fallback and key_name_org in contact_by_name_org:
            contact_id = contact_by_name_org[key_name_org]
            if key_owner:
                contact_by_owner_type[key_owner] = contact_id
            return contact_id, False

        if not name and not organization:
            return None, False

        contact_id = next_contact_id
        next_contact_id += 1
        contact_store[contact_id] = {
            "name": name,
            "organization": organization,
            "contact_type": contact_type,
            "phones": set(),
            "emails": set(),
            "addresses": set(),
        }
        contact_by_name_org[key_name_org] = contact_id
        if key_owner:
            contact_by_owner_type[key_owner] = contact_id
        return contact_id, True

    for row in owners.itertuples(index=False):
        pid = _normalize_text(getattr(row, "PointID", None))
        if not pid:
            continue

        owner_key = _normalize_text(getattr(row, "OwnerKey", None)) or None
        has_secondary_info = any(
            _has_text(getattr(row, field, None))
            for field in (
                "SecondFirstName",
                "SecondLastName",
                "SecondCtctEmail",
                "SecondCtctPhone",
            )
        )
        company = _normalize_source_organization(
            getattr(row, "Company", None), owner_org_mapper
        )
        company = company or None

        primary_name = _safe_make_name(
            getattr(row, "FirstName", None),
            getattr(row, "LastName", None),
            owner_key,
            company,
            "primary",
        )
        primary_contact, primary_new = _resolve_contact(
            owner_key, "Primary", primary_name, company
        )
        if primary_contact:
            pid_to_contact_ids[pid].add(primary_contact)
        if primary_contact:
            c = contact_store[primary_contact]
            for phone_value in (
                getattr(row, "Phone", None),
                getattr(row, "CellPhone", None),
            ):
                pn = _normalize_phone(phone_value)
                if pn:
                    c["phones"].add(pn)

            em = _normalize_email(getattr(row, "Email", None)).lower()
            if em:
                if _looks_like_phone(em):
                    pn = _normalize_phone(em)
                    if pn:
                        c["phones"].add(pn)
                else:
                    c["emails"].add(em)

            for prefix in ("Mail", "Physical"):
                line1 = _normalize_text(
                    getattr(
                        row,
                        (
                            f"{prefix}ingAddress"
                            if prefix == "Mail"
                            else "PhysicalAddress"
                        ),
                        None,
                    )
                )
                city = _normalize_text(getattr(row, f"{prefix}City", None))
                state = _normalize_text(getattr(row, f"{prefix}State", None))
                zipc = _normalize_text(getattr(row, f"{prefix}ZipCode", None))
                if line1:
                    c["addresses"].add(
                        f"{line1.lower()}|{city.lower()}|{state.lower()}|{zipc.lower()}"
                    )

        if has_secondary_info:
            secondary_name = _safe_make_name(
                getattr(row, "SecondFirstName", None),
                getattr(row, "SecondLastName", None),
                owner_key,
                company,
                "secondary",
            )
            secondary_contact, secondary_new = _resolve_contact(
                owner_key, "Secondary", secondary_name, company
            )
            if secondary_contact:
                pid_to_contact_ids[pid].add(secondary_contact)
            if secondary_contact:
                c = contact_store[secondary_contact]
                pn = _normalize_phone(getattr(row, "SecondCtctPhone", None))
                if pn:
                    c["phones"].add(pn)

                em = _normalize_email(getattr(row, "SecondCtctEmail", None)).lower()
                if em:
                    if _looks_like_phone(em):
                        pn = _normalize_phone(em)
                        if pn:
                            c["phones"].add(pn)
                    else:
                        c["emails"].add(em)

    for pid in pointids:
        for contact_id in pid_to_contact_ids.get(pid, set()):
            c = contact_store.get(contact_id)
            if not c:
                continue
            signatures["contacts"][pid].add(
                f"{_normalize_text(c.get('contact_type')).lower()}|{_normalize_contact_name(c.get('name'))}|{_normalize_text(c.get('organization')).lower()}"
            )
            for pn in c.get("phones", set()):
                signatures["contact_phones"][pid].add(pn)
            for em in c.get("emails", set()):
                signatures["contact_emails"][pid].add(em)
            for addr in c.get("addresses", set()):
                signatures["contact_addresses"][pid].add(addr)

    return signatures


def _rows_to_count_dict(
    rows: list[tuple[str, int]], pointids: list[str]
) -> dict[str, int]:
    lut = {pid: 0 for pid in pointids}
    for pid, n in rows:
        if pid in lut:
            lut[pid] = int(n)
    return lut


def _destination_entity_counts(pointids: list[str]) -> dict[str, dict[str, int]]:
    if not pointids:
        return {
            "thing": {},
            "wellscreens": {},
            "contacts": {},
            "contact_phones": {},
            "contact_emails": {},
            "contact_addresses": {},
            "waterlevel_observations": {},
            "deployments": {},
        }

    with session_ctx() as session:
        thing_rows = session.execute(
            select(Thing.name, func.count(Thing.id))
            .where(Thing.name.in_(pointids))
            .where(Thing.thing_type == "water well")
            .group_by(Thing.name)
        ).all()

        screen_rows = session.execute(
            select(Thing.name, func.count(WellScreen.id))
            .join(WellScreen, WellScreen.thing_id == Thing.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()

        contact_rows = session.execute(
            select(Thing.name, func.count(ThingContactAssociation.id))
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()

        phone_rows = session.execute(
            select(Thing.name, func.count(Phone.id))
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(Phone, Phone.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()
        incomplete_phone_rows = session.execute(
            select(Thing.name, func.count(IncompleteNMAPhone.id))
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(IncompleteNMAPhone, IncompleteNMAPhone.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()

        email_rows = session.execute(
            select(Thing.name, func.count(Email.id))
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(Email, Email.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()

        address_rows = session.execute(
            select(Thing.name, func.count(Address.id))
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(Address, Address.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()

        deployment_rows = session.execute(
            select(Thing.name, func.count(Deployment.id))
            .join(Deployment, Deployment.thing_id == Thing.id)
            .where(Thing.name.in_(pointids))
            .group_by(Thing.name)
        ).all()

        waterlevel_obs_rows = session.execute(
            select(Thing.name, func.count(Observation.id))
            .join(FieldEvent, FieldEvent.thing_id == Thing.id)
            .join(FieldActivity, FieldActivity.field_event_id == FieldEvent.id)
            .join(Sample, Sample.field_activity_id == FieldActivity.id)
            .join(Observation, Observation.sample_id == Sample.id)
            .where(Thing.name.in_(pointids))
            .where(Sample.nma_pk_waterlevels.is_not(None))
            .group_by(Thing.name)
        ).all()

    results = {
        "thing": _rows_to_count_dict(thing_rows, pointids),
        "wellscreens": _rows_to_count_dict(screen_rows, pointids),
        "contacts": _rows_to_count_dict(contact_rows, pointids),
        "contact_phones": _rows_to_count_dict(phone_rows, pointids),
        "contact_emails": _rows_to_count_dict(email_rows, pointids),
        "contact_addresses": _rows_to_count_dict(address_rows, pointids),
        "waterlevel_observations": _rows_to_count_dict(waterlevel_obs_rows, pointids),
        "deployments": _rows_to_count_dict(deployment_rows, pointids),
    }
    incomplete_phone_counts = _rows_to_count_dict(incomplete_phone_rows, pointids)
    for pid in pointids:
        results["contact_phones"][pid] = int(
            results["contact_phones"].get(pid, 0)
        ) + int(incomplete_phone_counts.get(pid, 0))
    return results


def _destination_entity_signatures(
    pointids: list[str],
) -> dict[str, dict[str, set[str]]]:
    signatures = {
        "thing": _blank_signature_map(pointids),
        "wellscreens": _blank_signature_map(pointids),
        "contacts": _blank_signature_map(pointids),
        "contact_phones": _blank_signature_map(pointids),
        "contact_emails": _blank_signature_map(pointids),
        "contact_addresses": _blank_signature_map(pointids),
        "waterlevel_observations": _blank_signature_map(pointids),
        "deployments": _blank_signature_map(pointids),
    }
    if not pointids:
        return signatures

    with session_ctx() as session:
        thing_rows = session.execute(
            select(
                Thing.name, Thing.well_depth, Thing.hole_depth, Thing.nma_formation_zone
            )
            .where(Thing.name.in_(pointids))
            .where(Thing.thing_type == "water well")
        ).all()
        for pid, wd, hd, fz in thing_rows:
            signatures["thing"][pid].add(
                "|".join(
                    [
                        _normalize_number(wd),
                        _normalize_number(hd),
                        _normalize_text(fz).upper(),
                    ]
                )
            )

        ws_rows = session.execute(
            select(
                Thing.name,
                WellScreen.screen_depth_top,
                WellScreen.screen_depth_bottom,
                WellScreen.screen_type,
            )
            .join(WellScreen, WellScreen.thing_id == Thing.id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, top, bottom, stype in ws_rows:
            signatures["wellscreens"][pid].add(
                "|".join(
                    [
                        _normalize_number(top),
                        _normalize_number(bottom),
                        _normalize_text(stype).lower(),
                    ]
                )
            )

        contact_rows = session.execute(
            select(Thing.name, Contact.contact_type, Contact.name, Contact.organization)
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, ctype, name, org in contact_rows:
            signatures["contacts"][pid].add(
                f"{_normalize_text(ctype).lower()}|{_normalize_contact_name(name)}|{_normalize_text(org).lower()}"
            )

        phone_rows = session.execute(
            select(Thing.name, Phone.phone_number)
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(Phone, Phone.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, phone in phone_rows:
            pn = _normalize_phone(phone)
            if pn:
                signatures["contact_phones"][pid].add(pn)
        incomplete_phone_rows = session.execute(
            select(Thing.name, IncompleteNMAPhone.phone_number)
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(IncompleteNMAPhone, IncompleteNMAPhone.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, phone in incomplete_phone_rows:
            pn = _normalize_phone(phone)
            if pn:
                signatures["contact_phones"][pid].add(pn)

        email_rows = session.execute(
            select(Thing.name, Email.email)
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(Email, Email.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, email in email_rows:
            em = _normalize_email(email).lower()
            if em:
                signatures["contact_emails"][pid].add(em)

        address_rows = session.execute(
            select(
                Thing.name,
                Address.address_line_1,
                Address.city,
                Address.state,
                Address.postal_code,
            )
            .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
            .join(Contact, Contact.id == ThingContactAssociation.contact_id)
            .join(Address, Address.contact_id == Contact.id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, line1, city, state, zipc in address_rows:
            if _has_text(line1):
                signatures["contact_addresses"][pid].add(
                    f"{_normalize_text(line1).lower()}|{_normalize_text(city).lower()}|{_normalize_text(state).lower()}|{_normalize_text(zipc).lower()}"
                )

        dep_rows = session.execute(
            select(
                Thing.name,
                Sensor.serial_no,
                Deployment.installation_date,
                Deployment.removal_date,
            )
            .join(Deployment, Deployment.thing_id == Thing.id)
            .join(Sensor, Sensor.id == Deployment.sensor_id)
            .where(Thing.name.in_(pointids))
        ).all()
        for pid, sensor_serial, installed, removed in dep_rows:
            signatures["deployments"][pid].add(
                "|".join(
                    [
                        _normalize_text(sensor_serial).lower(),
                        _normalize_text(installed)[:10],
                        _normalize_text(removed)[:10],
                    ]
                )
            )

    return signatures


def _status(source_count: int, destination_count: int) -> EntityStatus:
    src = source_count > 0
    dst = destination_count > 0
    if src and dst:
        return EntityStatus.present_in_both
    if (not src) and (not dst):
        return EntityStatus.absent_in_both
    if src and (not dst):
        return EntityStatus.missing_in_destination
    return EntityStatus.extra_in_destination


def _value_status(
    source_values: set[str], destination_values: set[str], compare_enabled: bool
) -> tuple[ValueStatus, list[str], list[str]]:
    if not compare_enabled:
        return ValueStatus.not_applicable, [], []

    missing = sorted(source_values - destination_values)
    extra = sorted(destination_values - source_values)
    if not missing and not extra:
        return ValueStatus.match, [], []
    if missing and extra:
        return ValueStatus.both_missing_and_extra, missing[:5], extra[:5]
    if missing:
        return ValueStatus.missing_in_destination, missing[:5], []
    return ValueStatus.extra_in_destination, [], extra[:5]


def run_well_smoke_test(
    sample_size: int,
    population: SmokePopulation,
    seed: int,
    all_wells: bool = False,
) -> dict[str, Any]:
    well_df = _load_well_population(population)
    pointids = _sample_pointids(
        well_df, sample_size=sample_size, seed=seed, all_wells=all_wells
    )

    if not pointids:
        return {
            "population": population.value,
            "seed": seed,
            "sample_size": sample_size,
            "available_wells": 0,
            "sampled_wells": 0,
            "entity_results": [],
            "mismatch_count": 0,
            "well_fail_count": 0,
        }

    source = _source_entity_counts(pointids, well_df)
    dest = _destination_entity_counts(pointids)
    source_values = _source_entity_signatures(pointids, well_df)
    dest_values = _destination_entity_signatures(pointids)

    entities = [
        "thing",
        "wellscreens",
        "contacts",
        "contact_phones",
        "contact_emails",
        "contact_addresses",
        "waterlevel_observations",
        "deployments",
    ]
    value_compare_entities = {
        "thing",
        "wellscreens",
        "contacts",
        "contact_phones",
        "contact_emails",
        "contact_addresses",
        "deployments",
    }

    results: list[SmokeResult] = []
    for pid in pointids:
        for entity in entities:
            src_values_set = source_values.get(entity, {}).get(pid, set())
            dst_values_set = dest_values.get(entity, {}).get(pid, set())
            src_count = int(source.get(entity, {}).get(pid, 0))
            dst_count = int(dest.get(entity, {}).get(pid, 0))
            # For entities where we compare normalized value sets, use those sets
            # for presence status to avoid false count mismatches from contact reuse.
            if entity in value_compare_entities:
                src_count = len(src_values_set)
                dst_count = len(dst_values_set)
            vstatus, missing_vals, extra_vals = _value_status(
                src_values_set,
                dst_values_set,
                compare_enabled=entity in value_compare_entities,
            )
            results.append(
                SmokeResult(
                    pointid=pid,
                    entity=entity,
                    source_count=src_count,
                    destination_count=dst_count,
                    status=_status(src_count, dst_count),
                    value_status=vstatus,
                    missing_value_sample=missing_vals,
                    extra_value_sample=extra_vals,
                )
            )

    value_mismatches = [
        r
        for r in results
        if r.value_status not in {ValueStatus.match, ValueStatus.not_applicable}
    ]
    mismatches = [r for r in results if not r.passed]
    failed_wells = sorted(
        {r.pointid for r in mismatches} | {r.pointid for r in value_mismatches}
    )

    payload = {
        "population": population.value,
        "seed": seed,
        "sample_size": sample_size,
        "available_wells": int(well_df["PointID"].dropna().nunique()),
        "sampled_wells": len(pointids),
        "mismatch_count": len(mismatches),
        "value_mismatch_count": len(value_mismatches),
        "well_fail_count": len(failed_wells),
        "failed_wells": failed_wells,
        "entity_results": [
            {
                "pointid": r.pointid,
                "entity": r.entity,
                "source_count": r.source_count,
                "destination_count": r.destination_count,
                "status": r.status.value,
                "value_status": r.value_status.value,
                "missing_value_sample": r.missing_value_sample,
                "extra_value_sample": r.extra_value_sample,
                "passed": r.passed,
            }
            for r in results
        ],
    }
    return payload


def write_smoke_outputs(
    payload: dict[str, Any], detail_path: Path, summary_path: Path
) -> None:
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    rows = payload.get("entity_results", [])
    pd.DataFrame(rows).to_csv(detail_path, index=False)

    summary = {k: v for k, v in payload.items() if k not in {"entity_results"}}
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
