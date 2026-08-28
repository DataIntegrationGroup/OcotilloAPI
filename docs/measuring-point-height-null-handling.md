# Measuring-point height: null handling

**Status:** Accepted
**Date:** 2026-08-26
**Decided by:** Cris Morton + Ethan Mamer
**Recorded by:** Kelsey Smuczynski

## Context

Three OGC layers compute depth-to-water and water-elevation values from measuring-point height:

- `water_well_summary`
- `depth_to_water_trend_wells`
- `water_elevation_wells`

Each uses `COALESCE(measuring_point_height, 0)` in the calculation. When `measuring_point_height` is null, this treats the measuring point as ground surface level (0), rather than excluding the record or flagging it for review.

## Decision

A missing or null measuring-point height defaults to zero (ground surface level) in these calculations. Cris Morton confirmed this is the correct default on 2026-08-26.

## Consequences

- Depth-to-water and water-elevation values for wells with no recorded measuring-point height are calculated as if the measurement were taken at ground surface. These values carry more uncertainty than wells with a known measuring point, but nothing in the output currently distinguishes them.
- If a future review determines this default introduces meaningful error for a subset of wells (for example, wells with a well casing or stickup that's unusually tall), revisit this decision and consider flagging affected records instead of silently defaulting to zero.
- Any new analytic layer that calculates depth-to-water or water-elevation from measuring-point height should follow this same convention, or explicitly document why it doesn't.
