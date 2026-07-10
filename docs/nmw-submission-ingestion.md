# NM_Wells (NMW_) spreadsheet submission ingestion — BDMS-960

Backend workflow that accepts the spreadsheet-based well submission form,
validates it, and loads it into the `NMW_` staging tables for ongoing data
entry.

## Code map

| Layer | File |
| --- | --- |
| API route | [`api/nmw.py`](../api/nmw.py) — `POST /nmw/bulk-upload` |
| Contract | [`schemas/nmw_submission.py`](../schemas/nmw_submission.py) |
| Service | [`services/nmw_submission.py`](../services/nmw_submission.py) |
| Tables (ORM) | [`db/nmw_legacy.py`](../db/nmw_legacy.py) |
| Sequence realign | `reset_nmw_identity_sequences` in [`transfers/nmw_mirror_transfer.py`](../transfers/nmw_mirror_transfer.py) |
| Tests | `tests/test_nmw_submission_schema.py`, `tests/test_nmw_submission_service.py` |

## Transport

`POST /nmw/bulk-upload`, **admin-gated** (`amp_admin_dependency`).

Body is a JSON array of `NMWSubmission` objects — **one object per well**. The
spreadsheet form is parsed client side into this shape; the server does not
parse `.xlsx`. Response `200` on success, `400` on rejection; both bodies share
the same shape (`summary` + `wells` + `validation_errors`).

## Nesting (mirrors the FK chains in `db/nmw_legacy.py`)

```
NMWSubmission
├─ header  (NMW_WellHeaders)          → server generates WellDataID
├─ location (NMW_WellLocations)       ← WellDataID
├─ records[] (NMW_WellRecords)        → server generates RecrdSetID, ← WellDataID
│   ├─ z_data[] (NMW_WellZDatum)      ← RecrdsetID
│   └─ samples[] (NMW_WellSamples)    → server generates SamplSetID, ← RecrdsetID
│       ├─ intervals[] (NMW_WsIntervals)        → gen IntrvlGUID
│       │   ├─ conductivity[] (NMW_GtConductivity)   ← IntrvlGUID
│       │   └─ heat_flow[]   (NMW_GtHeatFlow)         ← IntrvlGUID
│       ├─ bht_headers[] (NMW_GtBhtHeaders)     → gen BHTGUID
│       │   └─ bht_data[] (NMW_GtBhtData)       ← BHTGUID
│       ├─ temp_depths[] (NMW_GtTempDepths)     ← SamplSetID
│       ├─ sum_heat_flow[] (NMW_GtSumHeatFlow)  ← RecrdSetID + SamplSetID
│       └─ dst_headers[] (NMW_WsDstHeaders)     → gen DSTGUID
│           └─ dst_intervals[] (NMW_WsDstIntervals)  → gen DSTInterval
│               ├─ flow_history[]     ← DSTInterval
│               ├─ fluid_properties[] ← DSTInterval
│               └─ pressure[]         ← DSTInterval
└─ sources[] (NMW_Sources)            → standalone, keyed by text source_id
```

## Key generation — the submitter never sends internal keys

* **GUID primary keys** (WellDataID, RecrdSetID, SamplSetID, BHTGUID,
  IntrvlGUID, DSTGUID, DSTInterval) — generated server side (`uuid4`).
* **Integer `OBJECTID` primary keys** — filled by the tables' identity
  sequences (already present: SQLAlchemy created these single-column integer
  PKs as `SERIAL` in the original mirror migration `c0d1e2f3a4b5`; no new
  migration was needed).
* **Foreign-key link columns** — wired from the nesting, not the payload.
* **`GlobalID`** columns — dropped (staging artifact); rejected as input.

Every leaf model carries only the domain columns of its mirror table, and the
contract is strict (`extra="forbid"`) so an unknown/misspelled column is a
`422`, not a silently dropped value.

## Validation & failure semantics — abort the whole batch

The batch is validated before any write; if **any** well fails, nothing is
written and every error is returned (the chemistry-LIMS behavior, not the
per-row water-level one). A submission is accepted or rejected as a unit.

Enforced today:

* Each `header` must carry at least one identifier (`api` or `cur_well_nam`).
* `api` must be unique within the batch and must not already exist in
  `NMW_WellHeaders`.
* Each `sources[]` row must have a `source_id`.

## Example (minimal)

```json
[
  {
    "header": { "api": "30-001-00001", "cur_well_nam": "Deep Well 1", "total_depth": 5000.0 },
    "location": { "lat_dd83": 34.1, "long_dd83": -106.2, "state": "NM" },
    "records": [
      {
        "recrd_class": "geothermal",
        "z_data": [ { "elev_gl": 5000.0 } ],
        "samples": [
          {
            "sample_date": "2020-01-01T00:00:00",
            "bht_headers": [ { "temp_unit": "F", "bht_data": [ { "depth": 100, "bht": 98.6 } ] } ],
            "sum_heat_flow": [ { "heat_flow": 60.0 } ]
          }
        ]
      }
    ],
    "sources": [ { "source_id": "SRC1", "title": "A report" } ]
  }
]
```

Success response:

```json
{
  "summary": { "total_submissions": 1, "total_wells_imported": 1, "total_rows_written": 6, "validation_errors": 0 },
  "wells": [ { "submission_index": 0, "well_data_id": "…uuid…", "api": "30-001-00001", "well_name": "Deep Well 1", "rows_written": 6 } ],
  "validation_errors": []
}
```

## Operational note — sequences after a mirror reload

The `transfers/` mirror load inserts **explicit** OBJECTID values, which does
not advance the identity sequences. After any mirror (re)load, the sequences
must be realigned past the loaded max or the first submitted row collides on
the OBJECTID primary key. `transfer_nmw_mirror` now calls
`reset_nmw_identity_sequences(session)` at the end of every run; call it
directly if OBJECTID rows are loaded by any other path.

## Known gaps / future work

* **No server-side spreadsheet parsing.** Transport is JSON; the form is parsed
  to `NMWSubmission[]` client side. An `.xlsx` upload adapter (openpyxl, as in
  the chemistry LIMS ingest) could be added later.
* **Dedup is API-only.** A well with no `api` is never deduped; there is no
  fuzzy name/location matching. Re-submitting name-only wells creates
  duplicates.
* **Staging only — no transform.** Data lands in `NMW_` unchanged; the mapping
  into the Ocotillo Location/Thing/FieldEvent model
  (see `docs/nm_wells-migration.md`) is a separate phase.
* **No partial success.** By design the whole batch aborts on any error; there
  is no per-well savepoint mode.
```
