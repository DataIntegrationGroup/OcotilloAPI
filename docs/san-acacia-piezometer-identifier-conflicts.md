# San Acacia piezometer identifier conflicts

Found 2026-08-19 while reconciling Diver-HUB monitoring points against Ocotillo
wells for the automated ingestion pipeline. Present in **production**, not only
staging.

None of this blocks ingestion — the vendor names its points `SO-####` and
Ocotillo agrees on those, so matching is exact. It matters to anyone who
identifies these wells by their field names instead.

## 1. Two identifier sources disagree about which well is which

`thing_id_link` holds a `NMBGMR` identifier and an unattributed `Unknown` one
for most `SO-` wells. For the BRN-E04 pair they contradict each other:

| Well | NMBGMR | Unknown |
|---|---|---|
| `SO-0131` | `BRN-E04B (shallow)` | `BRN-E04A` |
| `SO-0132` | `BRN-E04A (deep)` | `BRN-E04B` |

The two sources assign A and B to opposite wells. Since these are a paired
shallow/deep piezometer nest, resolving `BRN-E04A` to the wrong one attributes a
shallow water-level series to a deep well or the reverse.

`SO-0131` is one of the 38 points the ingestion pipeline reads.

## 2. A site number disagreement, which may collide with a real site

| Well | NMBGMR | Unknown |
|---|---|---|
| `SO-0262` | `NRCS 3A (Deep)` | `NRCS 2 (Deep)` |
| `SO-0263` | `NRCS 3B (Shallow monitor well)` | `NRCS 2 (Shallow)` |

NRCS site 2 exists separately — `SO-0274` is `NRCS Site 2 Well 2`, and
`SO-0275`/`SO-0276` are its piezometers `2A`/`2B`. So the `Unknown` labels on
`SO-0262`/`SO-0263` either duplicate a different site's number or the `NMBGMR`
labels are wrong. One of the two is.

## 3. The A/B suffix does not consistently mean depth

Where NMBGMR annotates depth, the convention reverses between sites:

| Site | A | B |
|---|---|---|
| `BRN-E04` | deep | shallow |
| `HWY-W09` | deep | shallow |
| `SBB-W02` | deep | shallow |
| `NRCS 3` | deep | shallow |
| `NRCS 4` | **shallow** | **deep** |
| `NRCS 6` | **shallow** | **deep** |

It is not even consistent within the NRCS series: site 3 has A as the deep well,
sites 4 and 6 have A as the shallow one.

So the suffix cannot be used to infer completion depth, and any code or analysis
that assumes "A is the deep one" is right for four sites and wrong for two.

## Why it was not caught earlier

Nothing reads these identifiers programmatically today. The reconciler found it
because matching on `alternate_id` produced a *confident* match for `BRN-E04A` —
a single hit on `SO-0131`, contradicting NMBGMR, with no ambiguity flag, because
the `(shallow)` suffix makes the two strings differ.

External-id matching is now opt-in for that reason
(`automated_ingestion/sources/san_acacia/reconcile.py`), with a test pinning
these rows. That is a guard, not a fix: the underlying records still disagree.

## What resolving it needs

Someone with the field records or the drilling logs, deciding per pair which
physical well is which. The depth annotations in the NMBGMR labels are the only
in-database evidence, and for BRN-E04 they are exactly what is in dispute.

Worth checking whether the `Unknown` organization rows have a determinable
provenance — 4,825 links carry it, and if they came from a single import their
reliability can be assessed as a group rather than well by well.
