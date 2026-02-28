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
Backfill NMA_Radionuclides rows into the Ocotillo Observation schema.

Reads legacy NMA_Radionuclides + NMA_Chemistry_SampleInfo, resolves each
row to an existing Sample (via nma_pk_chemistrysample), and upserts
Observation records keyed on nma_pk_chemistryresults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db.analysis_method import AnalysisMethod
from db.notes import Notes
from db.nma_legacy import NMA_Radionuclides, NMA_Chemistry_SampleInfo
from db.observation import Observation
from db.parameter import Parameter
from db.sample import Sample
from db.engine import session_ctx
from transfers.logger import logger


@dataclass
class BackfillResult:
    inserted: int = 0
    updated: int = 0
    skipped_orphans: int = 0
    errors: list[str] = field(default_factory=list)


def _build_sample_cache(session: Session) -> dict[str, int]:
    """Map Sample.nma_pk_chemistrysample → Sample.id for rows that have the key."""
    rows = session.execute(
        select(Sample.nma_pk_chemistrysample, Sample.id).where(
            Sample.nma_pk_chemistrysample.isnot(None)
        )
    ).all()
    return {str(key).lower(): sid for key, sid in rows}


def _get_or_create_parameter(
    session: Session, parameter_name: str, matrix: str = "water"
) -> Parameter:
    """Return existing Parameter or create a new one.

    The parameter_name must already exist as a LexiconTerm (FK constraint).
    If it doesn't, the insert will fail — callers should ensure vocabulary
    is seeded before running the backfill.
    """
    param = session.execute(
        select(Parameter).where(
            Parameter.parameter_name == parameter_name,
            Parameter.matrix == matrix,
        )
    ).scalar_one_or_none()
    if param is None:
        param = Parameter(
            parameter_name=parameter_name,
            matrix=matrix,
            default_unit="pCi/L",
            release_status="draft",
        )
        session.add(param)
        session.flush()
    return param


def _get_or_create_analysis_method(
    session: Session, method_code: str
) -> AnalysisMethod:
    """Return existing AnalysisMethod or create a new one."""
    am = session.execute(
        select(AnalysisMethod).where(
            AnalysisMethod.analysis_method_code == method_code
        )
    ).scalar_one_or_none()
    if am is None:
        am = AnalysisMethod(
            analysis_method_code=method_code,
            analysis_method_name=method_code,
            release_status="draft",
        )
        session.add(am)
        session.flush()
    return am


def _resolve_detect_flag(symbol: str | None, value: float | None) -> bool | None:
    """Map legacy Symbol qualifier to detect_flag.

    Rules:
    - Symbol == '<'  → False  (below detection limit)
    - Symbol is non-null and != '<' → True (detected, other qualifier)
    - Symbol is null and value is not None → True (detected, no qualifier)
    - Symbol is null and value is None → None (unknown)
    """
    if symbol is not None:
        return symbol != "<"
    if value is not None:
        return True
    return None


def _backfill_radionuclides_impl(session: Session) -> BackfillResult:
    result = BackfillResult()

    sample_cache = _build_sample_cache(session)
    logger.info("Sample cache built with %d entries", len(sample_cache))

    # Track existing observation keys so we know insert vs update
    existing_keys = set(
        row[0]
        for row in session.execute(
            select(Observation.nma_pk_chemistryresults).where(
                Observation.nma_pk_chemistryresults.isnot(None)
            )
        ).all()
    )

    # Query all radionuclides joined with sample info for nma_sample_pt_id
    legacy_rows = session.execute(
        select(NMA_Radionuclides, NMA_Chemistry_SampleInfo.nma_sample_pt_id).join(
            NMA_Chemistry_SampleInfo,
            NMA_Radionuclides.chemistry_sample_info_id
            == NMA_Chemistry_SampleInfo.id,
        )
    ).all()

    logger.info("Processing %d legacy Radionuclides rows", len(legacy_rows))

    for row, nma_sample_pt_id in legacy_rows:
        global_id_str = str(row.nma_global_id).lower() if row.nma_global_id else None
        if global_id_str is None:
            result.errors.append(f"Row id={row.id} has no nma_global_id")
            continue

        # Resolve Sample via nma_pk_chemistrysample
        sample_pt_key = str(nma_sample_pt_id).lower() if nma_sample_pt_id else None
        if sample_pt_key is None or sample_pt_key not in sample_cache:
            result.skipped_orphans += 1
            logger.debug(
                "Skipping Radionuclide GlobalID=%s — no matching Sample for SamplePtID=%s",
                global_id_str,
                sample_pt_key,
            )
            continue

        sample_id = sample_cache[sample_pt_key]

        analyte = row.analyte
        if not analyte:
            result.errors.append(
                f"Row GlobalID={global_id_str} has no Analyte — skipping"
            )
            continue

        # Build observation_datetime
        obs_dt = row.analysis_date
        if obs_dt is not None:
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
        else:
            result.errors.append(
                f"Row GlobalID={global_id_str} has no AnalysisDate — skipping"
            )
            continue

        # Per-row savepoint so one bad row doesn't abort the entire backfill
        savepoint = session.begin_nested()
        try:
            # Get-or-create Parameter
            param = _get_or_create_parameter(session, analyte, "water")

            # Get-or-create AnalysisMethod
            analysis_method_id = None
            if row.analysis_method:
                am = _get_or_create_analysis_method(session, row.analysis_method)
                analysis_method_id = am.id

            # Resolve detect_flag
            detect_flag = _resolve_detect_flag(row.symbol, row.sample_value)

            # Determine unit
            unit = row.units if row.units else "pCi/L"

            # Upsert Observation
            obs_values = {
                "nma_pk_chemistryresults": global_id_str,
                "sample_id": sample_id,
                "parameter_id": param.id,
                "analysis_method_id": analysis_method_id,
                "observation_datetime": obs_dt,
                "value": row.sample_value,
                "unit": unit,
                "detect_flag": detect_flag,
                "uncertainty": row.uncertainty,
                "analysis_agency": row.analyses_agency,
                "release_status": "draft",
            }

            stmt = pg_insert(Observation).values(**obs_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["nma_pk_chemistryresults"],
                set_={
                    "sample_id": stmt.excluded.sample_id,
                    "parameter_id": stmt.excluded.parameter_id,
                    "analysis_method_id": stmt.excluded.analysis_method_id,
                    "observation_datetime": stmt.excluded.observation_datetime,
                    "value": stmt.excluded.value,
                    "unit": stmt.excluded.unit,
                    "detect_flag": stmt.excluded.detect_flag,
                    "uncertainty": stmt.excluded.uncertainty,
                    "analysis_agency": stmt.excluded.analysis_agency,
                },
            )
            session.execute(stmt)

            if global_id_str in existing_keys:
                result.updated += 1
            else:
                result.inserted += 1
                existing_keys.add(global_id_str)

            # Update Sample volume/volume_unit if present on legacy row
            if row.volume is not None or row.volume_unit is not None:
                sample = session.get(Sample, sample_id)
                if sample:
                    if row.volume is not None:
                        sample.volume = float(row.volume)
                    if row.volume_unit is not None:
                        sample.volume_unit = row.volume_unit

            # Create Notes if present
            if row.notes:
                obs = session.execute(
                    select(Observation).where(
                        Observation.nma_pk_chemistryresults == global_id_str
                    )
                ).scalar_one_or_none()

                if obs is None:
                    result.errors.append(
                        f"Row GlobalID={global_id_str}: upserted Observation not found "
                        f"when creating Notes — skipping note"
                    )
                else:
                    existing_note = session.execute(
                        select(Notes).where(
                            Notes.target_id == obs.id,
                            Notes.target_table == "observation",
                            Notes.note_type == "Chemistry Observation",
                            Notes.content == row.notes,
                        )
                    ).scalar_one_or_none()

                    if existing_note is None:
                        note = Notes(
                            target_id=obs.id,
                            target_table="observation",
                            note_type="Chemistry Observation",
                            content=row.notes,
                            release_status="draft",
                        )
                        session.add(note)

            savepoint.commit()
        except Exception as exc:
            savepoint.rollback()
            logger.exception("Row GlobalID=%s failed", global_id_str)
            result.errors.append(
                f"Row GlobalID={global_id_str}: {type(exc).__name__}: {exc}"
            )
            continue

    session.commit()
    logger.info(
        "Backfill complete: inserted=%d updated=%d skipped_orphans=%d errors=%d",
        result.inserted,
        result.updated,
        result.skipped_orphans,
        len(result.errors),
    )
    return result


def backfill_radionuclides() -> BackfillResult:
    """Top-level runner for the radionuclides backfill."""
    with session_ctx() as session:
        return _backfill_radionuclides_impl(session)


# ============= EOF =============================================
