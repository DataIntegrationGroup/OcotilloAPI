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
Migration smoke test.

Ensures Alembic can build the schema from scratch and reaches head.
"""

from pathlib import Path

import db  # noqa: F401  # Register models for metadata.
from alembic import command
from alembic.config import Config
from core.initializers import init_lexicon, init_parameter
from db.base import Base
from db.engine import session_ctx
from db.initialization import recreate_public_schema
from sqlalchemy import inspect
from sqlalchemy_searchable import sync_trigger
from sqlalchemy_utils import TSVectorType


def _reset_schema() -> None:
    with session_ctx() as session:
        recreate_public_schema(session)


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


def _sync_search_vectors() -> None:
    with session_ctx() as session:
        conn = session.connection()
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, TSVectorType):
                    sync_trigger(
                        conn,
                        table.name,
                        column.name,
                        list(column.type.columns),
                    )
        session.commit()


def test_migrations_upgrade_to_head():
    _reset_schema()
    command.upgrade(_alembic_config(), "head")

    with session_ctx() as session:
        inspector = inspect(session.bind)
        table_names = set(inspector.get_table_names())
        assert "alembic_version" in table_names

        expected_tables = set(Base.metadata.tables.keys())
        missing_tables = expected_tables - table_names
        assert not missing_tables, f"Missing tables: {sorted(missing_tables)}"

        location_cols = inspector.get_columns("location")
        columns = {col["name"]: col for col in location_cols}
        assert "description" in columns
        assert columns["description"]["nullable"] is True

    _sync_search_vectors()
    init_lexicon()
    init_parameter()
