# SPEC — BDMS-826 NM_Wells migrations core

Distilled from branch `feature/BDMS-826-NMW-migrations-core` (PR #738), POC of #686.
Status: Phase-1 impl landed in branch, NOT reviewed/tested. Spec captures built state + remaining work.

## §G — goal

1:1 staging mirror of legacy NM_Wells (SQL Server) into Postgres `NMW_*` tables.
Plus geothermal OGC API layers over mirror data. Phase-1 only: faithful copy, no transform to Ocotillo model.

## §C — constraints

- C1. Mirror = column-for-column copy. Original col names, types, PKs preserved. `SSMA_TimeStamp` dropped.
- C2. Phase split: P1 = land `NMW_*` mirror + OGC views (this branch). P2 = transform mirror → Ocotillo model (Location→Thing→Event→Sample→Observation). P2 NOT built; per-col targets + lexicon maps flagged inline.
- C3. Follow `db/nma_legacy.py` (NM_Aquifer) mirror convention.
- C4. Standalone orchestrator. Do NOT extend deprecated `transfers/transfer.py` (NM_Aquifer driver).
- C5. Tables load parent→child (FK order). Mirror load truncate+COPY (dump) or INSERT ON CONFLICT DO NOTHING (CSV). No upsert.
- C6. Coords/geom stay WGS84 4326 per project std.
- C7. Migrations idempotent, reversible (alembic up/down).

## §I — interfaces

- I.cli — `python -m transfers.transfer_geothermal` — runs ref→lexicon then NMW mirror load then refresh matviews.
- I.env — `NMW_SQL_DUMP` (dump path; else CSV), `NMW_CSV_DIR`, `TRANSFER_LIMIT`, `TRANSFER_GEOTHERMAL_REFERENCE` (def 1), `TRANSFER_NMW_MIRROR` (def 1). Export: `NMW_HOST/USER/PASSWORD/PORT/DATABASE`.
- I.export — `transfers/export_nmw_csvs.py` — pymssql dump SQL Server → `transfers/data/nma_csv_cache/<table>.csv`.
- I.db — 18 `NMW_*` mirror tables (`db/nmw_legacy.py`), PK verified vs dump DDL.
- I.migrations — `c0d1e2f3a4b5` (tables+FK), `d1e2f3a4b5c6` (per-well views), `e2f3a4b5c6d7` (measurement views). Linear chain (rebased onto staging head): x2y3z4a5b6c7 → c0 → d1 → e2.
- I.ogc — 6 new collections in `core/pygeoapi-config.yml`: geothermal_wells_bht, geothermal_wells_temperature_profile (MATVIEW), bht_measurements, temp_depth_measurements, heat_flow, dst.
- I.views — DB: ogc_geothermal_wells_bht, ogc_geothermal_wells_temperature_profile (MAT), ogc_geothermal_wells_summary_heat_flow, ogc_geothermal_wells_interval_heat_flow, ogc_bht_measurements, ogc_temp_depth_measurements, ogc_heat_flow, ogc_dst.
- I.lexicon — `reference_lexicon_transfer.py` maps 46 `ref_*` → `nmw_ref_*` LexiconCategory + terms.
- I.jira — BDMS-826 "Geothermal Migration Planning" (Story, In Progress) under epic BDMS-843 "Geothermal Migration". 6 linked tasks tracked in §T (T18-T23).

## §V — invariants

- V1. `NMW_*` cols match legacy NM_Wells DDL exactly (name+type+PK). No renames except dropped `SSMA_TimeStamp`.
- V2. Mirror load respects parent→child order in `NMW_MIRROR_SPECS`; child never loads before parent.
- V3. `alembic upgrade head` then `downgrade` cleanly creates+drops all 18 tables + 8 views, no orphans.
- V4. Re-running mirror load is non-destructive at row level (truncate+COPY full reload OR ON CONFLICT skip) — no dup rows, no partial-state corruption.
- V5. After mirror load, `ogc_geothermal_wells_temperature_profile` matview refreshed; stale matview never served.
- V6. Each of 6 OGC collections resolves to existing backing view; pygeoapi config view name == migration view name.
- V7. `core/pygeoapi.py` unchanged from staging (reviewer note: reverted to original).
- V8. `NMW_WellRecords.SourceID` joined as TEXT (free-text citation), not numeric FK.
- V9. P2 lexicon mapping complete: every coded NMW col either in `LEXICON_REF_BY_COLUMN` (28, has ref_*) or `LEXICON_CANDIDATES_NO_REF` (11, needs new enum).
- V10. ORM `NMW_*` models declare index only (`index=True`, no ORM `ForeignKey`); FK enforcement lives in migration `c0d1e2f3a4b5` (`op.create_foreign_key`). Keep both in sync.
- V11. SQL-dump parser unwraps `CAST(expr AS <type>)` for parameterised types too (`Decimal(18,2)`, `nvarchar(10)`); never store the literal `CAST(...)` string in a mirror column.

## §T — tasks

id|status|task|cites
T1|x|18 NMW_* mirror tables in db/nmw_legacy.py|V1,I.db
T2|x|migration c0d1e2f3a4b5 tables+FK|V3,I.migrations
T3|x|migration d1e2f3a4b5c6 per-well OGC views|I.views
T4|x|migration e2f3a4b5c6d7 measurement OGC views|I.views
T5|x|nmw_sql_dump.py SSMS dump parser|I.cli
T6|x|nmw_mirror_transfer.py loader (dump+CSV)|V2,V4,I.cli
T7|x|reference_lexicon_transfer.py ref_*→lexicon|I.lexicon
T8|x|export_nmw_csvs.py pymssql export|I.export
T9|x|transfer_geothermal.py orchestrator|I.cli
T10|x|6 OGC collections in pygeoapi-config.yml|V6,I.ogc
T11|x|FK enforced via migration op.create_foreign_key; model index-only (resolved)|V2,V10
T12|x|add NMW_* mirror/loader/migration/OGC tests (tests/test_nmw_mirror.py, 19 tests); found+fixed CAST-unwrap bug B1|V1,V2,V3,V5,V6,V10,V11
T13|.|verify alembic down path drops all views+tables (V3) on real db|V3
T14|.|run end-to-end load vs real dump, capture row counts per table|V2,V4
T15|.|finish PR #738 body (truncated at "- I ") + reviewer notes|-
T16|.|P2 (later): transform NMW_* → Ocotillo model; build new enums for 11 LEXICON_CANDIDATES_NO_REF|C2,V9
T17|x|landed docs/nm_wells-migration.md (commit ccf566d9; force-add, docs/ gitignored). Referenced 4x: nmw_legacy.py:75,81,759; nmw_mirror_transfer.py:19|-

### BDMS-826 linked tasks (six; status mirrors Jira)

id|status|task|cites
T18|x|BDMS-827 read/review Geothermal Data Discovery Report (Jira Done)|I.jira
T19|x|BDMS-846 technical review complete (Jira Done)|I.jira
T20|x|BDMS-845 Geothermal Report finalized (Jira Done)|I.jira
T21|x|BDMS-847 update data-migration tracking mechanism (Jira Done)|I.jira
T22|x|BDMS-907 stakeholder engagement follow-up (Jira Done; blocks BDMS-826)|I.jira
T23|~|BDMS-848 Geothermal Migration Technical Implementation Plan (Jira In Progress) — umbrella for code tasks T1-T16|I.jira,T1,T16

## §B — bugs

id|date|cause|fix
B1|2026-06-23|_CAST_RE in transfers/nmw_sql_dump.py matched AS-type without parens only; parenthesised types (nvarchar(10), Decimal(18,2)) left value as literal "CAST(...)" string|V11; widened regex to allow one paren level
