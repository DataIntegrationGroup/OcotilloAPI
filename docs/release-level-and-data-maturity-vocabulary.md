# Release Level and Data Maturity Vocabulary

**Status:** First draft
**References:** ADR5, "One Enforcement Engine, Two Grant Tables" ("Two axes in
one column" section).

## Summary

`ReleaseMixin` gives every record one `release_status` column that is being
asked two unrelated questions at once: *who may see this* (visibility) and
*how far along is this in review* (data quality). This document proposes
splitting it into two independent fields — `release_level` and
`data_maturity` — defines their enum values and access implications, and maps
the 7 existing `release_status` values onto the new two-axis model. This is a
vocabulary decision to be confirmed before any schema or
migration work begins.

## Why split (ADR5's example)

San Acacia data is public and provisional at the same time —
`automated_ingestion/ocotillo/loader.py` has a comment working around exactly
this, and it's already tested working code, not just a proposal:
`tests/test_transducer_loader.py::test_public_and_provisional_can_both_be_true`
loads a reading as `release_status="public"` and asserts its independently-set
`data_maturity` comes back `"provisional"`. A single `release_status` column
can only hold one of those two answers at once, which is exactly why that test
needs a second column to pass.

## 1. What's actually live today, versus lexicon-only

`core/lexicon.json` lists 7 terms under `release_status`:
`draft`, `provisional`, `final`, `published`, `archived`, `public`, `private`.
"Live" here means a value drives different behavior somewhere (a query
predicate, an access gate) 
| Value | Drives behavior? | Where |
|---|---|---|
| `public` | **Yes** — the only real access gate | `== "public"` checked in every OGC/EDR view (`alembic/versions/baba91fe5e83_...py`, `f4a5b6c7d8e9_...py`, `z9a0b1c2d3e4_...py`), `services/chemistry.py`, `services/ngwmn_helper.py` |
| `private` | **Yes**, but only as "not public" | Set by legacy transfers (`transfers/well_transfer.py`, `transfers/waterlevels_transfer.py`) as the fallback when a source row isn't public. Never itself checked with `==` — it works by failing the `public` check, same effect as any other non-`public` value. |
| `draft` | **Yes**, as the creation default | `db/base.py`: `ReleaseMixin.release_status` defaults to `"draft"`. Same "not public" role as `private` — no query treats `draft` differently from `private`. |
| `archived` | **No** — settable, but inert | A real, accepted value: `tests/test_contact.py` PATCHes `release_status="archived"` onto a contact, email, phone, and address, and it round-trips correctly. But nothing queries for or excludes it — an archived record is only as hidden as any other non-`public` value, same as `draft`/`private`. |
| `provisional` *(as `release_status`, not `data_maturity`)* | **No** | Accepted by validation (seen in incidental test payloads, e.g. `tests/test_thing.py`), but no query checks `release_status == "provisional"`. The live `"provisional"` elsewhere in the codebase is a `data_maturity` value — this is literally the conflation: the same word is a dead `release_status` leftover and a live `data_maturity` term at once. |
| `published` | **No** | A developer comment confirms this directly: `data_migrations/migrations/_superseded/20260810_0001_consolidate_geographic_area_groups.py` says *"The only release_status the OGC views recognise [is 'public']. The lexicon category also contains 'published' and 'final', which no view predicate matches."* |
| `final` | **No** | Same comment, same conclusion — no view predicate matches it either. |

This matches `core/lexicon.json`'s own description of the category:
*"Release level of a record, i.e. who may see it. Also holds historical
review-state terms (provisional, final) kept for old rows; new code puts
review state in data_maturity."* The lexicon already documents its own
conflation.

## 2. `release_level` (visibility axis)

**Recommended values — the 3 already proven live, not new terms:**

| Value | Meaning | Access implication |
|---|---|---|
| `draft` | Not yet released | Hidden from all public and partner feeds. Visible to staff only, same as today. |
| `private` | Explicitly withheld | Hidden from all public and partner feeds, same as `draft` in effect today — the two are currently indistinguishable in behavior (see open questions). |
| `public` | Released | Visible on public OGC/EDR views and anywhere else the `public` gate is checked today. |

**Not recommended:** the ticket's example values (`internal`, `restricted`,
`public`, `embargoed`) have no precedent anywhere in the codebase — adopting
them would be a genuine new taxonomy, not a rename of what already works. The
3 values above are what the system already enforces in production today;
reusing them keeps this a vocabulary cleanup rather than a behavior change.
Whether the team wants the richer `internal`/`restricted`/`embargoed`
taxonomy instead is an open question below.

## 3. `data_maturity` (review-state axis)

**Recommended values — generalize the existing lexicon, not a boolean:**

| Value | Meaning |
|---|---|
| `provisional` | Not yet reviewed, default state |
| `in review` | Under active review, not yet decided |
| `approved` | Reviewed and confirmed |

**Not recommended:** a plain boolean `is_provisional`. `data_maturity`
already has `provisional` and `approved` as live values today (see below); the
third, `in review`, is defined in the lexicon but not currently produced by
any code path (`services/transducer_helper.py`'s derivation only ever outputs
`approved` or `provisional`). Even so, `in review` is a distinct state from
both — reserved for a 3-level review workflow the lexicon already anticipates
(USGS Aquarius' Working/In Review/Approved) — and collapsing it into a boolean
would foreclose that state rather than just leave it unused.

**Existing precedent:** `data_maturity` already exists, but only on
`TransducerObservation` (`db/transducer.py`). It isn't set directly by the
client — it's *derived* from `TransducerObservationBlock.review_status`
(`approved`/`not reviewed`), specifically so the two axes can't be set to
contradict each other (`services/transducer_helper.py`). That derivation
pattern is specific to transducer blocks, though — `Sample`, `Observation`,
and `Thing` have no equivalent `review_status` to derive from, so generalizing
`data_maturity` to those models likely means it becomes directly settable
under the `update` capability, not derived. Flagged as an open question below.

## 4. Mapping matrix: legacy `release_status` → new two-axis model

| Legacy `release_status` value | Belongs to | Becomes |
|---|---|---|
| `draft` | `release_level` | `draft` |
| `public` | `release_level` | `public` |
| `private` | `release_level` | `private` |
| `provisional` | `data_maturity` | `provisional` |
| `final` | `data_maturity` *(proposed)* | `approved` *(proposed)* |
| `published` | not yet decided | not yet decided — see open question 4 |
| `archived` | neither axis | not yet decided — likely a separate field, see open question 3 |
| N/A — no legacy `release_status` value | `data_maturity` | `in review` |

The first 3 are a straight rename, no decision needed. The rest need a real
row-count audit before anyone commits to a mapping (see open question 4) —
`provisional`'s `data_maturity` side is clear, but what `release_level` those
rows should get isn't; `final` is a reasonable guess, not a confirmed one;
`published` and `archived` are genuinely unresolved.

## Open questions

**Blockers** — need team sign-off before BDMS-1382 begins:

1. **Confirm `release_level`'s value set.** Reuse the 3 proven live terms
   (`draft`/`private`/`public`), or adopt the ticket's richer
   `internal`/`restricted`/`public`/`embargoed` taxonomy? .
2. **Confirm `data_maturity` stays 3-valued**, not a boolean `is_provisional`
   — since `in review` is already a distinct, used state.
3. **What does `archived` actually mean**, and does it belong on either axis
   at all, or is it a separate lifecycle concept (e.g. a timestamp or a third
   field) outside this split entirely? **Recommend against folding it into
   `release_level`:** an archived record can plausibly still be public (e.g.
   a retired monitoring well's historical readings, still visible, no longer
   active) — cramming `archived` into a single-valued `release_level` would
   make "public" and "archived" mutually exclusive, recreating the exact
   one-column-two-questions problem this document exists to fix, one level up.
4. **Row-level audit of `provisional`, `published`, and `final`.** How many
   existing rows use each value, and what should each become under the new
   model? ADR5 itself notes this kind of data migration has no CD path in
   this repo and is run by hand — the audit needs to happen before any rows
   move, not as part of this document.

**Future** — do not block this draft:

5. **Should `data_maturity` be directly settable on non-transducer models**
   (`Sample`, `Observation`, `Thing`), or should some of them eventually gain
   their own `review_status`-style derivation, matching the transducer
   pattern?

## References

- [ADR5.md](../ADR5.md): "Two axes in one column" section, and the sequencing
  that makes this document step 2.
- [db/base.py](../db/base.py): `ReleaseMixin`, current single-axis column.
- [db/transducer.py](../db/transducer.py): the one existing `data_maturity`
  precedent, and its derivation from `review_status`.
- [services/transducer_helper.py](../services/transducer_helper.py): the
  derivation logic itself.
- [core/lexicon.json](../core/lexicon.json): current `release_status` and
  `data_maturity` term definitions.
