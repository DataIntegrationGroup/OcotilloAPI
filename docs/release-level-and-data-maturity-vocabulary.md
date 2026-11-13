# Release Level and Review State Vocabulary

**Status:** Updated

**References:** ADR5, "One Enforcement Engine, Two Grant Tables" ("Two axes in
one column" section). Blocks BDMS-1382.

## Summary

`ReleaseMixin` gives every record one `release_status` column that is being
asked two unrelated questions at once: *who may see this* (visibility) and
*how far along is this in review* (review state). This document proposes
splitting it into two independent fields — `release_level` and
`review_state` — defines their enum values and access implications, and maps
the 7 existing `release_status` values onto the new two-axis model. This is a
vocabulary decision to be confirmed before any schema or
migration work begins.

This field was renamed from `data_maturity` to `review_state` during
review. The real column on `TransducerObservation` is still called
`data_maturity` today — the actual rename hasn't happened yet. So below:
`data_maturity` means today's real code, `review_state` means the proposed
name.

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
predicate, an access gate).

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

**Recommended values — resolved (open question 1):**

| Value | Meaning | Access implication |
|---|---|---|
| `pending` | Not yet released to any audience, because no release decision has been made yet | Hidden from all public and partner feeds. Visible to staff only, same as today. |
| `private` | Explicitly withheld — a decision was made to hide it | Hidden from all public and partner feeds, same as `pending` in effect today — the two are currently indistinguishable in behavior, but the distinction is intentional going forward. |
| `public` | Released | Visible on public OGC/EDR views and anywhere else the `public` gate is checked today. |

`private` and `public` are a straight reuse of the live `release_status`
values, same word either side. `draft` is renamed to `pending`: PR review
pointed out "draft" reads like a review-state term, not a visibility one,
and that "not yet released because undecided" (`pending`)
is a meaningfully different statement from "explicitly withheld" (`private`)
even though the two behave identically today — see the mapping matrix for
what the rename actually costs.

**Not recommended:** the ticket's example values (`internal`, `restricted`,
`public`, `embargoed`) have no precedent anywhere in the codebase — adopting
them would be a genuine new taxonomy, not a rename of what already works.

## 3. `review_state`

**Recommended values — generalize the existing lexicon, not a boolean:**

| Value | Meaning |
|---|---|
| `provisional` | Not yet reviewed, default state |
| `approved` | Reviewed and confirmed |
| `unknown` | Review state cannot be determined because its review history is undocumented or it came from a source whose QA/QC the Bureau cannot confirm. Not a default for new data, which still starts as `provisional`. |

**Not recommended:** a plain boolean `is_provisional`; `in review` (unused
today); or `published` — see the mapping matrix for why. Actual source is
tracked separately via the existing `DataProvenance` table, not here.

**Existing precedent:** this field already exists under the name
`data_maturity`, but only on `TransducerObservation` (`db/transducer.py`).
It isn't set directly by the client — it's *derived* from
`TransducerObservationBlock.review_status` (`approved`/`not reviewed`),
specifically so the two axes can't be set to contradict each other
(`services/transducer_helper.py`). That derivation pattern is specific to
transducer blocks, though — `Observation` has no equivalent block to derive
from, so it would need `review_state` directly settable under the `update`
capability instead. See open question 4 for which tables get `review_state`
at all, and why it's a separate mixin
rather than part of `ReleaseMixin`.

## 4. Mapping matrix: legacy `release_status` → new two-axis model

| Legacy `release_status` value | Belongs to | Becomes |
|---|---|---|
| `draft` | `release_level` | `pending` |
| `public` | `release_level` | `public` |
| `private` | `release_level` | `private` |
| `provisional` | `review_state` | `provisional` |
| `published` | `review_state` | `unknown` |
| `final` | `review_state` *(proposed)* | `approved` *(proposed)* |
| `archived` | neither axis | not yet decided — likely a separate field, see open question 3 |

`public`/`private` are a straight rename, no decision needed. `draft`
becomes `pending` (open question 1) — same underlying behavior, renamed
value, which is still a real data migration for every existing `draft` row,
not just a documentation change. `provisional` maps cleanly to
`review_state`, same word either side, on the three tables that get a
`review_state` column — and per open question 2's audit, no other table has
any rows using `provisional`/`published`/`final` at all, so there is nothing
left to decide for "any other table." `published` becomes `unknown`
(deliberately not the same word, since the legacy `published` and the old
`review_state=published` proposal were two unrelated things that happened to
share a name — `unknown` removes that collision). `final` is a reasonable
guess on both axes, not a confirmed one, but moot in practice since no rows
use it; `archived` is genuinely unresolved; `TransducerObservation`/
`TransducerObservationBlock` rows where `release_status` itself is literally
`provisional` are their own separate case, see open question 5.

## Open questions

**Blockers** — need team sign-off before BDMS-1382 begins:

1. **Resolved: `release_level`'s value set is `pending`/`private`/`public`.**
   `private`/`public` are a straight reuse of the live values; `draft` is
   renamed to `pending`, since it reads as a review-state term rather than a
   visibility one. The ticket's richer
   `internal`/`restricted`/`embargoed` taxonomy was not adopted — no
   precedent for it exists anywhere in the codebase.

**Future** — do not block this draft:

2. **Resolved, via a row-level audit of live data:** `published`/`final`
   have zero rows anywhere, and `provisional` as a `release_status` value
   exists only on `TransducerObservation`/`TransducerObservationBlock` —
   every other table has none. Nothing to decide except for those two
   tables, promoted to their own question — see open question 5.
3. **`archived` doesn't get a slot in either axis for now.** Nothing today
   depends on it behaving differently from `pending`/`private`. If a real need
   for a distinct archived/retired state emerges later, it gets its own
   field then — not a value crammed into `release_level`, since an archived
   record can plausibly still be public (e.g. a retired monitoring well's
   historical readings), and squeezing it into a single-valued
   `release_level` would make "public" and "archived" mutually exclusive.
4. **Resolved:** `review_state` gets its own mixin, not folded into
   `ReleaseMixin` — not every record has a review state. Starts on
   `Observation`, `TransducerObservation`, and `TransducerObservationBlock`
   only; see Section 3 for how each sets its value.
5. **Assuming, not yet confirmed: the `TransducerObservation` (76,725
   rows) and `TransducerObservationBlock` (108 rows) rows with
   `release_status='provisional'` become `release_level='pending'`,**
   migrated in the same pass as every other table rather than held back
   separately. Based on the evidence so far (every one of these rows also
   has `data_maturity='provisional'`, never `approved`; `docs/
   hydrograph-correction-publish.md` describes "publishing as provisional"
   as a deliberate operator choice distinct from `public`) — needs real
   sign-off from the team.

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
- [db/data_provenance.py](../db/data_provenance.py): where source/origin
  metadata is tracked separately from `review_state`'s review-state
  question.
