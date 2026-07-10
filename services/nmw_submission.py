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
"""Bulk ingestion of NM_Wells (NMW_) submissions (BDMS-960).

Takes a validated ``list[NMWSubmission]`` (the JSON body of
``POST /nmw/bulk-upload``) and loads it into the ``NMW_`` staging tables.

Behavior (mirrors the chemistry-LIMS ingest, not the per-row water-level one):
the whole batch is validated first and, if ANY well fails, nothing is written
and every error is returned. This keeps a submission atomic — a spreadsheet is
accepted or rejected as a unit.

Key generation:
* GUID PKs (WellDataID, RecrdSetID, SamplSetID, BHTGUID, IntrvlGUID, DSTGUID,
  DSTInterval) are ``uuid4()`` generated here.
* Integer OBJECTID PKs are left unset and filled by database identity
  sequences (migration ``<id>_nmw_objectid_identity``).
* FK link columns are wired from the nesting.

Rows are inserted top-down with a ``flush`` after each parent level because the
staging tables carry real (non-deferred) FK constraints, so a parent row must
hit the database before its children.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import (
    NMW_WellHeaders,
    NMW_WellLocations,
    NMW_WellRecords,
    NMW_WellZDatum,
    NMW_WellSamples,
    NMW_WsIntervals,
    NMW_GtConductivity,
    NMW_GtHeatFlow,
    NMW_GtBhtHeaders,
    NMW_GtBhtData,
    NMW_GtTempDepths,
    NMW_GtSumHeatFlow,
    NMW_WsDstHeaders,
    NMW_WsDstIntervals,
    NMW_WsDstFlowHistory,
    NMW_WsDstFluidProperties,
    NMW_WsDstPressure,
    NMW_Sources,
)
from db.engine import session_ctx
from schemas.nmw_submission import NMWSubmission


@dataclass
class BulkUploadResult:
    exit_code: int
    stdout: str
    stderr: str
    payload: dict[str, Any]


@dataclass
class _PersistedWell:
    submission_index: int
    well_data_id: UUID
    api: str | None
    well_name: str | None
    rows_written: int


@dataclass
class _Counter:
    """Running row count for one well (mutated as the subtree is built)."""

    value: int = 0


# ---------------------------------------------------------------------------
# Validation (read-only; abort-whole-batch semantics)
# ---------------------------------------------------------------------------


def _existing_apis(session: Session, apis: set[str]) -> set[str]:
    if not apis:
        return set()
    rows = session.execute(
        select(NMW_WellHeaders.api).where(NMW_WellHeaders.api.in_(apis))
    ).all()
    return {row[0] for row in rows if row[0] is not None}


def _validate(session: Session, submissions: list[NMWSubmission]) -> list[str]:
    """Return a list of human-readable errors; empty means the batch is safe
    to write. No rows are inserted here."""

    errors: list[str] = []

    if not submissions:
        return ["No submissions provided."]

    apis_in_batch: dict[str, int] = {}
    for index, submission in enumerate(submissions):
        header = submission.header
        api = (header.api or "").strip() or None
        name = (header.cur_well_nam or "").strip() or None

        if api is None and name is None:
            errors.append(
                f"Well {index}: header must include at least one of "
                f"'api' or 'cur_well_nam'."
            )

        if api is not None:
            if api in apis_in_batch:
                errors.append(
                    f"Well {index}: duplicate api '{api}' also submitted as "
                    f"well {apis_in_batch[api]} in this batch."
                )
            else:
                apis_in_batch[api] = index

        # SourceID is the join key for NMW_Sources rows.
        for src_index, source in enumerate(submission.sources):
            if not (source.source_id or "").strip():
                errors.append(
                    f"Well {index}: sources[{src_index}] is missing 'source_id'."
                )

    existing = _existing_apis(session, set(apis_in_batch))
    for api in sorted(existing):
        errors.append(
            f"Well {apis_in_batch[api]}: api '{api}' already exists in "
            f"NMW_WellHeaders."
        )

    return errors


# ---------------------------------------------------------------------------
# Persistence (only reached when validation is clean)
# ---------------------------------------------------------------------------


def _persist_submission(
    session: Session, index: int, submission: NMWSubmission
) -> _PersistedWell:
    counter = _Counter()
    well_data_id = uuid4()

    header = submission.header
    session.add(NMW_WellHeaders(well_data_id=well_data_id, **header.model_dump()))
    counter.value += 1

    if submission.location is not None:
        session.add(
            NMW_WellLocations(
                well_data_id=well_data_id, **submission.location.model_dump()
            )
        )
        counter.value += 1

    for source in submission.sources:
        session.add(NMW_Sources(**source.model_dump()))
        counter.value += 1

    # header (and location/sources) must exist before records reference it.
    session.flush()

    for record in submission.records:
        _persist_record(session, well_data_id, record, counter)

    return _PersistedWell(
        submission_index=index,
        well_data_id=well_data_id,
        api=(header.api or "").strip() or None,
        well_name=(header.cur_well_nam or "").strip() or None,
        rows_written=counter.value,
    )


def _persist_record(
    session: Session, well_data_id: UUID, record, counter: _Counter
) -> None:
    recrd_set_id = uuid4()
    session.add(
        NMW_WellRecords(
            recrd_set_id=recrd_set_id,
            well_data_id=well_data_id,
            **record.model_dump(exclude={"z_data", "samples"}),
        )
    )
    counter.value += 1
    session.flush()

    for z_datum in record.z_data:
        session.add(NMW_WellZDatum(recrdset_id=recrd_set_id, **z_datum.model_dump()))
        counter.value += 1

    for sample in record.samples:
        _persist_sample(session, recrd_set_id, sample, counter)


def _persist_sample(
    session: Session, recrd_set_id: UUID, sample, counter: _Counter
) -> None:
    sampl_set_id = uuid4()
    session.add(
        NMW_WellSamples(
            sampl_set_id=sampl_set_id,
            recrdset_id=recrd_set_id,
            **sample.model_dump(
                exclude={
                    "intervals",
                    "bht_headers",
                    "temp_depths",
                    "sum_heat_flow",
                    "dst_headers",
                }
            ),
        )
    )
    counter.value += 1
    session.flush()

    for interval in sample.intervals:
        intrvl_guid = uuid4()
        session.add(
            NMW_WsIntervals(
                intrvl_guid=intrvl_guid,
                sampl_set_id=sampl_set_id,
                **interval.model_dump(exclude={"conductivity", "heat_flow"}),
            )
        )
        counter.value += 1
        session.flush()

        for conductivity in interval.conductivity:
            session.add(
                NMW_GtConductivity(intrvl_guid=intrvl_guid, **conductivity.model_dump())
            )
            counter.value += 1
        for heat_flow in interval.heat_flow:
            session.add(
                NMW_GtHeatFlow(intrvl_guid=intrvl_guid, **heat_flow.model_dump())
            )
            counter.value += 1

    for bht_header in sample.bht_headers:
        bht_guid = uuid4()
        session.add(
            NMW_GtBhtHeaders(
                bht_guid=bht_guid,
                sampl_set_id=sampl_set_id,
                **bht_header.model_dump(exclude={"bht_data"}),
            )
        )
        counter.value += 1
        session.flush()

        for bht_data in bht_header.bht_data:
            session.add(NMW_GtBhtData(bht_guid=bht_guid, **bht_data.model_dump()))
            counter.value += 1

    for temp_depth in sample.temp_depths:
        session.add(
            NMW_GtTempDepths(sampl_set_id=sampl_set_id, **temp_depth.model_dump())
        )
        counter.value += 1

    for sum_heat_flow in sample.sum_heat_flow:
        session.add(
            NMW_GtSumHeatFlow(
                recrd_set_id=recrd_set_id,
                sampl_set_id=sampl_set_id,
                **sum_heat_flow.model_dump(),
            )
        )
        counter.value += 1

    for dst_header in sample.dst_headers:
        _persist_dst_header(session, sampl_set_id, dst_header, counter)


def _persist_dst_header(
    session: Session, sampl_set_id: UUID, dst_header, counter: _Counter
) -> None:
    dst_guid = uuid4()
    session.add(
        NMW_WsDstHeaders(
            dst_guid=dst_guid,
            sampl_set_id=sampl_set_id,
            **dst_header.model_dump(exclude={"dst_intervals"}),
        )
    )
    counter.value += 1
    session.flush()

    for dst_interval in dst_header.dst_intervals:
        dst_interval_id = uuid4()
        session.add(
            NMW_WsDstIntervals(
                dst_interval=dst_interval_id,
                dst_guid=dst_guid,
                **dst_interval.model_dump(
                    exclude={"flow_history", "fluid_properties", "pressure"}
                ),
            )
        )
        counter.value += 1
        session.flush()

        for flow in dst_interval.flow_history:
            session.add(
                NMW_WsDstFlowHistory(dst_interval=dst_interval_id, **flow.model_dump())
            )
            counter.value += 1
        for fluid in dst_interval.fluid_properties:
            session.add(
                NMW_WsDstFluidProperties(
                    dst_interval=dst_interval_id, **fluid.model_dump()
                )
            )
            counter.value += 1
        for pressure in dst_interval.pressure:
            session.add(
                NMW_WsDstPressure(dst_interval=dst_interval_id, **pressure.model_dump())
            )
            counter.value += 1


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _build_payload(
    submissions: list[NMWSubmission],
    persisted: list[_PersistedWell],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "summary": {
            "total_submissions": len(submissions),
            "total_wells_imported": len(persisted),
            "total_rows_written": sum(p.rows_written for p in persisted),
            "validation_errors": len(errors),
        },
        "wells": [
            {
                "submission_index": p.submission_index,
                "well_data_id": str(p.well_data_id),
                "api": p.api,
                "well_name": p.well_name,
                "rows_written": p.rows_written,
            }
            for p in persisted
        ],
        "validation_errors": errors,
    }


def bulk_upload_nmw(
    submissions: list[NMWSubmission], *, pretty_json: bool = False
) -> BulkUploadResult:
    """Validate and load a batch of NMW_ well submissions.

    Returns a ``BulkUploadResult`` whose ``exit_code`` is 0 on success and 1 if
    the batch was rejected (validation errors) or a write failed. On any
    failure NOTHING is written.
    """

    errors: list[str] = []
    persisted: list[_PersistedWell] = []

    with session_ctx() as session:
        errors = _validate(session, submissions)

        if not errors:
            try:
                for index, submission in enumerate(submissions):
                    persisted.append(_persist_submission(session, index, submission))
                session.commit()
            except Exception as exc:  # noqa: BLE001 - surface as batch error
                session.rollback()
                persisted = []
                errors.append(f"Write failed, no rows committed: {exc}")

    payload = _build_payload(submissions, persisted, errors)
    stdout = json.dumps(payload, indent=2 if pretty_json else None, default=str)
    exit_code = 0 if not errors else 1
    stderr = "" if exit_code == 0 else "\n".join(errors)

    return BulkUploadResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        payload=payload,
    )


# ============= EOF =============================================
