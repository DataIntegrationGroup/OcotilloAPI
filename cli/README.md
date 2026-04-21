# CLI

This directory contains Typer-based command entrypoints for operational and migration workflows.

## Main entrypoint

- `cli/cli.py`
- `cli/aem_ingest.py`

Run commands from repo root:

```bash
source .venv/bin/activate
uv sync --locked --extra cli
python -m cli.cli --help
```

## Common commands

- `python -m cli.cli restore-local-db path/to/dump.sql`
- `python -m cli.cli restore-local-db gs://ocotillo/sql-exports/latest.sql.gz`
- `python -m cli.cli scoped-transfer --pointid SM-0001`
- `python -m cli.cli transfer-results`
- `python -m cli.cli compare-duplicated-welldata`
- `python -m cli.cli alembic-upgrade-and-data`

## AEM commands

The AEM ingest commands are mounted under `aem-ingest`:

- `python -m cli.cli aem-ingest detect <filepath>`
- `python -m cli.cli aem-ingest parse <filepath> [--flight-id F02] [--system 306hp|312hp] [--out parsed.parquet]`
- `python -m cli.cli aem-ingest run <filepath> --survey-id <survey> --stage preliminary_inversion|final_inversion --inversion-code seogi_python|aarhus_sci|aarhus_lci --contractor <name> --source-gcs-path <gcs/path> [--skip-stac-uploads]`
- `python -m cli.cli aem-ingest batch --mapping aem/gcs_path_mapping.csv [--bucket <gcs-bucket>] [--survey <survey>] [--stage <processing_stage>] [--limit N] [--dry-run] [--skip-soundings-upload] [--skip-asset-db-publish] [--skip-stac-uploads]`

Purpose by command:

- `detect`: identify the supported AEM source format for a single file.
- `parse`: normalize a single file to the canonical sounding schema without touching PostGIS or GCS.
- `run`: execute the full single-file ingest pipeline into PostGIS and GCS artifacts, write replayable STAC payloads, and upsert them into `pgstac`.
- `batch`: migrate all filtered `MOVE` rows from a mapper-generated `gcs_path_mapping.csv`, convert KMZ files to GeoPackage sidecars during upload, then ingest eligible inversion files and publish eligible AEM GeoTIFF assets.

AEM examples:

```bash
source .venv/bin/activate

python -m cli.cli aem-ingest detect data/aem/rho_GL250193_F02.csv

python -m cli.cli aem-ingest parse data/aem/rho_GL250193_F02.csv \
  --flight-id F02 \
  --out /tmp/rho_GL250193_F02.parquet

python -m cli.cli aem-ingest run data/aem/rho_GL250193_F02.csv \
  --survey-id gila_animas_2025 \
  --stage preliminary_inversion \
  --inversion-code seogi_python \
  --contractor "GeoTech/Seogi" \
  --source-gcs-path surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv

python -m cli.cli aem-ingest batch \
  --mapping aem/gcs_path_mapping.csv \
  --bucket nmbgmr-aem-data \
  --survey estancia_2025 \
  --dry-run

python -m cli.cli aem-ingest batch \
  --mapping aem/gcs_path_mapping.csv \
  --bucket nmbgmr-aem-data \
  --skip-soundings-upload

python -m cli.cli aem-ingest batch \
  --mapping aem/gcs_path_mapping.csv \
  --bucket nmbgmr-aem-data \
  --skip-asset-db-publish

python -m cli.cli aem-ingest batch \
  --mapping aem/gcs_path_mapping.csv \
  --bucket nmbgmr-aem-data \
  --skip-stac-uploads
```

AEM runtime notes:

- `run` and `batch` require a GCS bucket via `--gcs-bucket` or `--bucket`, or `AEM_GCS_BUCKET` / `GCS_BUCKET_NAME`.
- `run` and `batch` also need database connectivity unless you are doing a dry run.
- `run` writes replayable STAC payload artifacts under the survey metadata prefix and loads them into `pgstac` with `pypgstac`.
- `--skip-stac-uploads` skips STAC payload generation, GCS STAC artifact writes, and `pgstac` loading.
- `run` can also add survey-level GeoServer WMS/WFS/WCS assets to the STAC Collection when `GEOSERVER_PUBLIC_URL` and `GEOSERVER_WORKSPACE` are configured.
- `batch` now subsumes the legacy `aem/aem_migrate.py` flow: it uploads filtered `MOVE` rows to GCS first, emits the same migration log/summary files, and converts uploaded `.kmz` files into `.gpkg` sidecars.
- `batch` also uploads `geotiff` `MOVE` rows from the mapping CSV to GCS asset storage and attempts GeoServer publication when GeoServer credentials are configured.
- `--skip-asset-db-publish` keeps that GeoTIFF path out of the Ocotillo asset table while still attempting GeoServer publication.
- OcotilloAPI still does not serve the STAC API; the dedicated STAC stack still owns `stac-fastapi-pgstac`. GeoTIFF GeoServer publication is handled best-effort during `batch` when GeoServer credentials are configured.
- `parse` requires `--system` for AGF LCI files and may require `--flight-id` for Seogi inputs.

## Guides

- Beginner guide for scoped transfers: [scoped-transfer.md](./scoped-transfer.md)

## Notes

- CLI logging is written to `cli/logs/`.
- Keep CLI commands thin; move heavy logic into service/transfer modules.
