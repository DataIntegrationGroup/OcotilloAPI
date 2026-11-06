# ===============================================================================
# Copyright 2026 ross
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
"""
Rename the `permission_type` lexicon category to `site_activity`.

652b0abb3241 renamed permission_history to site_activity_consent and its
permission_type column to activity. The category that lists the activities
(Water Level Sample, Water Chemistry Sample, Datalogger Installation) kept the
old word, so "permission" still named owner consent in the lexicon while
permission_grant uses it for what staff may do.

`core/lexicon.json` already says `site_activity`, and the `SiteActivity` enum
is built from the JSON, so the API does not wait on this. It is data, not
schema: terms link to categories by id through
`lexicon_term_category_association`, so renaming the category row moves every
term with it and no foreign key changes. CD runs alembic only, so existing
databases need this to match the JSON.

If `site_activity` already exists, because `oco initialize-lexicon` ran after
the JSON changed, the two are merged: the old category's links move to the
new one, duplicates are dropped, and the old row is deleted. Re-running finds
no `permission_type` row and does nothing.
"""

import json
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.lexicon import LexiconCategory, LexiconTermCategoryAssociation

OLD_NAME = "permission_type"
NEW_NAME = "site_activity"
LEXICON_PATH = Path(__file__).resolve().parents[2] / "core" / "lexicon.json"


def _seed_description() -> str | None:
    with open(LEXICON_PATH) as f:
        lexicon = json.load(f)
    for category in lexicon["categories"]:
        if category["name"] == NEW_NAME:
            return category.get("description")
    raise RuntimeError(f"core/lexicon.json has no {NEW_NAME!r} category")


def _category(session: Session, name: str) -> LexiconCategory | None:
    return session.scalars(
        select(LexiconCategory).where(LexiconCategory.name == name)
    ).one_or_none()


def _plan(session: Session) -> str:
    old = _category(session, OLD_NAME)
    if old is None:
        return "noop"
    if _category(session, NEW_NAME) is None:
        return "rename"
    return "merge"


def dry_run(session: Session) -> str:
    plan = _plan(session)
    print(f"  {OLD_NAME} -> {NEW_NAME}: {plan}")
    return plan


def run(session: Session) -> None:
    plan = _plan(session)
    if plan == "noop":
        print(f"  no {OLD_NAME!r} category; nothing to do")
        return None

    old = _category(session, OLD_NAME)
    if plan == "rename":
        old.name = NEW_NAME
        old.description = _seed_description()
        print(f"  renamed category {OLD_NAME!r} to {NEW_NAME!r}")
        return None

    new = _category(session, NEW_NAME)
    already_linked = set(
        session.scalars(
            select(LexiconTermCategoryAssociation.term_id).where(
                LexiconTermCategoryAssociation.category_id == new.id
            )
        )
    )
    if already_linked:
        session.execute(
            delete(LexiconTermCategoryAssociation)
            .where(
                LexiconTermCategoryAssociation.category_id == old.id,
                LexiconTermCategoryAssociation.term_id.in_(already_linked),
            )
            .execution_options(synchronize_session=False)
        )
    moved = session.execute(
        update(LexiconTermCategoryAssociation)
        .where(LexiconTermCategoryAssociation.category_id == old.id)
        .values(category_id=new.id)
        .execution_options(synchronize_session=False)
    ).rowcount
    session.delete(old)
    print(
        f"  merged {OLD_NAME!r} into existing {NEW_NAME!r}: "
        f"moved {moved} term links, deleted the old category"
    )
    return None


MIGRATION = DataMigration(
    id="20261102_0001_rename_permission_type_lexicon_category",
    alembic_revision="652b0abb3241",
    name="Rename permission_type lexicon category to site_activity",
    description=(
        "permission_history became site_activity_consent (652b0abb3241). "
        "Renames the lexicon category listing its activities from "
        "permission_type to site_activity to match core/lexicon.json, merging "
        "into site_activity if a lexicon re-seed already created it."
    ),
    run=run,
    dry_run=dry_run,
    is_repeatable=False,
)
