"""Single source of truth for the pygeoapi materialized views.

Both the ``oco refresh-pygeoapi-materialized-views`` CLI command and the
pg_cron nightly-refresh alembic migration import this tuple so the view set is
defined in exactly one place. Add or remove a view here and both stay in sync.
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
