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
Publish and range-delete for corrected transducer series.

Orchestration only: load the well, deployment, and colliding blocks, hand the
decisions to ``domain.hydrograph``, persist the result. See
``docs/hydrograph-correction-publish.md`` for the endpoint contract.
"""

from datetime import datetime

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from db import Parameter, Thing
from db.deployment import Deployment
from db.transducer import TransducerObservation, TransducerObservationBlock
from domain.hydrograph import (
    HydrographError,
    derive_block_span,
    narrowed_block_span,
    resolve_deployment_id,
    validate_delete_range,
)
from schemas.transducer import (
    DeletedTransducerObservationsResponse,
    OverlappingBlock,
    PublishedTransducerBlockResponse,
    TransducerObservationBlockResponse,
)
from services.exceptions_helper import PydanticStyleException

# A published block has not been reviewed by anyone yet, which on USGS terms is
# exactly `provisional`. Once a reviewer marks the block `approved` the readings
# follow. Derived rather than sent by the client so the two axes cannot be set
# to contradict each other on the way in.
_MATURITY_FOR_REVIEW_STATUS = {"approved": "approved"}
_DEFAULT_MATURITY = "provisional"


def _not_found(field: str, value, message: str):
    return PydanticStyleException(
        status_code=HTTP_404_NOT_FOUND,
        detail=[
            {
                "loc": ["body", field],
                "msg": message,
                "type": "value_error",
                "input": value,
            }
        ],
    )


def _unprocessable(loc: list, value, message: str):
    return PydanticStyleException(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        detail=[
            {
                "loc": loc,
                "msg": message,
                "type": "value_error",
                "input": value,
            }
        ],
    )


def _enum_value(value):
    """Unwrap a lexicon-backed enum member to the term the column stores."""
    return getattr(value, "value", value)


def _deployment_ids_for_thing(session: Session, thing_id: int) -> list[int]:
    return list(
        session.scalars(
            select(Deployment.id).where(Deployment.thing_id == thing_id)
        ).all()
    )


def _overlapping_blocks(
    session: Session,
    thing_id: int,
    parameter_id: int,
    span_start: datetime,
    span_end: datetime,
) -> list[TransducerObservationBlock]:
    """
    Blocks whose closed span shares an instant with ``[span_start, span_end]``.

    Inclusive on both ends, matching the block reader rather than
    ``TransducerObservationBlock.overlaps``. See ``domain.hydrograph``.
    """
    return list(
        session.scalars(
            select(TransducerObservationBlock)
            .where(
                TransducerObservationBlock.thing_id == thing_id,
                TransducerObservationBlock.parameter_id == parameter_id,
                TransducerObservationBlock.start_datetime <= span_end,
                TransducerObservationBlock.end_datetime >= span_start,
            )
            .order_by(TransducerObservationBlock.start_datetime)
        ).all()
    )


def publish_transducer_block(
    session: Session,
    payload,
    user=None,
    replace_overlapping: bool = False,
) -> PublishedTransducerBlockResponse:
    """
    Create one block and all of its readings, or nothing.

    The block's span is derived from the readings -- a client-supplied span
    wider than the data would attach unrelated readings to the block.
    """
    thing = session.get(Thing, payload.thing_id)
    if thing is None:
        raise _not_found(
            "thing_id", payload.thing_id, f"Thing {payload.thing_id} not found"
        )

    parameter = session.get(Parameter, payload.parameter_id)
    if parameter is None:
        raise _not_found(
            "parameter_id",
            payload.parameter_id,
            f"Parameter {payload.parameter_id} not found",
        )

    span_start, span_end = derive_block_span(
        [measurement.observation_datetime for measurement in payload.measurements]
    )

    deployment_id = _resolve_deployment(session, payload, span_start, span_end)

    existing = _overlapping_blocks(
        session, payload.thing_id, payload.parameter_id, span_start, span_end
    )
    if existing and not replace_overlapping:
        raise _overlap_conflict(existing)

    if existing:
        _delete_superseded(session, payload.thing_id, payload.parameter_id, existing)

    # Readings can outlive the block that covered them -- nothing links the two
    # tables, so a block deleted by hand leaves its observations behind, where
    # the reader ignores them but the storage constraint still sees them. Insert
    # would abort the transaction on the first collision with a message naming
    # the constraint, so check first and say what is actually in the way.
    _reject_colliding_observations(
        session, deployment_id, payload.parameter_id, span_start, span_end
    )

    block = TransducerObservationBlock(
        thing_id=payload.thing_id,
        parameter_id=payload.parameter_id,
        review_status=_enum_value(payload.review_status),
        release_status=_enum_value(payload.release_status),
        start_datetime=span_start,
        end_datetime=span_end,
        source_file=payload.provenance.source_file,
        source_kind=payload.provenance.source_kind,
        corrections=payload.provenance.corrections or None,
        comment=payload.provenance.notes,
    )
    _stamp_created_by(block, user)
    session.add(block)
    session.flush()

    review_status = _enum_value(payload.review_status)
    data_maturity = _MATURITY_FOR_REVIEW_STATUS.get(review_status, _DEFAULT_MATURITY)
    release_status = _enum_value(payload.release_status)
    created_by_id, created_by_name = _created_by(user)

    rows = [
        {
            "parameter_id": payload.parameter_id,
            "deployment_id": deployment_id,
            "observation_datetime": measurement.observation_datetime,
            "value": measurement.value,
            "note": measurement.note,
            "data_maturity": data_maturity,
            "release_status": release_status,
            "created_by_id": created_by_id,
            "created_by_name": created_by_name,
        }
        for measurement in payload.measurements
    ]
    session.execute(insert(TransducerObservation), rows)

    session.commit()
    session.refresh(block)

    return PublishedTransducerBlockResponse(
        block=TransducerObservationBlockResponse.model_validate(block),
        observation_count=len(rows),
        thing_id=payload.thing_id,
        deployment_id=deployment_id,
    )


def _resolve_deployment(session, payload, span_start, span_end) -> int:
    if payload.deployment_id is not None:
        deployment = session.get(Deployment, payload.deployment_id)
        if deployment is None:
            raise _not_found(
                "deployment_id",
                payload.deployment_id,
                f"Deployment {payload.deployment_id} not found",
            )
        if deployment.thing_id != payload.thing_id:
            raise _unprocessable(
                ["body", "deployment_id"],
                payload.deployment_id,
                f"Deployment {payload.deployment_id} belongs to thing "
                f"{deployment.thing_id}, not {payload.thing_id}",
            )
        return payload.deployment_id

    candidates = session.execute(
        select(
            Deployment.id, Deployment.installation_date, Deployment.removal_date
        ).where(Deployment.thing_id == payload.thing_id)
    ).all()

    try:
        return resolve_deployment_id(
            [tuple(row) for row in candidates], span_start, span_end
        )
    except HydrographError as err:
        raise _unprocessable(["body", "deployment_id"], None, str(err))


def _overlap_conflict(blocks: list[TransducerObservationBlock]):
    overlapping = [
        OverlappingBlock.model_validate(block, from_attributes=True).model_dump(
            mode="json"
        )
        for block in blocks
    ]
    ids = ", ".join(str(block.id) for block in blocks)
    return PydanticStyleException(
        status_code=HTTP_409_CONFLICT,
        detail=[
            {
                "loc": ["body", "measurements"],
                "msg": (
                    f"Time span overlaps existing block(s) {ids}. Retry with "
                    "?replace_overlapping=true to supersede them."
                ),
                "type": "value_error",
                "input": {"overlapping_blocks": overlapping},
            }
        ],
    )


def _delete_superseded(
    session: Session,
    thing_id: int,
    parameter_id: int,
    blocks: list[TransducerObservationBlock],
) -> None:
    """
    Drop the blocks a replacing publish supersedes, and their readings.

    The readings go too. Keeping them would leave rows the reader cannot show
    (no block covers them) that still occupy the deployment/parameter/instant
    the new series is about to claim -- so "replace" that kept them would fail
    on the very insert it was asked to make room for.
    """
    deployment_ids = _deployment_ids_for_thing(session, thing_id)
    if deployment_ids:
        for block in blocks:
            session.execute(
                delete(TransducerObservation).where(
                    TransducerObservation.deployment_id.in_(deployment_ids),
                    TransducerObservation.parameter_id == parameter_id,
                    TransducerObservation.observation_datetime >= block.start_datetime,
                    TransducerObservation.observation_datetime <= block.end_datetime,
                )
            )

    session.execute(
        delete(TransducerObservationBlock).where(
            TransducerObservationBlock.id.in_([block.id for block in blocks])
        )
    )
    session.flush()


def _reject_colliding_observations(
    session: Session,
    deployment_id: int,
    parameter_id: int,
    span_start: datetime,
    span_end: datetime,
) -> None:
    collisions = session.scalar(
        select(TransducerObservation.observation_datetime)
        .where(
            TransducerObservation.deployment_id == deployment_id,
            TransducerObservation.parameter_id == parameter_id,
            TransducerObservation.observation_datetime >= span_start,
            TransducerObservation.observation_datetime <= span_end,
        )
        .order_by(TransducerObservation.observation_datetime)
        .limit(1)
    )
    if collisions is None:
        return

    raise PydanticStyleException(
        status_code=HTTP_409_CONFLICT,
        detail=[
            {
                "loc": ["body", "measurements"],
                "msg": (
                    f"Deployment {deployment_id} already has readings in this "
                    f"time span (earliest {collisions.isoformat()}) that no block "
                    "covers. Delete them by range before publishing."
                ),
                "type": "value_error",
                "input": {"deployment_id": deployment_id},
            }
        ],
    )


def delete_transducer_observations(
    session: Session,
    thing_id: int,
    parameter_id: int,
    start_time: datetime,
    end_time: datetime,
) -> DeletedTransducerObservationsResponse:
    """
    Delete every reading for a well inside a closed time range, then reconcile
    the blocks that covered them.

    Scoped exactly like the ``GET`` on the same path, so the set a client
    previews is the set this removes. There is deliberately no unbounded form.
    """
    thing = session.get(Thing, thing_id)
    if thing is None:
        raise _not_found("thing_id", thing_id, f"Thing {thing_id} not found")

    try:
        validate_delete_range(start_time, end_time)
    except HydrographError as err:
        raise _unprocessable(["query", "end_time"], end_time.isoformat(), str(err))

    deployment_ids = _deployment_ids_for_thing(session, thing_id)
    if not deployment_ids:
        return DeletedTransducerObservationsResponse(
            deleted_observation_count=0,
            deleted_block_ids=[],
            updated_block_ids=[],
            thing_id=thing_id,
        )

    # Read the affected blocks before deleting: after the readings are gone
    # there is nothing left to identify which blocks covered them.
    affected_blocks = _overlapping_blocks(
        session, thing_id, parameter_id, start_time, end_time
    )

    deleted = session.execute(
        delete(TransducerObservation).where(
            TransducerObservation.deployment_id.in_(deployment_ids),
            TransducerObservation.parameter_id == parameter_id,
            TransducerObservation.observation_datetime >= start_time,
            TransducerObservation.observation_datetime <= end_time,
        )
    )
    deleted_observation_count = deleted.rowcount or 0
    session.flush()

    deleted_block_ids: list[int] = []
    updated_block_ids: list[int] = []

    for block in affected_blocks:
        surviving = list(
            session.scalars(
                select(TransducerObservation.observation_datetime).where(
                    TransducerObservation.deployment_id.in_(deployment_ids),
                    TransducerObservation.parameter_id == parameter_id,
                    TransducerObservation.observation_datetime >= block.start_datetime,
                    TransducerObservation.observation_datetime <= block.end_datetime,
                )
            ).all()
        )
        span = narrowed_block_span(surviving)

        if span is None:
            deleted_block_ids.append(block.id)
            session.execute(
                delete(TransducerObservationBlock).where(
                    TransducerObservationBlock.id == block.id
                )
            )
            continue

        new_start, new_end = span
        if (new_start, new_end) != (block.start_datetime, block.end_datetime):
            updated_block_ids.append(block.id)
            session.execute(
                update(TransducerObservationBlock)
                .where(TransducerObservationBlock.id == block.id)
                .values(start_datetime=new_start, end_datetime=new_end)
            )

    session.commit()

    return DeletedTransducerObservationsResponse(
        deleted_observation_count=deleted_observation_count,
        deleted_block_ids=deleted_block_ids,
        updated_block_ids=updated_block_ids,
        thing_id=thing_id,
    )


def _created_by(user) -> tuple[str | None, str | None]:
    if isinstance(user, dict):
        return user.get("sub"), user.get("name")
    return None, None


def _stamp_created_by(obj, user) -> None:
    created_by_id, created_by_name = _created_by(user)
    obj.created_by_id = created_by_id
    obj.created_by_name = created_by_name


# ============= EOF =============================================
