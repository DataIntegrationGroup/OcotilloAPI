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
"""Load the legacy NM_Wells ``ref_*`` reference tables into the lexicon.

The planning workbook ("NM_Wells + Subsurface library.xlsx", sheet 1) flags the
``ref_*`` tables as "Add to lexicon". Each ref table is a small code/description
lookup; this transfer loads its rows as ``LexiconTerm`` rows and links them to a
``LexiconCategory`` named after the table (``ref_well_class`` -> ``well_class``).

Idempotent: mirrors ``core.initializers.init_lexicon`` — categories and terms
upsert via ``ON CONFLICT DO NOTHING`` (both ``name``/``term`` are unique);
term<->category associations are inserted only when missing (no unique
constraint exists on that table).

Row source is the same as the mirror loader: a SQL Server data dump when
``NMW_SQL_DUMP`` is set (parsed by ``transfers.nmw_sql_dump.iter_table_rows``),
otherwise per-table CSV exports via ``transfers.util.read_csv``.

NOTE(columns): the ref tables' actual column names are not in the workbook, so
term/definition columns are AUTO-DETECTED per table (see ``_pick_columns``). If
auto-detection is wrong for a table, set ``term_col`` / ``definition_col``
explicitly on its ``RefTableSpec`` below. The chosen columns are logged.

NOTE(LU_*): the Subsurface Library ``LU_*`` lookups (LU_EnteredBy, LU_LogType,
LU_Status, LU_Type_Wellheader, LU_WorkType) are also "Add to lexicon"; add them
to ``REFERENCE_TABLE_SPECS`` once their CSVs are available.
"""

import itertools
import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db import (
    LexiconCategory,
    LexiconTerm,
    LexiconTermCategoryAssociation,
)
from transfers.logger import logger
from transfers.nmw_sql_dump import iter_table_rows
from transfers.util import read_csv

# Same source selector as the mirror loader: a SQL Server data dump when
# NMW_SQL_DUMP is set, otherwise per-table CSV exports.
_SQL_DUMP_ENV = "NMW_SQL_DUMP"
# lexicon_term.term (and its FK targets) is String(100).
_TERM_MAX_LEN = 100

# Column-name hints for auto-detecting the code/term vs definition columns.
_META_COLS = {"objectid", "ssma_timestamp", "globalid", "id", "import_id"}
_TERM_HINTS = ("code", "abbr", "symbol", "letter", "key", "short")
_DEF_HINTS = (
    "description",
    "desc",
    "definition",
    "meaning",
    "label",
    "name",
    "long",
    "title",
    "value",
    "text",
)


@dataclass
class RefTableSpec:
    """One legacy ref table -> one lexicon category.

    term_col / definition_col are optional overrides; when None the columns are
    auto-detected from the CSV header.
    """

    source_table: str
    category: str
    term_col: Optional[str] = None
    definition_col: Optional[str] = None
    description: Optional[str] = None


def _spec(table: str) -> RefTableSpec:
    """Build a spec with category = table name minus the ``ref_`` prefix."""
    category = table[4:] if table.startswith("ref_") else table
    return RefTableSpec(
        source_table=table,
        category=category,
        description=f"Imported from NM_Wells {table}",
    )


# All ref_* tables marked "Add to lexicon" in the workbook (sheet 1).
# ref_nm_quads (Review, ~2k rows) is intentionally excluded; add/remove specs
# here as the mapping is refined.
REFERENCE_TABLE_SPECS: list[RefTableSpec] = [
    _spec(t)
    for t in (
        "ref_altitude_datums",
        "ref_altitude_methods",
        "ref_basins",
        "ref_coordinate_accuracy",
        "ref_coordinate_datum",
        "ref_coordinate_method",
        "ref_county",
        "ref_data_reliability",
        "ref_date_drilled",
        "ref_depth_types",
        "ref_display_scales",
        "ref_ground_levels",
        "ref_gt_data_sources",
        "ref_gt_well_types",
        "ref_ign_comps",
        "ref_indurations",
        "ref_initials",
        "ref_length_units",
        "ref_lith_class",
        "ref_lith_types",
        "ref_ll_sources",
        "ref_mm_facies",
        "ref_perforation_types",
        "ref_porosity_methods",
        "ref_pres_units",
        "ref_prod_meth_quality",
        "ref_prod_methods",
        "ref_prod_units",
        "ref_sample_class",
        "ref_sample_types",
        "ref_states",
        "ref_textures",
        "ref_unit_basis",
        "ref_unit_conductivity",
        "ref_unit_depths",
        "ref_unit_gradients",
        "ref_unit_heat_flow",
        "ref_unit_letters",
        "ref_unit_temps",
        "ref_well_action_class",
        "ref_well_class",
        "ref_well_commodity",
        "ref_well_log_class",
        "ref_well_orientations",
        "ref_well_record_class",
        "ref_well_status",
        "ref_well_types",
        "ref_work_types",
        "ref_xy_units",
    )
]


def _pick_columns(columns: list[str], spec: RefTableSpec) -> tuple[str, str]:
    """Resolve (term_col, definition_col) for a ref table.

    Honors explicit overrides on the spec, else auto-detects from the column
    names using name hints, ignoring meta columns (OBJECTID, GlobalID, ...).
    """
    cols = [c for c in columns if str(c).strip().lower() not in _META_COLS]
    if not cols:
        cols = list(columns)
    low = {c: str(c).strip().lower() for c in cols}

    term_col = spec.term_col
    if term_col is None:
        term_col = next(
            (c for c in cols if any(h in low[c] for h in _TERM_HINTS)), cols[0]
        )

    def_col = spec.definition_col
    if def_col is None:
        def_col = next(
            (c for c in cols if c != term_col and any(h in low[c] for h in _DEF_HINTS)),
            None,
        )
        if def_col is None:
            def_col = cols[1] if len(cols) > 1 else term_col

    return term_col, def_col


def _clean(value) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    return s or None


def _get_or_create_category(session: Session, spec: RefTableSpec) -> int:
    """Return the lexicon_category.id for the spec, creating it if needed."""
    cat_id = session.execute(
        select(LexiconCategory.id).where(LexiconCategory.name == spec.category)
    ).scalar_one_or_none()
    if cat_id is not None:
        return cat_id

    session.execute(
        pg_insert(LexiconCategory)
        .values(name=spec.category, description=spec.description)
        .on_conflict_do_nothing(index_elements=["name"])
    )
    session.commit()
    return session.execute(
        select(LexiconCategory.id).where(LexiconCategory.name == spec.category)
    ).scalar_one()


def _iter_source_rows(table: str, limit: int = 0):
    """Yield raw ``{column: value}`` dicts for a ref table.

    SQL dump when NMW_SQL_DUMP is set (same source as the mirror loader),
    otherwise per-table CSV. Mirrors transfers.nmw_mirror_transfer._row_source.
    """
    dump = os.getenv(_SQL_DUMP_ENV)
    if dump:
        it = iter_table_rows(dump, table)
    else:
        df = read_csv(table)
        it = (rec for rec in df.to_dict("records"))
    if limit and limit > 0:
        it = itertools.islice(it, limit)
    return it


def _transfer_one(session: Session, spec: RefTableSpec, limit: int = 0) -> dict:
    """Load a single ref table into the lexicon. Returns a stats dict."""
    try:
        rows = list(_iter_source_rows(spec.source_table, limit))
    except Exception as e:  # noqa: BLE001 - missing source should not abort the run
        logger.warning("Skipping %s (could not read source): %s", spec.source_table, e)
        return {"table": spec.source_table, "skipped": True, "reason": str(e)}

    if not rows:
        logger.warning("Skipping %s (empty)", spec.source_table)
        return {"table": spec.source_table, "skipped": True, "reason": "empty"}

    # Column names from the union of row keys (CSV rows and SSMS INSERTs are
    # column-consistent, but be defensive).
    columns: list[str] = []
    seen = set()
    for rec in rows:
        for k in rec:
            if k not in seen:
                seen.add(k)
                columns.append(k)

    term_col, def_col = _pick_columns(columns, spec)
    logger.info(
        "%s -> category=%s term_col=%s definition_col=%s (%d rows)",
        spec.source_table,
        spec.category,
        term_col,
        def_col,
        len(rows),
    )

    category_id = _get_or_create_category(session, spec)

    # Build unique (term -> definition) map, dropping empties and overlong terms.
    term_defs: dict[str, str] = {}
    truncated = 0
    for rec in rows:
        term = _clean(rec.get(term_col))
        if term is None:
            continue
        if len(term) > _TERM_MAX_LEN:
            term = term[:_TERM_MAX_LEN]
            truncated += 1
        definition = _clean(rec.get(def_col)) or term
        term_defs.setdefault(term, definition)

    if not term_defs:
        logger.warning("Skipping %s (no usable terms)", spec.source_table)
        return {"table": spec.source_table, "skipped": True, "reason": "no terms"}
    if truncated:
        logger.warning(
            "%s: truncated %d term(s) to %d chars",
            spec.source_table,
            truncated,
            _TERM_MAX_LEN,
        )

    term_names = list(term_defs)
    existing_terms = dict(
        session.execute(
            select(LexiconTerm.term, LexiconTerm.id).where(
                LexiconTerm.term.in_(term_names)
            )
        ).all()
    )
    new_rows = [
        {"term": t, "definition": d}
        for t, d in term_defs.items()
        if t not in existing_terms
    ]
    if new_rows:
        session.execute(
            pg_insert(LexiconTerm)
            .values(new_rows)
            .on_conflict_do_nothing(index_elements=["term"])
        )
        session.commit()
        existing_terms = dict(
            session.execute(
                select(LexiconTerm.term, LexiconTerm.id).where(
                    LexiconTerm.term.in_(term_names)
                )
            ).all()
        )

    term_ids = [tid for tid in existing_terms.values() if tid is not None]
    existing_links = set()
    if term_ids:
        existing_links = set(
            session.execute(
                select(LexiconTermCategoryAssociation.term_id).where(
                    LexiconTermCategoryAssociation.category_id == category_id,
                    LexiconTermCategoryAssociation.term_id.in_(term_ids),
                )
            ).scalars()
        )

    assoc_rows = [
        {"term_id": tid, "category_id": category_id}
        for tid in term_ids
        if tid not in existing_links
    ]
    if assoc_rows:
        session.execute(pg_insert(LexiconTermCategoryAssociation).values(assoc_rows))
        session.commit()

    return {
        "table": spec.source_table,
        "skipped": False,
        "rows": len(rows),
        "terms": len(term_defs),
        "created_terms": len(new_rows),
        "linked": len(assoc_rows),
    }


def transfer_reference_tables(session: Session, limit: int = None) -> tuple:
    """Foundational transfer: load all ``ref_*`` tables into the lexicon.

    Same ``(session, limit)`` signature as the other foundational transfers
    (aquifer systems, geologic formations). Returns
    ``(num_tables, total_created_terms, errors)``.
    """
    limit = int(limit or 0)
    dump = os.getenv(_SQL_DUMP_ENV)
    if dump:
        if not os.path.exists(dump):
            raise FileNotFoundError(f"{_SQL_DUMP_ENV} set but file not found: {dump}")
        logger.info("Reference lexicon source: SQL dump %s", dump)
    else:
        logger.info(
            "Reference lexicon source: CSV exports (set %s for a dump)", _SQL_DUMP_ENV
        )

    results = []
    errors = []
    for spec in REFERENCE_TABLE_SPECS:
        try:
            results.append(_transfer_one(session, spec, limit))
        except Exception as e:  # noqa: BLE001 - isolate per-table failures
            logger.critical(
                "Reference lexicon transfer failed for %s: %s", spec.source_table, e
            )
            session.rollback()
            errors.append({"table": spec.source_table, "error": str(e)})

    loaded = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]
    created = sum(r.get("created_terms", 0) for r in loaded)
    linked = sum(r.get("linked", 0) for r in loaded)
    logger.info(
        "Reference lexicon transfer complete: %d tables loaded, %d skipped, "
        "%d terms created, %d associations, %d errors",
        len(loaded),
        len(skipped),
        created,
        linked,
        len(errors),
    )
    return len(loaded), created, errors


# ============= EOF =============================================
