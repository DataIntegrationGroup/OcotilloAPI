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
The hydrograph corrector's publish and range-delete endpoints.

Both are gated on `AMP.Staging`, which nobody holds in Authentik yet -- these
tests override that dependency, so they cover the behaviour, not the grant.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from core.dependencies import amp_staging_function, amp_viewer_function
from db import Deployment, Sensor, Thing, TransducerObservation
from db.engine import session_ctx
from db.transducer import TransducerObservationBlock
from main import app
from tests import client, get_parameter_id, override_authentication

PUBLISH_URL = "/observation/transducer-groundwater-level/block"
READ_URL = "/observation/transducer-groundwater-level"

T0 = datetime(2025, 1, 15, tzinfo=timezone.utc)


def _groundwater_level_parameter_id() -> int:
    return get_parameter_id("groundwater level", "Field Parameter")


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[amp_staging_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


@pytest.fixture()
def published_well():
    """A well with one deployment and nothing stored yet."""
    with session_ctx() as session:
        thing = Thing(
            name=f"Hydrograph Publish Well {datetime.now().timestamp()}",
            first_visit_date="2023-03-03",
            thing_type="water well",
            release_status="draft",
            well_depth=200,
            hole_depth=200,
            well_casing_diameter=5.0,
            well_casing_depth=200.0,
        )
        sensor = Sensor(
            name=f"Hydrograph Publish Sensor {datetime.now().timestamp()}",
            sensor_type="Pressure Transducer",
            model="Model X",
            serial_no=f"serial-{datetime.now().timestamp()}",
            pcn_number=f"pcn-{datetime.now().timestamp()}",
            owner_agency="NMBGMR",
            sensor_status="In Service",
            release_status="draft",
        )
        session.add_all([thing, sensor])
        session.flush()

        deployment = Deployment(
            sensor_id=sensor.id,
            thing_id=thing.id,
            installation_date="2020-01-01",
            removal_date=None,
            recording_interval=6,
            recording_interval_units="hour",
        )
        session.add(deployment)
        session.commit()

        thing_id, deployment_id, sensor_id = thing.id, deployment.id, sensor.id

    yield thing_id, deployment_id

    with session_ctx() as session:
        deployment_ids = session.scalars(
            select(Deployment.id).where(Deployment.thing_id == thing_id)
        ).all()
        if deployment_ids:
            for observation in session.scalars(
                select(TransducerObservation).where(
                    TransducerObservation.deployment_id.in_(deployment_ids)
                )
            ).all():
                session.delete(observation)
        for block in session.scalars(
            select(TransducerObservationBlock).where(
                TransducerObservationBlock.thing_id == thing_id
            )
        ).all():
            session.delete(block)
        session.flush()
        for model, pk in ((Deployment, deployment_id), (Thing, thing_id)):
            obj = session.get(model, pk)
            if obj is not None:
                session.delete(obj)
        session.flush()
        sensor = session.get(Sensor, sensor_id)
        if sensor is not None:
            session.delete(sensor)
        session.commit()


def _payload(thing_id, hours=(0, 6, 12), **overrides):
    payload = {
        "thing_id": thing_id,
        "parameter_id": _groundwater_level_parameter_id(),
        "release_status": "provisional",
        "review_status": "not reviewed",
        "provenance": {
            "source_file": "SO-0167_20250115.csv",
            "source_kind": "water_head",
            "corrections": ["convert_water_head (drift corrected)"],
            "notes": "Snapped to 2025-01-15 manual measurement.",
        },
        "measurements": [
            {
                "observation_datetime": (T0 + timedelta(hours=h)).isoformat(),
                "value": 42.5 + index * 0.01,
            }
            for index, h in enumerate(hours)
        ],
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------
def test_publish_creates_one_block_and_all_of_its_readings(published_well):
    thing_id, deployment_id = published_well

    response = client.post(PUBLISH_URL, json=_payload(thing_id))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["observation_count"] == 3
    assert body["thing_id"] == thing_id
    # Deployment resolved server-side: the payload never named one.
    assert body["deployment_id"] == deployment_id

    block = body["block"]
    assert block["release_status"] == "provisional"
    assert block["review_status"] == "not reviewed"
    assert block["source_file"] == "SO-0167_20250115.csv"
    assert block["corrections"] == ["convert_water_head (drift corrected)"]
    assert block["comment"] == "Snapped to 2025-01-15 manual measurement."

    # Span is derived from the data, not sent by the client.
    assert block["start_datetime"] == "2025-01-15T00:00:00Z"
    assert block["end_datetime"] == "2025-01-15T12:00:00Z"


def test_published_readings_come_back_from_the_read_endpoint(published_well):
    thing_id, _ = published_well
    client.post(PUBLISH_URL, json=_payload(thing_id))

    response = client.get(READ_URL, params={"thing_id": thing_id})

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 3
    # Newest first by default, so a client can ask for the latest with size 1.
    assert items[0]["observation"]["observation_datetime"] == "2025-01-15T12:00:00Z"
    # Unreviewed on publish is provisional on USGS terms.
    assert items[0]["observation"]["data_maturity"] == "provisional"


def test_per_reading_notes_are_persisted(published_well):
    thing_id, _ = published_well
    payload = _payload(thing_id)
    payload["measurements"][1]["note"] = "spurious reflection removed"

    client.post(PUBLISH_URL, json=payload)

    response = client.get(READ_URL, params={"thing_id": thing_id, "order": "asc"})
    observations = [item["observation"] for item in response.json()["items"]]
    assert observations[0]["note"] is None
    assert observations[1]["note"] == "spurious reflection removed"


def test_a_single_reading_publishes_as_a_zero_width_block(published_well):
    thing_id, _ = published_well

    response = client.post(PUBLISH_URL, json=_payload(thing_id, hours=(0,)))

    assert response.status_code == 201, response.text
    block = response.json()["block"]
    assert block["start_datetime"] == block["end_datetime"]


def test_overlapping_publish_is_rejected_and_names_the_blocks(published_well):
    thing_id, _ = published_well
    first = client.post(PUBLISH_URL, json=_payload(thing_id))
    first_block_id = first.json()["block"]["id"]

    response = client.post(PUBLISH_URL, json=_payload(thing_id, hours=(6, 18)))

    assert response.status_code == 409
    detail = response.json()["detail"][0]
    assert str(first_block_id) in detail["msg"]
    assert detail["input"]["overlapping_blocks"][0]["id"] == first_block_id


def test_replace_overlapping_supersedes_the_old_block_and_its_readings(
    published_well,
):
    thing_id, _ = published_well
    first = client.post(PUBLISH_URL, json=_payload(thing_id))
    first_block_id = first.json()["block"]["id"]

    response = client.post(
        PUBLISH_URL,
        params={"replace_overlapping": "true"},
        json=_payload(thing_id, hours=(6, 18)),
    )

    assert response.status_code == 201, response.text
    assert response.json()["block"]["id"] != first_block_id

    with session_ctx() as session:
        assert session.get(TransducerObservationBlock, first_block_id) is None

    # Only the replacing series survives -- the superseded readings went with
    # their block rather than being left where no block covers them.
    items = client.get(READ_URL, params={"thing_id": thing_id}).json()["items"]
    assert len(items) == 2


def test_publish_is_atomic_when_a_reading_collides(published_well):
    thing_id, _ = published_well
    client.post(PUBLISH_URL, json=_payload(thing_id))

    # Delete the block but leave its readings, which is what a hand-deleted
    # block leaves behind: rows the reader ignores but storage still holds.
    with session_ctx() as session:
        for block in session.scalars(
            select(TransducerObservationBlock).where(
                TransducerObservationBlock.thing_id == thing_id
            )
        ).all():
            session.delete(block)
        session.commit()

    response = client.post(PUBLISH_URL, json=_payload(thing_id))

    assert response.status_code == 409
    assert "no block covers" in response.json()["detail"][0]["msg"]

    with session_ctx() as session:
        blocks = session.scalars(
            select(TransducerObservationBlock).where(
                TransducerObservationBlock.thing_id == thing_id
            )
        ).all()
        assert blocks == []


def test_unknown_thing_is_a_404(published_well):
    response = client.post(PUBLISH_URL, json=_payload(-1))
    assert response.status_code == 404


def test_out_of_order_measurements_point_at_the_offending_row(published_well):
    thing_id, _ = published_well
    payload = _payload(thing_id, hours=(0, 12, 6))

    response = client.post(PUBLISH_URL, json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"][:3] == ["body", "measurements"]
        for error in response.json()["detail"]
    )


def test_naive_timestamps_are_rejected(published_well):
    thing_id, _ = published_well
    payload = _payload(thing_id)
    payload["measurements"][0]["observation_datetime"] = "2025-01-15T00:00:00"

    response = client.post(PUBLISH_URL, json=payload)

    assert response.status_code == 422


def test_an_empty_series_is_rejected(published_well):
    thing_id, _ = published_well
    response = client.post(PUBLISH_URL, json=_payload(thing_id, hours=()))
    assert response.status_code == 422


def test_a_deployment_on_another_well_is_rejected(published_well, sensor):
    thing_id, _ = published_well
    with session_ctx() as session:
        other = Thing(
            name=f"Hydrograph Other Well {datetime.now().timestamp()}",
            first_visit_date="2023-03-03",
            thing_type="water well",
            release_status="draft",
        )
        session.add(other)
        session.flush()
        other_deployment = Deployment(
            sensor_id=sensor.id, thing_id=other.id, installation_date="2020-01-01"
        )
        session.add(other_deployment)
        session.commit()
        other_deployment_id, other_thing_id = other_deployment.id, other.id

    try:
        response = client.post(
            PUBLISH_URL,
            json=_payload(thing_id, deployment_id=other_deployment_id),
        )
        assert response.status_code == 422
        assert "belongs to thing" in response.json()["detail"][0]["msg"]
    finally:
        with session_ctx() as session:
            session.delete(session.get(Deployment, other_deployment_id))
            session.flush()
            session.delete(session.get(Thing, other_thing_id))
            session.commit()


# --------------------------------------------------------------------------
# range delete
# --------------------------------------------------------------------------
def test_deleting_the_whole_span_removes_the_block_too(published_well):
    thing_id, _ = published_well
    block_id = client.post(PUBLISH_URL, json=_payload(thing_id)).json()["block"]["id"]

    response = client.request(
        "DELETE",
        READ_URL,
        params={
            "thing_id": thing_id,
            "start_time": T0.isoformat(),
            "end_time": (T0 + timedelta(hours=12)).isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted_observation_count"] == 3
    assert body["deleted_block_ids"] == [block_id]
    assert body["updated_block_ids"] == []
    assert client.get(READ_URL, params={"thing_id": thing_id}).json()["items"] == []


def test_a_partial_delete_narrows_the_block_to_the_survivors(published_well):
    thing_id, _ = published_well
    block_id = client.post(PUBLISH_URL, json=_payload(thing_id)).json()["block"]["id"]

    response = client.request(
        "DELETE",
        READ_URL,
        params={
            "thing_id": thing_id,
            "start_time": (T0 + timedelta(hours=6)).isoformat(),
            "end_time": (T0 + timedelta(hours=12)).isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted_observation_count"] == 2
    assert body["deleted_block_ids"] == []
    assert body["updated_block_ids"] == [block_id]

    with session_ctx() as session:
        block = session.get(TransducerObservationBlock, block_id)
        assert block.start_datetime == T0
        assert block.end_datetime == T0

    # The survivor is still readable, which it would not be if the narrowed
    # block no longer covered it.
    items = client.get(READ_URL, params={"thing_id": thing_id}).json()["items"]
    assert len(items) == 1


def test_an_inverted_delete_range_is_rejected(published_well):
    thing_id, _ = published_well

    response = client.request(
        "DELETE",
        READ_URL,
        params={
            "thing_id": thing_id,
            "start_time": (T0 + timedelta(hours=12)).isoformat(),
            "end_time": T0.isoformat(),
        },
    )

    assert response.status_code == 422


def test_delete_without_a_bound_is_rejected(published_well):
    thing_id, _ = published_well

    response = client.request("DELETE", READ_URL, params={"thing_id": thing_id})

    assert response.status_code == 422


def test_delete_for_an_unknown_well_is_a_404():
    response = client.request(
        "DELETE",
        READ_URL,
        params={
            "thing_id": -1,
            "start_time": T0.isoformat(),
            "end_time": (T0 + timedelta(hours=12)).isoformat(),
        },
    )

    assert response.status_code == 404


# --------------------------------------------------------------------------
# read ordering
# --------------------------------------------------------------------------
def test_ascending_order_is_honoured(published_well):
    thing_id, _ = published_well
    client.post(PUBLISH_URL, json=_payload(thing_id))

    items = client.get(READ_URL, params={"thing_id": thing_id, "order": "asc"}).json()[
        "items"
    ]

    assert items[0]["observation"]["observation_datetime"] == "2025-01-15T00:00:00Z"


def test_an_unknown_sort_field_is_rejected_rather_than_ignored(published_well):
    thing_id, _ = published_well

    response = client.get(READ_URL, params={"thing_id": thing_id, "sort": "nonsense"})

    assert response.status_code == 422


# --------------------------------------------------------------------------
# deployment resolution at the service boundary
#
# domain.hydrograph covers the rule itself; these cover the translation of its
# verdicts into responses, and the path where the client names a deployment
# and the rule never runs.
# --------------------------------------------------------------------------
def test_an_explicitly_named_deployment_is_used_as_given(published_well):
    thing_id, deployment_id = published_well

    response = client.post(
        PUBLISH_URL, json=_payload(thing_id, deployment_id=deployment_id)
    )

    assert response.status_code == 201, response.text
    assert response.json()["deployment_id"] == deployment_id


def test_unknown_deployment_is_a_404(published_well):
    thing_id, _ = published_well

    response = client.post(PUBLISH_URL, json=_payload(thing_id, deployment_id=-1))

    assert response.status_code == 404
    assert response.json()["detail"][0]["loc"] == ["body", "deployment_id"]


def test_unknown_parameter_is_a_404(published_well):
    thing_id, _ = published_well

    response = client.post(PUBLISH_URL, json=_payload(thing_id, parameter_id=-1))

    assert response.status_code == 404
    assert response.json()["detail"][0]["loc"] == ["body", "parameter_id"]


def test_two_covering_deployments_are_a_422_not_a_coin_flip(published_well, sensor):
    thing_id, _ = published_well
    with session_ctx() as session:
        second = Deployment(
            sensor_id=sensor.id,
            thing_id=thing_id,
            installation_date="2019-01-01",
            removal_date=None,
        )
        session.add(second)
        session.commit()
        second_id = second.id

    try:
        response = client.post(PUBLISH_URL, json=_payload(thing_id))

        assert response.status_code == 422
        detail = response.json()["detail"][0]
        assert detail["loc"] == ["body", "deployment_id"]
        assert "2 deployments cover" in detail["msg"]
    finally:
        with session_ctx() as session:
            session.delete(session.get(Deployment, second_id))
            session.commit()


def test_a_span_no_deployment_covers_is_a_422(published_well):
    thing_id, deployment_id = published_well
    # Retire the well's only deployment before the series was recorded.
    with session_ctx() as session:
        session.get(Deployment, deployment_id).removal_date = "2021-01-01"
        session.commit()

    try:
        response = client.post(PUBLISH_URL, json=_payload(thing_id))

        assert response.status_code == 422
        assert "No deployment covers" in response.json()["detail"][0]["msg"]
    finally:
        with session_ctx() as session:
            session.get(Deployment, deployment_id).removal_date = None
            session.commit()


def test_deleting_from_a_well_with_no_deployments_removes_nothing():
    with session_ctx() as session:
        thing = Thing(
            name=f"Hydrograph Bare Well {datetime.now().timestamp()}",
            first_visit_date="2023-03-03",
            thing_type="water well",
            release_status="draft",
        )
        session.add(thing)
        session.commit()
        thing_id = thing.id

    try:
        response = client.request(
            "DELETE",
            READ_URL,
            params={
                "thing_id": thing_id,
                "start_time": T0.isoformat(),
                "end_time": (T0 + timedelta(hours=12)).isoformat(),
            },
        )

        assert response.status_code == 200, response.text
        assert response.json() == {
            "deleted_observation_count": 0,
            "deleted_block_ids": [],
            "updated_block_ids": [],
            "thing_id": thing_id,
        }
    finally:
        with session_ctx() as session:
            session.delete(session.get(Thing, thing_id))
            session.commit()


def test_audit_stamping_survives_a_non_dict_user():
    # `authenticated()` yields the token claims, but the development bypass
    # yields `True`. Reachable in any environment running with
    # AUTHENTIK_DISABLE_AUTHENTICATION, where a publish must still write rather
    # than fail reaching into a bool for a subject id.
    from services.transducer_helper import _created_by

    assert _created_by(True) == (None, None)
    assert _created_by({"sub": "1234567890", "name": "foobar"}) == (
        "1234567890",
        "foobar",
    )


def test_a_review_status_outside_the_lexicon_is_rejected(published_well):
    # `review_status` is lexicon-backed, so an unknown term would otherwise
    # reach the column and fail on a foreign key rather than as a bad request.
    thing_id, _ = published_well

    response = client.post(
        PUBLISH_URL, json=_payload(thing_id, review_status="mostly reviewed")
    )

    assert response.status_code == 422
    assert any(
        error["loc"][:2] == ["body", "review_status"]
        for error in response.json()["detail"]
    )
