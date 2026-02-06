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

from contextlib import contextmanager

from typer.testing import CliRunner

from cli.cli import cli
from data_migrations.base import DataMigration


@contextmanager
def _fake_session_ctx():
    yield object()


def test_data_migrations_list_empty(monkeypatch):
    monkeypatch.setattr("data_migrations.registry.list_migrations", lambda: [])
    runner = CliRunner()
    result = runner.invoke(cli, ["data-migrations", "list"])
    assert result.exit_code == 0
    assert "No data migrations registered" in result.output


def test_data_migrations_list_non_empty(monkeypatch):
    migrations = [
        DataMigration(
            id="20260205_0001",
            alembic_revision="000000000000",
            name="Backfill Example",
            description="Example",
            run=lambda session: None,
        )
    ]
    monkeypatch.setattr("data_migrations.registry.list_migrations", lambda: migrations)
    runner = CliRunner()
    result = runner.invoke(cli, ["data-migrations", "list"])
    assert result.exit_code == 0
    assert "20260205_0001: Backfill Example" in result.output


def test_data_migrations_run_invokes_runner(monkeypatch):
    monkeypatch.setattr("db.engine.session_ctx", _fake_session_ctx)

    called = {}

    def fake_run(session, migration_id, force=False):
        called["migration_id"] = migration_id
        called["force"] = force
        return True

    monkeypatch.setattr("data_migrations.runner.run_migration_by_id", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["data-migrations", "run", "20260205_0001"])

    assert result.exit_code == 0
    assert called == {"migration_id": "20260205_0001", "force": False}
    assert "applied" in result.output


def test_data_migrations_run_all_invokes_runner(monkeypatch):
    monkeypatch.setattr("db.engine.session_ctx", _fake_session_ctx)

    called = {}

    def fake_run_all(session, include_repeatable=False, force=False):
        called["include_repeatable"] = include_repeatable
        called["force"] = force
        return ["20260205_0001"]

    monkeypatch.setattr("data_migrations.runner.run_all", fake_run_all)

    runner = CliRunner()
    result = runner.invoke(cli, ["data-migrations", "run-all", "--include-repeatable"])

    assert result.exit_code == 0
    assert called == {"include_repeatable": True, "force": False}
    assert "applied 1 migration(s)" in result.output
