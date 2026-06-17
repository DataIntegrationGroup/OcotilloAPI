"""Curated pygeoapi materialized-view list for the CLI refresh command.

``oco refresh-pygeoapi-materialized-views`` refreshes these views (in order)
by default. The nightly pg_cron job does NOT use this list -- its SQL helper
discovers the ``ogc_*`` materialized views from the catalog at run time (see
alembic migration ``x2y3z4a5b6c7``) to stay immutable and self-contained.
"""

# Order is the order views are refreshed in.
PYGEOAPI_MATERIALIZED_VIEWS: tuple[str, ...] = (
    "ogc_latest_depth_to_water_wells",
    "ogc_water_elevation_wells",
    "ogc_avg_tds_wells",
    "ogc_depth_to_water_trend_wells",
    "ogc_water_well_summary",
    "ogc_major_chemistry_results",
    "ogc_minor_chemistry_wells",
)
