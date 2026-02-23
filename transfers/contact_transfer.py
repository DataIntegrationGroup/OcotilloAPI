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
import re

import pandas as pd
from pandas import DataFrame
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.enums import Organization
from db import (
    Contact,
    ThingContactAssociation,
    Email,
    Phone,
    Address,
    IncompleteNMAPhone,
    Base,
    Thing,
)
from transfers.logger import logger
from transfers.transferer import ThingBasedTransferer
from transfers.util import (
    get_transfers_data_path,
)
from transfers.util import read_csv, filter_to_valid_point_ids, replace_nans


def _select_ownerkey_col(df: DataFrame, source_name: str) -> str:
    exact_matches = [col for col in df.columns if col.lower() == "ownerkey"]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise ValueError(
            f"Multiple 'OwnerKey' columns found in {source_name}: {exact_matches}. "
            "Column names differing only by case are ambiguous; please "
            "disambiguate."
        )

    candidates = [col for col in df.columns if col.lower().endswith("ownerkey")]
    if not candidates:
        raise ValueError(
            f"No owner key column found in {source_name}; expected a column named "
            "'OwnerKey' (case-insensitive) or ending with 'OwnerKey'."
        )
    if len(candidates) > 1:
        raise ValueError(
            f"Multiple owner key-like columns found in {source_name}: {candidates}. "
            "Please disambiguate."
        )
    return candidates[0]


class ContactTransfer(ThingBasedTransferer):
    source_table = "OwnersData"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        """
        Developer's note

        - company to organization mapping is stored in transfers/data/owners_organization_mapper.json
        - the key is the value in NM_Aquifer and the value is the standardized organization name used in the lexicon
        """
        co_to_org_mapper_path = get_transfers_data_path(
            "owners_organization_mapper.json"
        )
        with open(co_to_org_mapper_path, "r") as f:
            self._co_to_org_mapper = json.load(f)

        ownerkey_mapper_path = get_transfers_data_path("owners_ownerkey_mapper.json")
        try:
            with open(ownerkey_mapper_path, "r") as f:
                self._ownerkey_mapper = json.load(f)
        except FileNotFoundError:
            logger.warning(
                "Owner key mapper file not found at '%s'; proceeding with empty owner key mapping.",
                ownerkey_mapper_path,
            )
            self._ownerkey_mapper = {}

        self._added: set[tuple[str | None, str | None]] = set()
        self._contact_by_owner_type: dict[tuple[str, str], Contact] = {}
        self._contact_by_name_org: dict[tuple[str | None, str | None], Contact] = {}
        self._commit_step = 500

    def _build_contact_caches(self, session: Session) -> None:
        contacts = session.query(Contact).all()
        owner_type: dict[tuple[str, str], Contact] = {}
        name_org: dict[tuple[str | None, str | None], Contact] = {}
        for contact in contacts:
            if contact.nma_pk_owners and contact.contact_type:
                owner_type[(contact.nma_pk_owners, contact.contact_type)] = contact
            name_org[(contact.name, contact.organization)] = contact
        self._contact_by_owner_type = owner_type
        self._contact_by_name_org = name_org
        logger.info(
            "Built contact caches: owner_type=%s name_org=%s",
            len(self._contact_by_owner_type),
            len(self._contact_by_name_org),
        )

    def calculate_missing_organizations(self):
        input_df, cleaned_df = self._get_dfs()

        for row in replace_nans(input_df).itertuples():
            if not row.Company:
                continue
            try:
                _get_organization(row, self._co_to_org_mapper)
            except ValueError as e:
                logger.critical(f"Invalid Organization {e}")

    def _get_dfs(self):
        input_df = read_csv(self.source_table)
        odf = input_df.drop(["OBJECTID", "GlobalID"], axis=1)
        ldf = read_csv("OwnerLink")
        ldf = ldf.drop(["OBJECTID", "GlobalID"], axis=1)
        locdf = read_csv("Location")
        ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

        owner_key_col = _select_ownerkey_col(odf, "OwnersData")
        link_owner_key_col = _select_ownerkey_col(ldf, "OwnerLink")

        if self._ownerkey_mapper:
            odf["ownerkey_canonical"] = odf[owner_key_col].replace(
                self._ownerkey_mapper
            )
            ldf["ownerkey_canonical"] = ldf[link_owner_key_col].replace(
                self._ownerkey_mapper
            )
        else:
            odf["ownerkey_canonical"] = odf[owner_key_col]
            ldf["ownerkey_canonical"] = ldf[link_owner_key_col]

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

        collisions = (
            ldf.groupby("ownerkey_norm")["ownerkey_canonical"]
            .nunique(dropna=True)
            .loc[lambda s: s > 1]
        )
        if not collisions.empty:
            examples = []
            for key in collisions.index[:10]:
                variants = (
                    ldf.loc[ldf["ownerkey_norm"] == key, "ownerkey_canonical"]
                    .dropna()
                    .unique()
                    .tolist()
                )
                examples.append(f"{key} -> {sorted(variants)}")
            logger.critical(
                "OwnerKey normalization collision(s) detected in OwnerLink. "
                "Resolve these before proceeding. Examples: %s",
                "; ".join(examples),
            )
            raise ValueError(
                "OwnerKey normalization collisions detected in OwnerLink. "
                "Fix source data or update owners_ownerkey_mapper.json."
            )

        ldf_join = ldf.set_index("ownerkey_norm")
        overlap_cols = [col for col in ldf_join.columns if col in odf.columns]
        if overlap_cols:
            ldf_join = ldf_join.drop(columns=overlap_cols, errors="ignore")
        odf = odf.join(ldf_join, on="ownerkey_norm")

        odf = replace_nans(odf)

        odf = filter_to_valid_point_ids(odf, self.pointids)
        return input_df, odf

    def _get_prepped_group(self, group) -> DataFrame:
        return group.sort_values(by=["PointID"])

    def _transfer_hook(self, session: Session):
        self._build_contact_caches(session)

        groups = self._get_group()
        pointids = [
            idx[0] if isinstance(idx, tuple) else idx for idx in groups.groups.keys()
        ]
        things = session.query(Thing).filter(Thing.name.in_(pointids)).all()
        thing_by_name = {thing.name: thing for thing in things}
        logger.info(
            "Prepared ContactTransfer caches: %s grouped PointIDs, %s matching Things",
            len(pointids),
            len(thing_by_name),
        )

        processed_groups = 0
        for index, group in groups:
            pointid = index[0] if isinstance(index, tuple) else index
            db_item = thing_by_name.get(pointid)
            if db_item is None:
                logger.warning(f"Thing with PointID {pointid} not found in database.")
                continue

            prepped_group = self._get_prepped_group(group)
            for row in prepped_group.itertuples():
                try:
                    self._group_step(session, row, db_item)
                except Exception as e:
                    logger.critical(
                        f"Could not add contact(s) for PointID {pointid}: {e}"
                    )
                    self._capture_error(pointid, str(e), "UnknownField")

            processed_groups += 1
            if processed_groups % self._commit_step == 0:
                session.commit()
                logger.info(
                    "Committed ContactTransfer progress: %s groups processed",
                    processed_groups,
                )

    def _group_step(self, session: Session, row: pd.Series, db_item: Base):
        organization = _get_organization(row, self._co_to_org_mapper)
        for adder, tag in (_add_first_contact, "first"), (
            _add_second_contact,
            "second",
        ):
            try:
                contact = adder(
                    session,
                    row,
                    db_item,
                    organization,
                    self._added,
                    self._contact_by_owner_type,
                    self._contact_by_name_org,
                )
                if contact is not None:
                    session.flush([contact])
                if (
                    tag == "first"
                    and contact
                    and pd.notna(row.OwnerComment)
                    and isinstance(row.OwnerComment, str)
                    and row.OwnerComment.strip()
                ):
                    note = contact.add_note(row.OwnerComment, "OwnerComment")
                    session.add(note)
                logger.info(f"added {tag} contact for PointID {row.PointID}")
            except ValidationError as e:
                logger.critical(
                    f"Skipping {tag} contact for PointID {row.PointID} due to validation error: {e.errors()}"
                )
                self._capture_validation_error(row.PointID, e)
            except Exception as e:
                logger.critical(
                    f"Skipping {tag} contact for PointID {row.PointID} due to error: {e}"
                )
                session.rollback()
                self._capture_error(row.PointID, str(e), "UnknownError")


def _add_first_contact(
    session: Session,
    row: pd.Series,
    thing: Thing,
    organization: str,
    added: set[tuple[str | None, str | None]],
    contact_by_owner_type: dict[tuple[str, str], Contact],
    contact_by_name_org: dict[tuple[str | None, str | None], Contact],
) -> Contact | None:
    # TODO: extract role from OwnerComment
    # role = extract_owner_role(row.OwnerComment)
    role = "Owner"
    release_status = "private"

    name = _safe_make_name(
        row.FirstName,
        row.LastName,
        row.OwnerKey,
        organization,
        fallback_suffix="primary",
    )

    contact_data = {
        "thing_id": thing.id,
        "release_status": release_status,
        "name": name,
        "role": role,
        "contact_type": "Primary",
        "organization": organization,
        "nma_pk_owners": row.OwnerKey,
        "addresses": [],
        "emails": [],
        "phones": [],
    }

    contact, new = _make_contact_and_assoc(
        session,
        contact_data,
        thing,
        added,
        contact_by_owner_type,
        contact_by_name_org,
    )

    if row.Email:
        raw_email = str(row.Email).strip()
        if _looks_like_phone_in_email_field(raw_email):
            logger.warning(
                "first '%s' Email field looked like a phone number; storing as phone instead.",
                row.OwnerKey,
            )
            phone, complete = _make_phone(
                "first",
                row.OwnerKey,
                phone_number=raw_email,
                phone_type="Primary",
                release_status=release_status,
            )
            if phone:
                if complete:
                    _append_phone_if_missing(contact, phone)
                else:
                    _append_incomplete_phone_if_missing(contact, phone)
        else:
            email = _make_email(
                "first",
                row.OwnerKey,
                email=raw_email,
                email_type="Primary",
                release_status=release_status,
            )
            if email:
                _append_email_if_missing(contact, email)

    if row.Phone:
        phone, complete = _make_phone(
            "first",
            row.OwnerKey,
            phone_number=row.Phone,
            phone_type="Primary",
            release_status=release_status,
        )
        if phone:
            if complete:
                _append_phone_if_missing(contact, phone)
            else:
                _append_incomplete_phone_if_missing(contact, phone)

    if row.CellPhone:
        phone, complete = _make_phone(
            "first",
            row.OwnerKey,
            phone_number=row.CellPhone,
            phone_type="Mobile",
            release_status=release_status,
        )
        if phone:
            if complete:
                _append_phone_if_missing(contact, phone)
            else:
                _append_incomplete_phone_if_missing(contact, phone)

    if row.MailingAddress:
        address = _make_address(
            "first",
            row.OwnerKey,
            "mailing",
            address_line_1=row.MailingAddress,
            city=row.MailCity,
            state=row.MailState,
            postal_code=row.MailZipCode,
            address_type="Mailing",
            release_status=release_status,
        )
        if address:
            _append_address_if_missing(contact, address)

    if row.PhysicalAddress:
        address = _make_address(
            "first",
            row.OwnerKey,
            "physical",
            address_line_1=row.PhysicalAddress,
            city=row.PhysicalCity,
            state=row.PhysicalState,
            postal_code=row.PhysicalZipCode,
            address_type="Physical",
            release_status=release_status,
        )
        if address:
            _append_address_if_missing(contact, address)

    return contact if new else None


def _safe_make_name(
    first: str | None,
    last: str | None,
    ownerkey: str,
    organization: str | None,
    fallback_suffix: str | None = None,
) -> str | None:
    name = _make_name(first, last)
    if name is None and organization is None:
        fallback = str(ownerkey) if ownerkey is not None else None
        if fallback and fallback_suffix:
            fallback = f"{fallback}-{fallback_suffix}"
        logger.warning(
            f"Missing both first and last name and organization for OwnerKey {ownerkey}; "
            f"using OwnerKey fallback name '{fallback}'."
        )
        return fallback
    return name


def _add_second_contact(
    session: Session,
    row: pd.Series,
    thing: Thing,
    organization: str,
    added: set[tuple[str | None, str | None]],
    contact_by_owner_type: dict[tuple[str, str], Contact],
    contact_by_name_org: dict[tuple[str | None, str | None], Contact],
) -> Contact | None:
    if all(
        [
            getattr(row, f"Second{f}") is None
            for f in ["FirstName", "LastName", "CtctEmail", "CtctPhone"]
        ]
    ):
        logger.warning(f"No second contact info for PointID {row.PointID}, skipping.")
        return

    release_status = "private"
    name = _safe_make_name(
        row.SecondFirstName,
        row.SecondLastName,
        row.OwnerKey,
        organization,
        fallback_suffix="secondary",
    )

    contact_data = {
        "thing_id": thing.id,
        "release_status": release_status,
        "name": name,
        "role": "Owner",
        "contact_type": "Secondary",
        "organization": organization,
        "nma_pk_owners": row.OwnerKey,
        "addresses": [],
        "emails": [],
        "phones": [],
    }

    contact, new = _make_contact_and_assoc(
        session,
        contact_data,
        thing,
        added,
        contact_by_owner_type,
        contact_by_name_org,
    )
    if row.SecondCtctEmail:
        raw_email = str(row.SecondCtctEmail).strip()
        if _looks_like_phone_in_email_field(raw_email):
            logger.warning(
                "second '%s' Email field looked like a phone number; storing as phone instead.",
                row.OwnerKey,
            )
            phone, complete = _make_phone(
                "second",
                row.OwnerKey,
                phone_number=raw_email,
                phone_type="Primary",
                release_status=release_status,
            )
            if phone:
                if complete:
                    _append_phone_if_missing(contact, phone)
                else:
                    _append_incomplete_phone_if_missing(contact, phone)
        else:
            email = _make_email(
                "second",
                row.OwnerKey,
                email=raw_email,
                email_type="Primary",
                release_status=release_status,
            )
            if email:
                _append_email_if_missing(contact, email)

    if row.SecondCtctPhone:
        phone, complete = _make_phone(
            "second",
            row.OwnerKey,
            phone_number=row.SecondCtctPhone,
            phone_type="Primary",
            release_status=release_status,
        )
        if phone:
            if complete:
                _append_phone_if_missing(contact, phone)
            else:
                _append_incomplete_phone_if_missing(contact, phone)

    return contact if new else None


# helpers
def _get_organization(row, co_to_org_mapper):
    organization = co_to_org_mapper.get(row.Company, row.Company)

    # use Organization enum to catch validation errors
    try:
        Organization(organization)
    except ValueError:
        return None

    return organization


def _make_name(first: str | None, last: str | None) -> str | None:
    if first is None and last is None:
        return None
    elif first is not None and last is None:
        return first
    elif first is None and last is not None:
        return last
    else:
        return f"{first} {last}"


def _make_email(first_second: str, ownerkey: str, **kw) -> Email | None:
    from schemas.contact import CreateEmail

    try:
        if "email" in kw:
            email = kw["email"].strip()
            # Normalize legacy values like "Email: user@example.com"
            email = re.sub(r"^\s*email\s*:\s*", "", email, flags=re.IGNORECASE)
            # Normalize trailing punctuation from data-entry notes (e.g., "user@aol.com.")
            email = re.sub(r"[.,;:]+$", "", email)
            kw["email"] = email

        email = CreateEmail(**kw)
        return Email(**email.model_dump())
    except ValidationError as e:
        logger.critical(
            f"{first_second} '{ownerkey}' Skipping email. Validation error: {e.errors()}"
        )


def _looks_like_phone_in_email_field(value: str | None) -> bool:
    if not value:
        return False

    text = value.strip()
    if "@" in text:
        return False

    # Accept common phone formatting chars, require enough digits to be a phone number.
    if not re.fullmatch(r"[\d\s().+\-]+", text):
        return False
    digits = re.sub(r"\D", "", text)
    return len(digits) >= 7


def _make_phone(first_second: str, ownerkey: str, **kw) -> tuple[Phone | None, bool]:
    from schemas.contact import CreatePhone

    try:
        if "phone_number" in kw:
            kw["phone_number"] = kw["phone_number"].strip()

        phone = CreatePhone(**kw)
        return Phone(**phone.model_dump()), True
    except ValidationError as e:
        try:
            if "phone_number" in kw:
                incomplete_phone = IncompleteNMAPhone(phone_number=kw["phone_number"])
                logger.info(f"Salvaged incomplete phone number for OwnerKey {ownerkey}")
                return incomplete_phone, False
        except ValidationError:

            logger.critical(
                f"{first_second} '{ownerkey}' Skipping phone . Validation error: {e.errors()}"
            )


def _make_address(first_second: str, ownerkey: str, kind: str, **kw) -> Address | None:
    from schemas.contact import CreateAddress

    try:
        address = CreateAddress(**kw)
        return Address(**address.model_dump())
    except ValidationError as e:
        logger.warning(
            f"{first_second} '{ownerkey}' Skipping {kind} address. Validation error: {e.errors()}"
        )


def _norm_text(value) -> str:
    return str(value).strip().casefold() if value is not None else ""


def _phone_digits(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def _append_email_if_missing(contact: Contact, email: Email) -> None:
    new_key = (_norm_text(email.email), _norm_text(email.email_type))
    existing = {
        (_norm_text(e.email), _norm_text(e.email_type)) for e in (contact.emails or [])
    }
    if new_key not in existing:
        contact.emails.append(email)


def _append_phone_if_missing(contact: Contact, phone: Phone) -> None:
    new_key = (_phone_digits(phone.phone_number), _norm_text(phone.phone_type))
    existing = {
        (_phone_digits(p.phone_number), _norm_text(p.phone_type))
        for p in (contact.phones or [])
    }
    if new_key not in existing:
        contact.phones.append(phone)


def _append_incomplete_phone_if_missing(
    contact: Contact, phone: IncompleteNMAPhone
) -> None:
    new_key = _phone_digits(phone.phone_number)
    existing = {
        _phone_digits(p.phone_number) for p in (contact.incomplete_nma_phones or [])
    }
    if new_key not in existing:
        contact.incomplete_nma_phones.append(phone)


def _append_address_if_missing(contact: Contact, address: Address) -> None:
    new_key = (
        _norm_text(address.address_line_1),
        _norm_text(address.city),
        _norm_text(address.state),
        _norm_text(address.postal_code),
        _norm_text(address.address_type),
    )
    existing = {
        (
            _norm_text(a.address_line_1),
            _norm_text(a.city),
            _norm_text(a.state),
            _norm_text(a.postal_code),
            _norm_text(a.address_type),
        )
        for a in (contact.addresses or [])
    }
    if new_key not in existing:
        contact.addresses.append(address)


def _make_contact_and_assoc(
    session: Session,
    data: dict,
    thing: Thing,
    added: set[tuple[str | None, str | None]],
    contact_by_owner_type: dict[tuple[str, str], Contact],
    contact_by_name_org: dict[tuple[str | None, str | None], Contact],
) -> tuple[Contact, bool]:
    new_contact = True
    contact = None

    owner_key = data.get("nma_pk_owners")
    contact_type = data.get("contact_type")
    organization = data.get("organization")
    # Prefer owner-key/type identity. Allow name/org reuse when organization is
    # present (stable identity) or when owner key is unavailable.
    allow_name_org_fallback = (not bool(owner_key)) or bool(organization)
    if owner_key and contact_type:
        contact = contact_by_owner_type.get((owner_key, contact_type))
        if contact is not None:
            new_contact = False

    name_org_key = (data["name"], data["organization"])
    if contact is None and allow_name_org_fallback:
        contact = contact_by_name_org.get(name_org_key)
        if contact is not None:
            new_contact = False

    if contact is None:
        from schemas.contact import CreateContact

        contact = CreateContact(**data)
        contact_data = contact.model_dump(exclude=["thing_id", "notes"])
        contact = Contact(**contact_data)
        session.add(contact)
        contact_by_name_org[name_org_key] = contact
        added.add(name_org_key)

    if owner_key and contact_type:
        contact_by_owner_type[(owner_key, contact_type)] = contact

    assoc_exists = False
    if contact.id is not None:
        assoc_exists = (
            session.query(ThingContactAssociation.id)
            .filter(
                ThingContactAssociation.thing_id == thing.id,
                ThingContactAssociation.contact_id == contact.id,
            )
            .first()
            is not None
        )
    if not assoc_exists:
        assoc = ThingContactAssociation()
        assoc.thing = thing
        assoc.contact = contact
        session.add(assoc)

    return contact, new_contact


# ============= EOF =============================================
