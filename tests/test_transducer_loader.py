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
Loader behaviour against a real database.

Idempotency is the whole point of the unique constraint and cannot be shown with
a stub: it depends on Postgres enforcing the constraint and on ON CONFLICT
resolving against it.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select

from automated_ingestion.ocotillo.loader import load_observations
from automated_ingestion.ocotillo.structs import ObservationRecord
from db.engine import session_ctx
from db.parameter import Parameter
from db.transducer import TransducerObservation

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def loader_target(sensor_to_water_well_thing_deployment):
    """A deployment and parameter to load against, cleaned up afterwards."""
    deployment_id = sensor_to_water_well_thing_deployment.id
    with session_ctx() as session:
        parameter_id = session.scalar(select(Parameter.id).limit(1))
        assert parameter_id, "lexicon parameters are seeded by conftest"
        yield deployment_id, parameter_id
        session.execute(
            delete(TransducerObservation).where(
                TransducerObservation.deployment_id == deployment_id
            )
        )
        session.commit()


def _records(count, value=10.0):
    return [
        ObservationRecord(
            external_point_id="sanacaciareach-40",
            observation_datetime=START + timedelta(minutes=5 * i),
            value=value + i,
            units="ft",
        )
        for i in range(count)
    ]


def _count(session, deployment_id):
    return session.scalar(
        select(func.count())
        .select_from(TransducerObservation)
        .where(TransducerObservation.deployment_id == deployment_id)
    )


def test_loading_the_same_window_twice_does_not_duplicate(loader_target):
    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        load_observations(session, _records(10), deployment_id, parameter_id, "draft")
        load_observations(session, _records(10), deployment_id, parameter_id, "draft")
        assert _count(session, deployment_id) == 10


def test_a_corrected_value_overwrites_rather_than_being_ignored(loader_target):
    # DO NOTHING would leave the old reading in place while the run reported
    # success -- the worst of both outcomes.
    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        load_observations(
            session, _records(1, value=10.0), deployment_id, parameter_id, "draft"
        )
        load_observations(
            session, _records(1, value=99.0), deployment_id, parameter_id, "draft"
        )
        stored = session.scalar(
            select(TransducerObservation.value).where(
                TransducerObservation.deployment_id == deployment_id
            )
        )
        assert stored == 99.0


def test_batches_commit_separately(loader_target):
    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        result = load_observations(
            session,
            _records(25),
            deployment_id,
            parameter_id,
            "draft",
            batch_size=10,
        )
        assert result.batches == 3
        assert result.rows_written == 25
        assert _count(session, deployment_id) == 25


def test_loaded_readings_are_provisional_by_default(loader_target):
    # USGS publishes unapproved records as provisional. A diver reading is that
    # until somebody reviews it.
    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        load_observations(session, _records(1), deployment_id, parameter_id, "draft")
        row = session.execute(
            select(
                TransducerObservation.data_maturity,
                TransducerObservation.release_status,
            ).where(TransducerObservation.deployment_id == deployment_id)
        ).one()
        assert row.data_maturity == "provisional"


def test_public_and_provisional_can_both_be_true(loader_target):
    # The reason this is a second column: release_status lists public and
    # provisional as siblings, so one column could not express both.
    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        load_observations(session, _records(1), deployment_id, parameter_id, "public")
        row = session.execute(
            select(
                TransducerObservation.data_maturity,
                TransducerObservation.release_status,
            ).where(TransducerObservation.deployment_id == deployment_id)
        ).one()
        assert (row.release_status, row.data_maturity) == ("public", "provisional")


def test_a_correction_refreshes_maturity_too(loader_target):
    # Re-loading an approved value must not leave the earlier maturity behind.
    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        load_observations(session, _records(1), deployment_id, parameter_id, "draft")
        load_observations(
            session,
            _records(1, value=99.0),
            deployment_id,
            parameter_id,
            "draft",
            data_maturity="approved",
        )
        row = session.execute(
            select(
                TransducerObservation.value, TransducerObservation.data_maturity
            ).where(TransducerObservation.deployment_id == deployment_id)
        ).one()
        assert (row.value, row.data_maturity) == (99.0, "approved")


def test_maturity_must_be_a_lexicon_term(loader_target):
    # The column is a foreign key onto lexicon_term, so a typo is rejected by
    # the database rather than stored and puzzled over later.
    #
    # DatabaseError rather than IntegrityError: pg8000 reports a foreign key
    # violation as a ProgrammingError, and SQLAlchemy preserves that. Both
    # descend from DatabaseError, so this catches the violation without
    # asserting which driver is underneath.
    import pytest
    from sqlalchemy.exc import DatabaseError

    deployment_id, parameter_id = loader_target
    with session_ctx() as session:
        with pytest.raises(DatabaseError):
            load_observations(
                session,
                _records(1),
                deployment_id,
                parameter_id,
                "draft",
                data_maturity="probational",
            )
        session.rollback()


# ============= EOF =============================================
