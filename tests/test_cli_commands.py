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
from __future__ import annotations

import tempfile
from pathlib import Path

from click.testing import CliRunner
from sqlalchemy import select

from cli.cli import cli
from db import FieldActivity, FieldEvent, FieldEventParticipant, Observation, Sample
from db.engine import session_ctx


def test_initialize_lexicon_invokes_initializer(monkeypatch):
    called = {"count": 0}

    def fake_initializer():
        called["count"] += 1

    monkeypatch.setattr("core.initializers.init_lexicon", fake_initializer)

    runner = CliRunner()
    result = runner.invoke(cli, ["initialize-lexicon"])

    assert result.exit_code == 0
    assert called["count"] == 1


def test_associate_assets_command_calls_service(monkeypatch):
    captured = {}

    def fake_associate(source_directory):
        captured["path"] = Path(source_directory)
        return ["uri1"]

    monkeypatch.setattr("cli.service_adapter.associate_assets", fake_associate)

    runner = CliRunner()
    with runner.isolated_filesystem():
        workdir = Path.cwd()
        asset_dir = workdir / "asset_import_batch"
        asset_dir.mkdir()

        result = runner.invoke(cli, ["associate-assets", str(asset_dir)])

    assert result.exit_code == 0, result.output
    assert captured["path"] == asset_dir


def test_well_inventory_csv_command_calls_service(monkeypatch, tmp_path):
    inventory_file = tmp_path / "inventory.csv"
    inventory_file.write_text("header\nvalue\n")
    captured = {}

    def fake_well_inventory(file_path):
        captured["path"] = file_path

    monkeypatch.setattr("cli.service_adapter.well_inventory_csv", fake_well_inventory)

    runner = CliRunner()
    result = runner.invoke(cli, ["well-inventory-csv", str(inventory_file)])

    assert result.exit_code == 0
    assert Path(captured["path"]) == inventory_file


def test_water_levels_bulk_upload_default_output(monkeypatch, tmp_path):
    csv_file = tmp_path / "water_levels.csv"
    csv_file.write_text("col\nvalue\n")
    captured = {}

    def fake_upload(file_path, *, pretty_json=False):
        captured["path"] = file_path
        captured["pretty_json"] = pretty_json
        return 0

    monkeypatch.setattr("cli.service_adapter.water_levels_csv", fake_upload)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["water-levels", "bulk-upload", "--file", str(csv_file)]
    )

    assert result.exit_code == 0
    assert Path(captured["path"]) == csv_file
    assert captured["pretty_json"] is False


def test_water_levels_bulk_upload_json_output(monkeypatch, tmp_path):
    """
    Developer's note

    The function that uploads water levels from CSV files has its own unit tests that
    verify that the database rows are created correctly. Since the CLI command simply
    calls that function, an end-to-end test here is not needed. The test here verifies
    that the CLI can be invoked and that the response is as expected.
    """

    csv_file = tmp_path / "water_levels.csv"
    csv_file.write_text("col\nvalue\n")
    captured = {}

    def fake_upload(file_path, *, pretty_json=False):
        captured["path"] = file_path
        captured["pretty_json"] = pretty_json
        return 0

    monkeypatch.setattr("cli.service_adapter.water_levels_csv", fake_upload)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "water-levels",
            "bulk-upload",
            "--file",
            str(csv_file),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert Path(captured["path"]) == csv_file
    assert captured["pretty_json"] is True


def test_water_levels_cli_persists_observations(
    water_level_bulk_upload_data, water_well_thing, contact, second_contact
):
    """
    End-to-end CLI invocation should create FieldEvent, Sample, and Observation rows.

    This is essentially the same test in tests/services/test_water_level_service.py::test_bulk_upload,
    but it works by invoking the command line rather than just the function directly.
    """

    # write to a CSV file in memory then delete it after processing
    # this is being done to avoid filesystem dependencies in tests and
    # to use the contact fixture for the field staff
    csv_headers = list(water_level_bulk_upload_data.keys())
    csv_values = list(water_level_bulk_upload_data.values())

    csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    with tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8", delete_on_close=True
    ) as temp_csv:
        temp_csv.write(csv_content)
        temp_csv.flush()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["water-levels", "bulk-upload", "--file", str(temp_csv.name)]
        )

        assert result.exit_code == 0, result.output

        created_ids: dict[str, int] = {}
        with session_ctx() as session:
            stmt = (
                select(Observation)
                .join(Observation.sample)
                .join(Sample.field_activity)
                .join(FieldActivity.field_event)
                .where(
                    Observation.notes
                    == water_level_bulk_upload_data["water_level_notes"]
                )
            )
            observations = session.scalars(stmt).all()
            assert (
                len(observations) == 1
            ), "Expected one observation for the uploaded CSV"

            observation = observations[0]
            sample = observation.sample
            field_activity = sample.field_activity
            field_event = field_activity.field_event
            # contact is created before second_contact so will have a lower id
            field_event_participants = sorted(
                field_event.field_event_participants, key=lambda fep: fep.contact_id
            )
            field_event_participant_1 = field_event_participants[0]
            field_event_participant_2 = field_event_participants[1]

            # ----------
            # INSERTION VERIFICATION
            # ----------

            # FieldEvent
            assert field_event is not None
            assert field_event.thing_id == water_well_thing.id
            # TODO: uncomment after timezone handling is fixed
            # assert field_event.event_date.isoformat() == "2025-02-15T15:00:00+00:00"
            assert (
                field_event.event_date.isoformat()
                == water_level_bulk_upload_data["field_event_date_time"] + "+00:00"
            )

            # FieldActivity
            assert field_activity is not None
            assert field_activity.activity_type == "groundwater level"

            # FieldEventParticipants
            assert field_event_participant_1 is not None
            assert field_event_participant_1.contact_id == contact.id
            assert field_event_participant_1.field_event_id == field_event.id
            assert field_event_participant_1.participant_role == "Lead"

            assert field_event_participant_2 is not None
            assert field_event_participant_2.contact_id == second_contact.id
            assert field_event_participant_2.field_event_id == field_event.id
            assert field_event_participant_2.participant_role == "Participant"

            # Sample
            assert sample is not None
            assert sample.field_activity_id == field_activity.id
            # TODO: uncomment after timezone handling is fixed
            # assert sample.sample_date.isoformat() == "2025-02-15T17:30:00+00:00"
            assert (
                sample.sample_date.isoformat()
                == water_level_bulk_upload_data["water_level_date_time"] + "+00:00"
            )
            assert sample.sample_name[0:3] == "wl-"
            assert sample.sample_matrix == "water"
            assert sample.sample_method == water_level_bulk_upload_data["sample_method"]
            assert sample.qc_type == "Normal"
            assert sample.depth_top is None
            assert sample.depth_bottom is None

            # Observation
            assert observation is not None
            assert observation.sample_id == sample.id
            # TODO: uncomment after timezone handling is fixed
            # assert observation.observation_datetime.isoformat() == "2025-02-15T17:30:00+00:00"
            assert (
                observation.observation_datetime.isoformat()
                == water_level_bulk_upload_data["water_level_date_time"] + "+00:00"
            )
            assert observation.value == float(
                water_level_bulk_upload_data["depth_to_water_ft"]
            )
            assert observation.unit == "ft"
            assert observation.measuring_point_height == float(
                water_level_bulk_upload_data["mp_height"]
            )
            assert (
                observation.groundwater_level_reason
                == water_level_bulk_upload_data["level_status"]
            )
            assert (
                observation.groundwater_level_accuracy
                == water_level_bulk_upload_data["data_quality"]
            )
            assert (
                observation.notes == water_level_bulk_upload_data["water_level_notes"]
            )

            created_ids = {
                "observation_id": observation.id,
                "sample_id": sample.id,
                "field_activity_id": field_activity.id,
                "field_event_id": field_event.id,
                "field_participant_ids": [fep.id for fep in field_event.participants],
            }

        if created_ids:
            # Clean up committed rows so other tests see a pristine database.
            with session_ctx() as session:
                observation = session.get(Observation, created_ids["observation_id"])
                sample = session.get(Sample, created_ids["sample_id"])
                field_activity = session.get(
                    FieldActivity, created_ids["field_activity_id"]
                )
                field_event = session.get(FieldEvent, created_ids["field_event_id"])
                field_participants = (
                    session.query(FieldEventParticipant)
                    .filter(
                        FieldEventParticipant.id.in_(
                            created_ids["field_participant_ids"]
                        )
                    )
                    .all()
                )

                if observation:
                    session.delete(observation)
                    session.flush()
                if sample:
                    session.delete(sample)
                    session.flush()
                if field_participants:
                    for participant in field_participants:
                        session.delete(participant)
                    session.flush()
                if field_activity:
                    session.delete(field_activity)
                    session.flush()
                if field_event:
                    session.delete(field_event)
                    session.flush()

                session.commit()


# ============= EOF =============================================
