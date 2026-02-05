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
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    func,
    select,
    text,
)
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from data_migrations.registry import get_migration, list_migrations
from transfers.logger import logger

metadata = MetaData()
data_migration_history = Table(
    "data_migration_history",
    metadata,
    Column("id", String(100), nullable=False),
    Column("alembic_revision", String(100), nullable=False),
    Column("name", String(255), nullable=False),
    Column("is_repeatable", Boolean, nullable=False, default=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
    Column("checksum", String(64), nullable=True),
)


@dataclass(frozen=True)
class MigrationStatus:
    id: str
    alembic_revision: str
    name: str
    is_repeatable: bool
    applied_count: int
    last_applied_at: datetime | None


def ensure_history_table(session: Session) -> None:
    metadata.create_all(bind=session.get_bind(), tables=[data_migration_history])


def _applied_counts(session: Session) -> dict[str, int]:
    stmt = select(data_migration_history.c.id, func.count().label("count")).group_by(
        data_migration_history.c.id
    )
    return {row.id: int(row.count) for row in session.execute(stmt).all()}


def _last_applied_map(session: Session) -> dict[str, datetime]:
    stmt = select(
        data_migration_history.c.id,
        func.max(data_migration_history.c.applied_at).label("last_applied_at"),
    ).group_by(data_migration_history.c.id)
    return {row.id: row.last_applied_at for row in session.execute(stmt).all()}


def get_status(session: Session) -> list[MigrationStatus]:
    ensure_history_table(session)
    applied_counts = _applied_counts(session)
    last_applied = _last_applied_map(session)
    statuses = []
    for migration in list_migrations():
        statuses.append(
            MigrationStatus(
                id=migration.id,
                alembic_revision=migration.alembic_revision,
                name=migration.name,
                is_repeatable=migration.is_repeatable,
                applied_count=applied_counts.get(migration.id, 0),
                last_applied_at=last_applied.get(migration.id),
            )
        )
    return statuses


def _record_migration(session: Session, migration: DataMigration) -> None:
    session.execute(
        data_migration_history.insert().values(
            id=migration.id,
            alembic_revision=migration.alembic_revision,
            name=migration.name,
            is_repeatable=bool(migration.is_repeatable),
            applied_at=datetime.now(tz=timezone.utc),
        )
    )


def _is_applied(session: Session, migration: DataMigration) -> bool:
    stmt = (
        select(func.count())
        .select_from(data_migration_history)
        .where(data_migration_history.c.id == migration.id)
    )
    return session.execute(stmt).scalar_one() > 0


def _ensure_alembic_applied(session: Session, migration: DataMigration) -> None:
    count = session.execute(
        text("SELECT COUNT(*) FROM alembic_version WHERE version_num = :rev"),
        {"rev": migration.alembic_revision},
    ).scalar_one()
    if count == 0:
        raise ValueError(
            f"Alembic revision {migration.alembic_revision} not applied for "
            f"data migration {migration.id}"
        )


def run_migration(
    session: Session,
    migration: DataMigration,
    *,
    force: bool = False,
) -> bool:
    ensure_history_table(session)
    _ensure_alembic_applied(session, migration)

    if not migration.is_repeatable and not force and _is_applied(session, migration):
        logger.info("Skipping data migration %s (already applied)", migration.id)
        return False

    logger.info("Running data migration %s - %s", migration.id, migration.name)
    migration.run(session)
    _record_migration(session, migration)
    session.commit()
    return True


def run_migration_by_id(
    session: Session, migration_id: str, *, force: bool = False
) -> bool:
    migration = get_migration(migration_id)
    if migration is None:
        raise ValueError(f"Unknown data migration: {migration_id}")
    return run_migration(session, migration, force=force)


def run_all(
    session: Session,
    *,
    include_repeatable: bool = False,
    force: bool = False,
    allowed_alembic_revisions: set[str] | None = None,
) -> list[str]:
    ran = []
    for migration in list_migrations():
        if (
            allowed_alembic_revisions is not None
            and migration.alembic_revision not in allowed_alembic_revisions
        ):
            logger.info(
                "Skipping data migration %s (alembic revision %s not applied)",
                migration.id,
                migration.alembic_revision,
            )
            continue
        _ensure_alembic_applied(session, migration)
        if migration.is_repeatable and not include_repeatable:
            logger.info(
                "Skipping repeatable migration %s (include_repeatable=false)",
                migration.id,
            )
            continue
        if run_migration(session, migration, force=force):
            ran.append(migration.id)
    return ran
