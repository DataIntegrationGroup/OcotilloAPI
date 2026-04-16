"""
aem_ingest — NMBGMR AEM Data Sharing Platform ingest pipeline

Reads contractor-delivered AEM inversion files from three formats,
normalizes to a canonical PostGIS schema, loads into PostGIS, writes
Parquet bulk-download files to GCS, and returns STAC item stubs.

Three source formats:
  A) Aarhus Workbench *_byLayer.xyz  — space-delimited, long format
  B) Seogi Python rho CSV            — comma-delimited, wide format (40 layers)
  C) AGF LCI CSV                     — comma-delimited, wide format (39 layers)

Platform stack: GCS + PostGIS + GeoServer + GeoNetwork + STAC
Runtime: GCP Cloud Run, Python 3.11+

Authors: Marissa (data curator), Jake (platform engineer)
"""
