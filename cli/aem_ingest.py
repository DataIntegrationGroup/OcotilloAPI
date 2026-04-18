# flake8: noqa: E501
from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import click
import typer

from schemas.aem import (
    IngestConfig,
    InversionCode,
    ProcessingStage,
    SkytemSystem,
    SourceFormat,
)
from services.aem_batch import run_batch
from services.aem_ingest import run_ingest
from services.aem_parsers import (
    detect_format,
    parse_agf_lci,
    parse_bylayer,
    parse_seogi_rho,
)
from services.aem_parsers.common import CANONICAL_COLUMNS

app = typer.Typer(
    name="aem-ingest",
    help="NMBGMR AEM ingest pipeline — load inversion files to PostGIS + GCS",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def _resolve_bucket(explicit_bucket: str | None) -> str:
    bucket = (
        explicit_bucket
        or os.environ.get("AEM_GCS_BUCKET")
        or os.environ.get("GCS_BUCKET_NAME")
    )
    if not bucket:
        raise typer.BadParameter(
            "GCS bucket is required. Pass --gcs-bucket or set AEM_GCS_BUCKET/GCS_BUCKET_NAME."
        )
    return bucket


@app.command()
def run(
    filepath: Annotated[
        Path, typer.Argument(help="Path to the inversion file", exists=True)
    ],
    survey_id: Annotated[
        str, typer.Option("--survey-id", help="e.g. gila_animas_2025")
    ],
    stage: Annotated[
        str,
        typer.Option(
            "--stage",
            help="Processing stage",
            click_type=click.Choice(["preliminary_inversion", "final_inversion"]),
        ),
    ],
    inversion_code: Annotated[
        str,
        typer.Option(
            "--inversion-code",
            help="Inversion software",
            click_type=click.Choice(["seogi_python", "aarhus_sci", "aarhus_lci"]),
        ),
    ],
    contractor: Annotated[
        str, typer.Option("--contractor", help="e.g. 'GeoTech/Seogi'")
    ],
    db_conn: Annotated[
        Optional[str],
        typer.Option(
            "--db-conn", help="Optional PostgreSQL connection string override"
        ),
    ] = None,
    gcs_bucket: Annotated[
        Optional[str], typer.Option("--gcs-bucket", help="GCS bucket name override")
    ] = None,
    source_gcs_path: Annotated[
        str,
        typer.Option(
            "--source-gcs-path",
            help=(
                "GCS path for the source file (from the mapper's proposed_gcs_path). "
                "e.g. 'surveys/estancia_2025/aem/inversion/preliminary/rho_GL250194_F01.csv'"
            ),
        ),
    ] = ...,
    flight_id: Annotated[
        Optional[str],
        typer.Option("--flight-id", help="Flight ID for Seogi (e.g. F02)"),
    ] = None,
    system: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            help="SkyTEM system for AGF",
            click_type=click.Choice(["306hp", "312hp"]),
        ),
    ] = None,
    date_acquired: Annotated[
        Optional[str],
        typer.Option("--date-acquired", help="Acquisition date (YYYY-MM-DD)"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Run the full ingest pipeline for a single AEM inversion file."""
    _setup_logging(verbose)

    config = IngestConfig(
        filepath=str(filepath),
        survey_id=survey_id,
        processing_stage=ProcessingStage(stage),
        inversion_code=InversionCode(inversion_code),
        contractor=contractor,
        db_conn_string=db_conn,
        gcs_bucket=_resolve_bucket(gcs_bucket),
        source_gcs_path=source_gcs_path,
        flight_id=flight_id,
        system=SkytemSystem(system) if system else None,
        date_acquired=(
            datetime.date.fromisoformat(date_acquired) if date_acquired else None
        ),
    )

    stac_stub = run_ingest(config)
    typer.echo(json.dumps(stac_stub, indent=2))


@app.command()
def detect(
    filepath: Annotated[
        Path, typer.Argument(help="Path to the inversion file", exists=True)
    ],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Detect the format of an AEM inversion file (no DB or GCS needed)."""
    _setup_logging(verbose)
    fmt = detect_format(str(filepath))
    typer.echo(f"Format: {fmt.value}")


@app.command()
def parse(
    filepath: Annotated[
        Path, typer.Argument(help="Path to the inversion file", exists=True)
    ],
    flight_id: Annotated[
        Optional[str],
        typer.Option("--flight-id", help="Flight ID for Seogi (e.g. F02)"),
    ] = None,
    system: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            help="SkyTEM system for AGF",
            click_type=click.Choice(["306hp", "312hp"]),
        ),
    ] = None,
    out: Annotated[
        Optional[Path],
        typer.Option("--out", "-o", help="Output path (.parquet or .csv)"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Parse an AEM file to canonical schema without loading to DB."""
    _setup_logging(verbose)
    fmt = detect_format(str(filepath))

    if fmt == SourceFormat.BYLAYER:
        df = parse_bylayer(str(filepath))
    elif fmt == SourceFormat.SEOGI_RHO:
        df = parse_seogi_rho(str(filepath), flight_id=flight_id)
    else:
        if system is None:
            typer.echo(
                "Error: AGF LCI format requires --system (306hp or 312hp)", err=True
            )
            raise typer.Exit(code=1)
        df = parse_agf_lci(str(filepath), system=system)

    typer.echo(
        f"Parsed: {len(df):,} rows, {df['record_id'].nunique():,} soundings",
        err=True,
    )

    if out is None:
        typer.echo(df.describe().to_string())
    elif str(out).endswith(".parquet"):
        import pyarrow as pa
        import pyarrow.parquet as pq

        cols = [c for c in CANONICAL_COLUMNS if c in df.columns]
        table = pa.Table.from_pandas(df[cols], preserve_index=False)
        pq.write_table(table, str(out), compression="snappy")
        typer.echo(f"Written to {out}", err=True)
    else:
        df.to_csv(str(out), index=False)
        typer.echo(f"Written to {out}", err=True)


@app.command()
def batch(
    mapping: Annotated[
        Path, typer.Option("--mapping", help="Path to gcs_path_mapping.csv")
    ],
    db_conn: Annotated[
        Optional[str],
        typer.Option(
            "--db-conn", help="Optional PostgreSQL connection string override"
        ),
    ] = None,
    bucket: Annotated[
        Optional[str], typer.Option("--bucket", help="GCS bucket name override")
    ] = None,
    root: Annotated[
        Optional[str],
        typer.Option("--root", help="Override source path root for local Drive copies"),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be ingested")
    ] = False,
    limit: Annotated[
        Optional[int], typer.Option("--limit", help="Only ingest the first N files")
    ] = None,
    survey: Annotated[
        Optional[str], typer.Option("--survey", help="Only ingest this survey_id")
    ] = None,
    stage: Annotated[
        Optional[str],
        typer.Option("--stage", help="Only ingest this processing_stage"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Run batch ingest for every ingestible file listed in the mapping CSV."""
    _setup_logging(verbose)
    stac_items = run_batch(
        mapping_path=str(mapping),
        db_conn_string=db_conn,
        gcs_bucket=_resolve_bucket(bucket),
        root_override=root,
        dry_run=dry_run,
        limit=limit,
        survey_filter=survey,
        stage_filter=stage,
    )
    if not dry_run:
        typer.echo(json.dumps(stac_items, indent=2, default=str))
