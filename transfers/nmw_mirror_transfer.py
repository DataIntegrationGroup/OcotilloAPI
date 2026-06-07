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
"""Load the NM_Wells SQL dump into the ``NMW_*`` 1:1 staging mirror tables.

Phase 1 of the NM_Wells migration (see db/nmw_legacy.py and
docs/nm_wells-migration.md). This is a faithful copy: each source table's CSV
export is read and its rows are inserted into the matching ``NMW_*`` mirror
model with NO transformation beyond type coercion. The Phase 2 transform into
the Ocotillo model is separate.

Generic + data-driven: one ``MirrorSpec`` per (model, source table). Column
handling is derived from each model's ``__table__`` metadata, so adding a new
mirror table requires only a model + a spec entry (no per-table code).

Two row sources, selected at runtime:

1. **SQL Server data dump** (preferred): set ``NMW_SQL_DUMP`` to a ``.sql`` file
   containing ``INSERT [dbo].[tbl_*] (...) VALUES (...)`` statements. Rows are
   streamed and parsed by ``transfers.nmw_sql_dump.iter_table_rows``.
2. **CSV exports** (fallback when ``NMW_SQL_DUMP`` is unset): per-table CSVs read
   with ``transfers.util.read_csv`` (``transfers/data/nma_csv_cache/<table>.csv``
   then GCS ``nma_csv/<table>.csv``).

In both cases the source column names are the original SQL Server names
(OBJECTID, WellDataID, ...), which match the mirror columns' DB names exactly.

Idempotent: rows upsert via ``INSERT ... ON CONFLICT (<pk>) DO NOTHING``.
"""

import itertools
import os
import uuid
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import DateTime, Float, Integer, LargeBinary, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db.nmw_legacy import (
    NMW_GtBhtData,
    NMW_GtBhtHeaders,
    NMW_GtConductivity,
    NMW_GtHeatFlow,
    NMW_GtSumHeatFlow,
    NMW_GtTempDepths,
    NMW_WellHeaders,
    NMW_WellLocations,
    NMW_WellRecords,
    NMW_WellSamples,
    NMW_WellZDatum,
    NMW_WsDstFlowHistory,
    NMW_WsDstFluidProperties,
    NMW_WsDstHeaders,
    NMW_WsDstIntervals,
    NMW_WsDstPressure,
    NMW_WsIntervals,
)
from transfers.logger import logger
from transfers.nmw_sql_dump import iter_table_rows
from transfers.util import read_csv

# Path to a SQL Server data-dump .sql file. When set, rows are parsed from it;
# otherwise the loader falls back to per-table CSV exports.
_SQL_DUMP_ENV = "NMW_SQL_DUMP"
_CHUNK_SIZE = 2000


@dataclass
class MirrorSpec:
    """Maps a mirror model to its NM_Wells source CSV/table name."""

    model: type
    source_table: str


# All NMW_* mirror tables. Order is irrelevant (no enforced cross-table FKs in
# the staging layer), but parents are listed before children for readability.
NMW_MIRROR_SPECS: list[MirrorSpec] = [
    # Main
    MirrorSpec(NMW_WellLocations, "tbl_well_locations"),
    MirrorSpec(NMW_WellHeaders, "tbl_well_headers"),
    MirrorSpec(NMW_WellRecords, "tbl_well_records"),
    MirrorSpec(NMW_WellZDatum, "tbl_well_z_datum"),
    MirrorSpec(NMW_WellSamples, "tbl_well_samples"),
    # Geothermal
    MirrorSpec(NMW_GtBhtHeaders, "tbl_gt_bht_headers"),
    MirrorSpec(NMW_GtBhtData, "tbl_gt_bht_data"),
    MirrorSpec(NMW_WsIntervals, "tbl_ws_intervals"),
    MirrorSpec(NMW_GtConductivity, "tbl_gt_conductivity"),
    MirrorSpec(NMW_GtHeatFlow, "tbl_gt_heat_flow"),
    MirrorSpec(NMW_GtSumHeatFlow, "tbl_gt_sum_heat_flow"),
    MirrorSpec(NMW_GtTempDepths, "tbl_gt_temp_depths"),
    # Drill Stem Tests
    MirrorSpec(NMW_WsDstHeaders, "tbl_ws_dst_headers"),
    MirrorSpec(NMW_WsDstIntervals, "tbl_ws_dst_intervals"),
    MirrorSpec(NMW_WsDstFlowHistory, "tbl_ws_dst_flow_history"),
    MirrorSpec(NMW_WsDstFluidProperties, "tbl_ws_dst_fluid_properties"),
    MirrorSpec(NMW_WsDstPressure, "tbl_ws_dst_pressure"),
]


def _coerce(value, col_type):
    """Coerce a single cell to the Python value for ``col_type`` (or None).

    Treats NaN/NaT as None. (pandas keeps NaN/NaT in typed columns even after a
    ``.where(notnull, None)``, so the missing-value check must happen here.)
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # non-scalar / unhashable: fall through and coerce normally
    if isinstance(col_type, UUID):
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value).strip())
        except (ValueError, AttributeError, TypeError):
            return None
    if isinstance(col_type, (Integer, SmallInteger)):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    if isinstance(col_type, Float):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    if isinstance(col_type, DateTime):
        # read_csv does not parse_dates, so values are typically raw strings.
        # Parse explicitly to avoid driver-dependent insert failures.
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()
        ts = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(ts) else ts.to_pydatetime()
    if isinstance(col_type, String):
        s = str(value)
        return s[: col_type.length] if col_type.length else s
    # Fallback (should not hit for our mirror types).
    return value


def _row_source(spec: MirrorSpec):
    """Return ``(iterator_of_raw_dicts, source_label)`` for a spec.

    SQL dump if ``NMW_SQL_DUMP`` is set, otherwise CSV. Raises on a hard read
    error so the caller can record/skip the table.
    """
    dump = os.getenv(_SQL_DUMP_ENV)
    if dump:
        return iter_table_rows(dump, spec.source_table), f"sql:{os.path.basename(dump)}"
    df = read_csv(spec.source_table)
    return (rec for rec in df.to_dict("records")), "csv"


def _flush(session: Session, model, rows: list[dict], pk_cols: list[str]) -> int:
    """Upsert a batch; return inserted row count."""
    if not rows:
        return 0
    stmt = pg_insert(model).values(rows).on_conflict_do_nothing(index_elements=pk_cols)
    result = session.execute(stmt)
    session.commit()
    return result.rowcount if result.rowcount and result.rowcount > 0 else 0


def _load_table(session: Session, spec: MirrorSpec, limit: int = 0) -> dict:
    """Load one source table (SQL dump or CSV) into its mirror. Stats dict."""
    table = spec.model.__table__
    name = spec.source_table
    # Loadable columns from the model (rowversion/LargeBinary excluded defensively).
    cols = {c.name: c for c in table.columns if not isinstance(c.type, LargeBinary)}
    pk_cols = [c.name for c in table.primary_key]

    try:
        rows_iter, src = _row_source(spec)
    except Exception as e:  # noqa: BLE001 - missing source must not abort the run
        logger.warning("Skipping %s (could not read source): %s", name, e)
        return {"table": name, "skipped": True, "reason": str(e)}

    if limit and limit > 0:
        rows_iter = itertools.islice(rows_iter, limit)

    total = 0
    inserted = 0
    batch: list[dict] = []
    warned_cols = False
    for rec in rows_iter:
        total += 1
        if not warned_cols:
            missing = [n for n in cols if n not in rec]
            if missing:
                logger.warning(
                    "%s: mirror columns absent from source: %s", name, missing
                )
            warned_cols = True
        # NaN/NaT (CSV) and NULL (SQL) normalize to None inside _coerce.
        row = {n: _coerce(rec.get(n), cols[n].type) for n in cols if n in rec}
        if any(row.get(pk) is None for pk in pk_cols):
            continue  # cannot upsert without a PK value
        batch.append(row)
        if len(batch) >= _CHUNK_SIZE:
            inserted += _flush(session, spec.model, batch, pk_cols)
            batch = []
    inserted += _flush(session, spec.model, batch, pk_cols)

    if total == 0:
        logger.warning("Skipping %s (no source rows from %s)", name, src)
        return {"table": name, "skipped": True, "reason": "no rows", "source": src}

    logger.info(
        "Mirror %s -> %s [%s]: %d source rows, %d inserted",
        name,
        table.name,
        src,
        total,
        inserted,
    )
    return {
        "table": name,
        "skipped": False,
        "rows": total,
        "inserted": inserted,
        "source": src,
    }


def transfer_nmw_mirror(session: Session, limit: int = None) -> tuple:
    """Load all NM_Wells source tables into the ``NMW_*`` staging mirror.

    Source is a SQL dump (``NMW_SQL_DUMP``) when set, else per-table CSVs. Same
    ``(session, limit)`` signature as the other session-based transfers. Returns
    ``(num_tables_loaded, total_rows_inserted, errors)``.
    """
    limit = int(limit or 0)
    dump = os.getenv(_SQL_DUMP_ENV)
    if dump:
        if not os.path.exists(dump):
            raise FileNotFoundError(f"{_SQL_DUMP_ENV} set but file not found: {dump}")
        logger.info("NMW mirror source: SQL dump %s", dump)
    else:
        logger.info("NMW mirror source: CSV exports (set %s for a dump)", _SQL_DUMP_ENV)

    results = []
    errors = []
    for spec in NMW_MIRROR_SPECS:
        try:
            results.append(_load_table(session, spec, limit))
        except Exception as e:  # noqa: BLE001 - isolate per-table failures
            logger.critical("NMW mirror load failed for %s: %s", spec.source_table, e)
            session.rollback()
            errors.append({"table": spec.source_table, "error": str(e)})

    loaded = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]
    inserted = sum(r.get("inserted", 0) for r in loaded)
    logger.info(
        "NMW mirror load complete: %d tables loaded, %d skipped, %d rows inserted, "
        "%d errors",
        len(loaded),
        len(skipped),
        inserted,
        len(errors),
    )
    return len(loaded), inserted, errors


# ============= EOF =============================================
