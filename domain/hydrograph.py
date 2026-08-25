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
Rules for publishing and deleting corrected transducer series.

The hydrograph corrector (OcotilloUI) uploads a whole corrected file as one
block. These functions decide the block's span, whether it collides with what is
already stored, which deployment it belongs to, and what survives a range
delete. They take plain values -- no session, no request -- so the awkward parts
(inclusive vs half-open overlap, a block narrowed to a single instant) can be
tested without a database.

**Overlap is inclusive on both bounds here**, which differs from
``TransducerObservationBlock.overlaps`` on the model. That method is half-open,
so two blocks sharing an endpoint do not "overlap". The block *reader*
(``services.observation_helper.get_transducer_observations``) matches an
observation to a block with ``start <= t <= end``, so two blocks sharing an
endpoint both claim any reading at that instant and the reader picks whichever
sorts first. That ambiguity is the thing the publish conflict check exists to
prevent, so the check uses the reader's inclusive bounds rather than the
model's.
"""

from datetime import date, datetime

# One request per logger file is the expected shape; a 90-day file at a 6-hour
# cadence is 360 rows. The cap is three orders of magnitude above that, high
# enough never to reject real work and low enough that a runaway client cannot
# ask the server to build a million-row transaction.
MAX_MEASUREMENTS = 100_000


class HydrographError(ValueError):
    """Base for publish/delete rule violations. A ValueError, per ADR4."""


def derive_block_span(
    observation_datetimes: list[datetime],
) -> tuple[datetime, datetime]:
    """
    The block's span is the extent of its readings.

    The client does not send ``start_datetime``/``end_datetime``: a span wider
    than the data would claim coverage the block does not have, and the reader
    would attach unrelated readings to it.
    """
    if not observation_datetimes:
        raise HydrographError("A block needs at least one measurement")

    return min(observation_datetimes), max(observation_datetimes)


def first_out_of_order_index(observation_datetimes: list[datetime]) -> int | None:
    """
    Index of the first timestamp that does not advance on its predecessor.

    Strictly increasing, so a repeated timestamp is reported too -- the storage
    constraint is one reading per deployment/parameter/instant, and a duplicate
    inside one request would abort the whole transaction on insert rather than
    be reported against the row that caused it.

    Returns the index so the caller can point at the offending row.
    """
    for index in range(1, len(observation_datetimes)):
        if observation_datetimes[index] <= observation_datetimes[index - 1]:
            return index

    return None


def spans_overlap(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    """Whether two closed intervals share any instant. See the module docstring."""
    return not (a_end < b_start or a_start > b_end)


def resolve_deployment_id(
    candidates: list[tuple[int, date | None, date | None]],
    span_start: datetime,
    span_end: datetime,
) -> int:
    """
    Pick the deployment whose installation period covers a block's span.

    ``candidates`` are ``(deployment_id, installation_date, removal_date)`` for
    one well. A NULL installation date reads as "always installed" and a NULL
    removal date as "still installed" -- that is how the column is used, and
    treating an unrecorded date as a closed boundary would exclude the
    deployments most likely to be current.

    Ambiguity is an error rather than a choice: two overlapping deployments mean
    two sensors could have produced the file, and guessing attributes readings to
    hardware that did not record them.
    """
    span_start_date = span_start.date()
    span_end_date = span_end.date()

    covering = [
        deployment_id
        for deployment_id, installation_date, removal_date in candidates
        if (installation_date is None or installation_date <= span_start_date)
        and (removal_date is None or removal_date >= span_end_date)
    ]

    if not covering:
        raise HydrographError(
            f"No deployment covers {span_start_date} to {span_end_date}; "
            "send deployment_id explicitly"
        )
    if len(covering) > 1:
        joined = ", ".join(str(deployment_id) for deployment_id in sorted(covering))
        raise HydrographError(
            f"{len(covering)} deployments cover {span_start_date} to "
            f"{span_end_date} ({joined}); send deployment_id explicitly"
        )

    return covering[0]


def narrowed_block_span(
    surviving_datetimes: list[datetime],
) -> tuple[datetime, datetime] | None:
    """
    What a block's span becomes after some of its readings are deleted.

    ``None`` means nothing survived and the block should go with them -- an
    empty block is invisible to the reader and would only ever collide with a
    later publish.
    """
    if not surviving_datetimes:
        return None

    return min(surviving_datetimes), max(surviving_datetimes)


def validate_delete_range(start_time: datetime, end_time: datetime) -> None:
    """
    Reject a delete range that cannot be meant.

    Both bounds are required by the route signature; this covers the ordering.
    An inverted range is not silently reordered, because the operation is
    irreversible and a transposed pair is as likely to be the wrong pair as the
    right one written backwards.
    """
    if end_time <= start_time:
        raise HydrographError("end_time must be after start_time")


# ============= EOF =============================================
