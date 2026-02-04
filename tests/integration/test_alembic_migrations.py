# ===============================================================================
# Copyright 2026
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
Integration tests for Alembic migrations.

Tests that:
1. Migrations run successfully (upgrade head)
2. Expected tables and columns exist after migration
3. Migration history is consistent
4. Downgrade paths work (optional, selected migrations)

These tests ensure CI catches migration errors before merge and that
schema drift between models and migrations is detected.

Related: GitHub Issue #356
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from db.engine import engine, session_ctx


def _alembic_config() -> Config:
    """Get Alembic configuration pointing to project root."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "alembic"))
    return cfg


# =============================================================================
# Migration History Tests
# =============================================================================


class TestMigrationHistory:
    """Tests for migration script consistency."""

    def test_migrations_have_no_multiple_heads(self):
        """
        Migration history should have a single head (no branching).

        Multiple heads indicate parallel migrations that need to be merged.
        """
        config = _alembic_config()
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()

        assert len(heads) == 1, (
            f"Multiple migration heads detected: {heads}. "
            "Run 'alembic merge heads' to resolve."
        )

    def test_all_migrations_have_down_revision(self):
        """
        All migrations except the first should have a down_revision.

        This ensures the migration chain is unbroken.
        """
        config = _alembic_config()
        script = ScriptDirectory.from_config(config)

        revisions_without_down = []
        base_found = False

        for rev in script.walk_revisions():
            if rev.down_revision is None:
                if base_found:
                    revisions_without_down.append(rev.revision)
                base_found = True

        assert not revisions_without_down, (
            f"Migrations missing down_revision (besides base): {revisions_without_down}"
        )

    def test_current_revision_matches_head(self):
        """
        Database should be at the latest migration head.

        This verifies that test setup ran migrations successfully.
        """
        config = _alembic_config()
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            current = result.scalar()

        assert current == head, (
            f"Database at revision {current}, expected head {head}. "
            "Run 'alembic upgrade head'."
        )


# =============================================================================
# Schema Verification Tests
# =============================================================================


class TestSchemaAfterMigration:
    """Tests that verify expected schema exists after migrations."""

    @pytest.fixture(autouse=True)
    def inspector(self):
        """Provide SQLAlchemy inspector for schema introspection."""
        self._inspector = inspect(engine)
        yield
        self._inspector = None

    def test_core_tables_exist(self):
        """Core application tables should exist after migration."""
        expected_tables = [
            "location",
            "thing",
            "observation",
            "sample",
            "sensor",
            "contact",
            "field_event",
            "field_activity",
            "group",
            "asset",
            "parameter",
            "lexicon_term",
            "lexicon_category",
        ]

        existing_tables = self._inspector.get_table_names()

        missing = [t for t in expected_tables if t not in existing_tables]
        assert not missing, f"Missing core tables: {missing}"

    def test_legacy_nma_tables_exist(self):
        """Legacy NMA tables should exist for data migration support."""
        expected_nma_tables = [
            "NMA_Chemistry_SampleInfo",
            "NMA_MajorChemistry",
            "NMA_MinorTraceChemistry",
            "NMA_FieldParameters",
            "NMA_HydraulicsData",
            "NMA_Stratigraphy",
            "NMA_Radionuclides",
            "NMA_AssociatedData",
            "NMA_WeatherData",
        ]

        existing_tables = self._inspector.get_table_names()

        missing = [t for t in expected_nma_tables if t not in existing_tables]
        assert not missing, f"Missing NMA legacy tables: {missing}"

    def test_thing_table_has_required_columns(self):
        """Thing table should have all required columns."""
        columns = {c["name"] for c in self._inspector.get_columns("thing")}

        required_columns = [
            "id",
            "name",
            "thing_type",
            "release_status",
            "created_at",
            "nma_pk_welldata",
            "nma_pk_location",
        ]

        missing = [c for c in required_columns if c not in columns]
        assert not missing, f"Thing table missing columns: {missing}"

    def test_location_table_has_geometry_column(self):
        """Location table should have PostGIS geometry column."""
        columns = {c["name"] for c in self._inspector.get_columns("location")}

        assert "point" in columns, "Location table missing 'point' geometry column"

    def test_observation_table_has_required_columns(self):
        """Observation table should have all required columns."""
        columns = {c["name"] for c in self._inspector.get_columns("observation")}

        required_columns = [
            "id",
            "observation_datetime",
            "value",
            "unit",
            "sample_id",
            "release_status",
        ]

        missing = [c for c in required_columns if c not in columns]
        assert not missing, f"Observation table missing columns: {missing}"

    def test_alembic_version_table_exists(self):
        """Alembic version tracking table should exist."""
        tables = self._inspector.get_table_names()
        assert "alembic_version" in tables, "alembic_version table missing"

    def test_postgis_extension_enabled(self):
        """PostGIS extension should be enabled."""
        with session_ctx() as session:
            result = session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
            )
            postgis = result.scalar()

        assert postgis == "postgis", "PostGIS extension not enabled"


# =============================================================================
# Foreign Key Integrity Tests
# =============================================================================


class TestForeignKeyIntegrity:
    """Tests that verify FK relationships are properly defined."""

    @pytest.fixture(autouse=True)
    def inspector(self):
        """Provide SQLAlchemy inspector for schema introspection."""
        self._inspector = inspect(engine)
        yield
        self._inspector = None

    def test_observation_has_sample_fk(self):
        """Observation should have FK to Sample."""
        fks = self._inspector.get_foreign_keys("observation")
        fk_tables = {fk["referred_table"] for fk in fks}

        assert "sample" in fk_tables, "Observation missing FK to sample"

    def test_sample_has_field_activity_fk(self):
        """Sample should have FK to FieldActivity."""
        fks = self._inspector.get_foreign_keys("sample")
        fk_tables = {fk["referred_table"] for fk in fks}

        assert "field_activity" in fk_tables, "Sample missing FK to field_activity"

    def test_field_activity_has_field_event_fk(self):
        """FieldActivity should have FK to FieldEvent."""
        fks = self._inspector.get_foreign_keys("field_activity")
        fk_tables = {fk["referred_table"] for fk in fks}

        assert "field_event" in fk_tables, "FieldActivity missing FK to field_event"

    def test_field_event_has_thing_fk(self):
        """FieldEvent should have FK to Thing."""
        fks = self._inspector.get_foreign_keys("field_event")
        fk_tables = {fk["referred_table"] for fk in fks}

        assert "thing" in fk_tables, "FieldEvent missing FK to thing"

    def test_nma_chemistry_has_thing_fk(self):
        """NMA_Chemistry_SampleInfo should have FK to Thing."""
        fks = self._inspector.get_foreign_keys("NMA_Chemistry_SampleInfo")
        fk_tables = {fk["referred_table"] for fk in fks}

        assert "thing" in fk_tables, (
            "NMA_Chemistry_SampleInfo missing FK to thing"
        )


# =============================================================================
# Index Tests
# =============================================================================


class TestIndexes:
    """Tests that verify important indexes exist."""

    @pytest.fixture(autouse=True)
    def inspector(self):
        """Provide SQLAlchemy inspector for schema introspection."""
        self._inspector = inspect(engine)
        yield
        self._inspector = None

    def test_location_has_spatial_index(self):
        """Location table should have spatial index on point column."""
        indexes = self._inspector.get_indexes("location")
        index_columns = []
        for idx in indexes:
            index_columns.extend(idx.get("column_names", []))

        # Spatial indexes may be named differently, check for point column
        # or gist index type
        has_point_index = "point" in index_columns or any(
            "point" in str(idx.get("name", "")).lower() or
            "gist" in str(idx.get("name", "")).lower()
            for idx in indexes
        )

        # Also check via pg_indexes for GIST indexes
        if not has_point_index:
            with session_ctx() as session:
                result = session.execute(
                    text("""
                        SELECT indexname FROM pg_indexes
                        WHERE tablename = 'location'
                        AND indexdef LIKE '%gist%'
                    """)
                )
                gist_indexes = result.fetchall()
                has_point_index = len(gist_indexes) > 0

        assert has_point_index, "Location table missing spatial index on point"


# =============================================================================
# Downgrade Tests (Selective)
# =============================================================================


class TestMigrationDowngrade:
    """
    Tests for migration downgrade capability.

    Note: These tests are more expensive as they modify schema.
    Only test critical migrations.
    """

    @pytest.mark.skip(reason="Downgrade tests modify schema - run manually")
    def test_can_downgrade_one_revision(self):
        """
        Should be able to downgrade one revision and upgrade back.

        This is a destructive test - skipped by default.
        """
        config = _alembic_config()
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()

        # Get the revision before head
        head_script = script.get_revision(head)
        if head_script.down_revision is None:
            pytest.skip("Cannot downgrade from base revision")

        previous = head_script.down_revision
        if isinstance(previous, tuple):
            previous = previous[0]

        # Downgrade
        command.downgrade(config, previous)

        # Verify we're at previous revision
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            current = result.scalar()
        assert current == previous

        # Upgrade back
        command.upgrade(config, "head")

        # Verify we're back at head
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            current = result.scalar()
        assert current == head
